"""Accounts: the bank accounts and credit cards that statements are filed under.

A statement belongs to at most one account, and every transaction carries its statement's account_id so that
filtering by account is a plain indexed query. Moving a statement updates both in one step.
"""
from __future__ import annotations

from bson import ObjectId
from pymongo.errors import DuplicateKeyError

from app.core.errors import AppError
from app.database.mongo import ACCOUNTS, RAW_TRANSACTIONS, STATEMENT_UPLOADS
from app.models.documents import ACCOUNT_COLORS, account_doc
from app.services.query import oid
from app.utils.dates import month_end
from app.utils.money import r2

TYPE_LABEL = {"bank": "a bank account", "credit_card": "a credit card"}


async def get_account(db, user_id: ObjectId, account_id) -> dict:
    acc = await db[ACCOUNTS].find_one({"_id": oid(account_id, "account id"), "user_id": user_id})
    if not acc:
        raise AppError("Account not found", 404, "not_found")
    return acc


async def check_for_statement(db, user_id: ObjectId, account_id, statement_type: str) -> ObjectId:
    """The account must exist, belong to the user, and be the same kind as the statement."""
    acc = await get_account(db, user_id, account_id)
    if acc["account_type"] != statement_type:
        raise AppError(f"This is a statement for {TYPE_LABEL.get(statement_type, 'an account')}. Choose "
                       f"{TYPE_LABEL.get(statement_type, 'a matching account')}, not '{acc['name']}'.", 400, "account_type_mismatch")
    return acc["_id"]


async def suggest_account(db, user_id: ObjectId, bank_name: str | None, account_type: str) -> str | None:
    """The account a new statement most likely belongs to: the only one of this kind for the same bank."""
    if not bank_name:
        return None
    matches = [a async for a in db[ACCOUNTS].find({"user_id": user_id, "account_type": account_type}, {"bank_name": 1})
               if (a.get("bank_name") or "").casefold() == bank_name.casefold()]
    return str(matches[0]["_id"]) if len(matches) == 1 else None


async def assign_statement(db, user_id: ObjectId, upload_id: ObjectId, account_id: str | None) -> dict:
    """File a statement (and all its transactions) under an account, or unassign it with None."""
    up = await db[STATEMENT_UPLOADS].find_one({"_id": upload_id, "user_id": user_id})
    if not up or up.get("processing_status") == "deleting":
        raise AppError("Statement not found", 404, "not_found")
    target = await check_for_statement(db, user_id, account_id, up.get("account_type", "bank")) if account_id else None
    await db[STATEMENT_UPLOADS].update_one({"_id": upload_id}, {"$set": {"account_id": target}})
    res = await db[RAW_TRANSACTIONS].update_many({"user_id": user_id, "upload_id": upload_id}, {"$set": {"account_id": target}})
    return {"account_id": str(target) if target else None, "moved_transactions": res.modified_count}


async def delete_account(db, user_id: ObjectId, account_id: str) -> dict:
    """Statements and transactions are kept; they simply become unassigned."""
    acc = await get_account(db, user_id, account_id)
    ups = await db[STATEMENT_UPLOADS].update_many({"user_id": user_id, "account_id": acc["_id"]}, {"$set": {"account_id": None}})
    txns = await db[RAW_TRANSACTIONS].update_many({"user_id": user_id, "account_id": acc["_id"]}, {"$set": {"account_id": None}})
    await db[ACCOUNTS].delete_one({"_id": acc["_id"]})
    return {"unassigned_statements": ups.modified_count, "unassigned_transactions": txns.modified_count}


async def _activity(db, user_id: ObjectId, account_key) -> dict:
    """Counts, dates, latest balance and the latest month's money in/out for one account (None = unassigned)."""
    q = {"user_id": user_id, "account_id": account_key}
    count = await db[RAW_TRANSACTIONS].count_documents(q)
    out = {"transaction_count": count, "date_range": {"start": None, "end": None}, "balance": None, "latest_month": None}
    if not count:
        return out
    first = await db[RAW_TRANSACTIONS].find_one(q, {"transaction_date": 1}, sort=[("transaction_date", 1)])
    last = await db[RAW_TRANSACTIONS].find_one(q, {"transaction_date": 1}, sort=[("transaction_date", -1)])
    out["date_range"] = {"start": first["transaction_date"].strftime("%Y-%m-%d"), "end": last["transaction_date"].strftime("%Y-%m-%d")}

    bal = await db[RAW_TRANSACTIONS].find_one({**q, "balance": {"$ne": None}}, {"balance": 1, "transaction_date": 1},
                                              sort=[("transaction_date", -1), ("_id", -1)])
    if bal:
        out["balance"] = {"amount": r2(bal["balance"]), "as_of": bal["transaction_date"].strftime("%Y-%m-%d")}

    start = last["transaction_date"].replace(day=1)
    month = await db[RAW_TRANSACTIONS].find({**q, "transaction_date": {"$gte": start, "$lte": month_end(start)}},
                                            {"debit_amount": 1, "credit_amount": 1}).to_list(None)
    out["latest_month"] = {
        "year": start.year, "month": start.month, "label": start.strftime("%B %Y"),
        "money_in": r2(sum(t.get("credit_amount") or 0 for t in month)),
        "money_out": r2(sum(t.get("debit_amount") or 0 for t in month)),
    }
    return out


async def account_summaries(db, user_id: ObjectId) -> dict:
    accounts = await db[ACCOUNTS].find({"user_id": user_id}).sort("name_key", 1).to_list(None)
    counts: dict = {}
    async for u in db[STATEMENT_UPLOADS].find({"user_id": user_id, "processing_status": "completed"}, {"account_id": 1}):
        counts[u.get("account_id")] = counts.get(u.get("account_id"), 0) + 1

    rows = []
    for a in accounts:
        rows.append({
            "id": str(a["_id"]), "name": a["name"], "account_type": a["account_type"], "bank_name": a.get("bank_name"),
            "last4": a.get("last4"), "color": a["color"], "statement_count": counts.get(a["_id"], 0),
            **await _activity(db, user_id, a["_id"]),
        })
    un = await _activity(db, user_id, None)
    unassigned = {"statement_count": counts.get(None, 0), "transaction_count": un["transaction_count"]} if un["transaction_count"] else None

    balances = [r["balance"]["amount"] for r in rows if r["account_type"] == "bank" and r["balance"]]
    return {
        "accounts": rows, "unassigned": unassigned,
        "totals": {"bank_balance": r2(sum(balances)), "bank_accounts_with_balance": len(balances),
                   "bank_account_count": sum(1 for r in rows if r["account_type"] == "bank"),
                   "card_count": sum(1 for r in rows if r["account_type"] == "credit_card")},
    }


async def create_account(db, user_id: ObjectId, name: str, account_type: str, bank_name: str | None,
                         last4: str | None, color: str | None) -> dict:
    n = await db[ACCOUNTS].count_documents({"user_id": user_id})
    doc = account_doc(user_id, name, account_type, bank_name, last4, color or ACCOUNT_COLORS[n % len(ACCOUNT_COLORS)])
    try:
        await db[ACCOUNTS].insert_one(doc)
    except DuplicateKeyError:
        raise AppError(f"You already have an account called '{name}'.", 409, "duplicate") from None
    return doc


async def auto_setup(db, user_id: ObjectId) -> dict:
    """One account per bank and kind among the statements that aren't filed anywhere yet (named after the bank)."""
    ups = await db[STATEMENT_UPLOADS].find(
        {"user_id": user_id, "processing_status": "completed", "account_id": None}).to_list(None)
    created, assigned = 0, 0
    for u in ups:
        bank = u.get("bank_name") or "Unknown Bank"
        kind = u.get("account_type", "bank")
        acc = await db[ACCOUNTS].find_one({"user_id": user_id, "name_key": bank.casefold()})
        if acc is None:
            acc = await create_account(db, user_id, bank, kind, bank, None, None)
            created += 1
        elif acc["account_type"] != kind:
            continue  # a differently-typed account already uses that name; leave this statement for the user
        await assign_statement(db, user_id, u["_id"], str(acc["_id"]))
        assigned += 1
    return {"created_accounts": created, "assigned_statements": assigned}
