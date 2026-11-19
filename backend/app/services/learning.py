"""Learning from corrections.

When you move a transaction to another category, Tally can offer to remember that for the merchant as a rule. Nothing is
ever learned silently: a rule is only created when you accept a suggestion, and it shows up in Categories & Rules like any
other rule (priority above every built-in rule), where you can edit, disable or delete it.

A learned rule matches the merchant name exactly. The engine tests "MERCHANT | DESCRIPTION", so the pattern is anchored to
the merchant part: "Swiggy" is learned without catching "Swiggy Instamart", and a word in a narration never matches.
"""
from __future__ import annotations

import re
from collections import Counter, defaultdict

from bson import ObjectId
from pymongo.errors import DuplicateKeyError

from app.categorization.engine import validate_pattern
from app.core.errors import AppError
from app.database.mongo import CATEGORIES, CATEGORIZATION_RULES, LEARNING_DISMISSED, RAW_TRANSACTIONS
from app.models.documents import rule_doc
from app.services.categories import load_engine, recategorize_all
from app.services.query import oid
from app.services.summaries import refresh_summaries
from app.utils.dates import utcnow

LEARNED_PREFIX = "Learned: "
LEARNED_PRIORITY = 150      # above every built-in rule (the highest is 100), so what you taught wins
MIN_EVIDENCE = 2            # corrections to the same category before Tally proposes a rule unprompted
MAX_MERCHANT_LEN = 120
MAX_SUGGESTIONS = 10
MAX_UNCATEGORISED = 15


def learnable(merchant: str | None) -> bool:
    """'Unknown' is what Tally calls a payee it could not read, so a rule for it would catch unrelated payments."""
    return bool(merchant) and merchant.strip().lower() != "unknown" and len(merchant) <= MAX_MERCHANT_LEN


def merchant_pattern(merchant: str) -> str:
    return rf"^{re.escape(merchant.strip().upper())}\s\|"


def _type_filter(applies_to: str) -> dict:
    return {} if applies_to == "any" else {"transaction_type": applies_to}


async def similar_count(db, user_id: ObjectId, merchant: str, category_id: ObjectId, applies_to: str = "any",
                        exclude_id: ObjectId | None = None) -> int:
    """Other transactions from this merchant that a rule would move (your own manual choices are never moved)."""
    q = {"user_id": user_id, "normalized_merchant": merchant, "manual_override": {"$ne": True},
         "category_id": {"$ne": category_id}, **_type_filter(applies_to)}
    if exclude_id:
        q["_id"] = {"$ne": exclude_id}
    return await db[RAW_TRANSACTIONS].count_documents(q)


async def suggestion_after_correction(db, user_id: ObjectId, txn: dict, category: dict) -> dict | None:
    """What to offer right after a manual category change, or None if a rule would add nothing."""
    merchant = txn.get("normalized_merchant")
    if not learnable(merchant):
        return None
    applies_to = txn.get("transaction_type", "debit")
    engine = await load_engine(db, user_id)
    # the rules already file this merchant under that category (for example you moved it back to what they say)
    if engine.categorize(merchant, None, applies_to).category_id == str(category["_id"]):
        return None
    return {
        "merchant": merchant, "category_id": str(category["_id"]), "category_name": category["name"], "applies_to": applies_to,
        "similar_count": await similar_count(db, user_id, merchant, category["_id"], applies_to, txn["_id"]),
    }


async def learn_rule(db, user_id: ObjectId, merchant: str, category_id: str, applies_to: str = "any") -> dict:
    merchant = merchant.strip()
    if not learnable(merchant):
        raise AppError("Tally can't make a rule for that payee. Use a rule with your own pattern instead.", 400, "not_learnable")
    cid = oid(category_id, "category id")
    cat = await db[CATEGORIES].find_one({"_id": cid, "user_id": user_id})
    if not cat:
        raise AppError("Category not found", 404, "not_found")
    pattern = merchant_pattern(merchant)
    validate_pattern(pattern)  # defence in depth: an escaped merchant always passes

    existing = await db[CATEGORIZATION_RULES].find_one(
        {"user_id": user_id, "regex_pattern": pattern, "applies_to": applies_to, "is_default": False})
    if existing:  # teaching the same merchant again just changes where it goes
        await db[CATEGORIZATION_RULES].update_one(
            {"_id": existing["_id"]}, {"$set": {"category_id": cid, "enabled": True, "priority": max(existing["priority"], LEARNED_PRIORITY)}})
        rule_id, created = existing["_id"], False
    else:
        doc = rule_doc(user_id, f"{LEARNED_PREFIX}{merchant}"[:60], pattern, cid, LEARNED_PRIORITY, applies_to)
        await db[CATEGORIZATION_RULES].insert_one(doc)
        rule_id, created = doc["_id"], True

    changed = await recategorize_all(db, user_id)  # manual choices are skipped by the engine
    await refresh_summaries(db, user_id)
    await db[LEARNING_DISMISSED].delete_many({"user_id": user_id, "merchant": merchant})
    rule = await db[CATEGORIZATION_RULES].find_one({"_id": rule_id})
    return {"rule_id": str(rule_id), "rule_name": rule["rule_name"], "created": created, "recategorized": changed,
            "category_name": cat["name"]}


async def dismiss(db, user_id: ObjectId, merchant: str, category_id: str) -> None:
    try:
        await db[LEARNING_DISMISSED].update_one(
            {"user_id": user_id, "merchant": merchant.strip(), "category_id": oid(category_id, "category id")},
            {"$setOnInsert": {"created_at": utcnow()}}, upsert=True)
    except DuplicateKeyError:  # a concurrent identical dismissal: already what the user wanted
        pass


async def suggestions(db, user_id: ObjectId) -> list[dict]:
    """Merchants you keep moving to the same category, with no rule yet that does it for you."""
    cats = {c["_id"]: c async for c in db[CATEGORIES].find({"user_id": user_id})}
    moves: dict[str, Counter] = defaultdict(Counter)      # merchant -> category -> times you moved it there
    types: dict[tuple, Counter] = defaultdict(Counter)    # (merchant, category) -> debit / credit counts
    async for t in db[RAW_TRANSACTIONS].find({"user_id": user_id, "manual_override": True},
                                             {"normalized_merchant": 1, "category_id": 1, "transaction_type": 1}):
        m = t.get("normalized_merchant")
        if learnable(m) and t.get("category_id") in cats:
            moves[m][t["category_id"]] += 1
            types[(m, t["category_id"])][t.get("transaction_type", "debit")] += 1

    dismissed = {(d["merchant"], d["category_id"]) async for d in db[LEARNING_DISMISSED].find({"user_id": user_id})}
    engine = await load_engine(db, user_id)
    out = []
    for merchant, counter in moves.items():
        ranked = counter.most_common(2)
        (cid, n), runner_up = ranked[0], (ranked[1][1] if len(ranked) > 1 else 0)
        if n < MIN_EVIDENCE or n == runner_up or (merchant, cid) in dismissed:
            continue  # not enough evidence, or you have moved it to two places equally often
        kinds = types[(merchant, cid)]
        applies_to = next(iter(kinds)) if len(kinds) == 1 else "any"
        if engine.categorize(merchant, None, "credit" if applies_to == "credit" else "debit").category_id == str(cid):
            continue  # the rules already put it there
        cat = cats[cid]
        out.append({
            "merchant": merchant, "category_id": str(cid), "category_name": cat["name"], "category_color": cat["color"],
            "evidence": n, "applies_to": applies_to,
            "affected": await similar_count(db, user_id, merchant, cid, applies_to),
        })
    out.sort(key=lambda s: (-s["evidence"], -s["affected"], s["merchant"]))
    return out[:MAX_SUGGESTIONS]


async def uncategorised_merchants(db, user_id: ObjectId) -> list[dict]:
    """Payees whose transactions Tally could not categorise, grouped so one choice sorts them all."""
    groups: dict[str, dict] = {}
    async for t in db[RAW_TRANSACTIONS].find({"user_id": user_id, "needs_review": True},
                                             {"normalized_merchant": 1, "raw_description": 1, "amount": 1, "transaction_type": 1,
                                              "transaction_date": 1}).sort("transaction_date", -1):
        m = t.get("normalized_merchant")
        if not learnable(m):
            continue
        g = groups.setdefault(m, {"merchant": m, "count": 0, "total": 0.0, "sample": t.get("raw_description"), "types": Counter()})
        g["count"] += 1
        g["total"] += t.get("amount") or 0
        g["types"][t.get("transaction_type", "debit")] += 1
    rows = []
    for g in groups.values():
        types = g.pop("types")
        rows.append({**g, "total": round(g["total"], 2), "applies_to": next(iter(types)) if len(types) == 1 else "any"})
    rows.sort(key=lambda r: (-r["count"], -r["total"], r["merchant"]))
    return rows[:MAX_UNCATEGORISED]
