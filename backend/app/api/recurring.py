"""Recurring payments: subscriptions, bills, rent and SIPs detected from the user's own history."""
from fastapi import APIRouter, Depends

from app.analytics.recurring import detect_recurring, summarize
from app.api.deps import current_user, db_dep
from app.database.mongo import RAW_TRANSACTIONS, RECURRING_IGNORED
from app.schemas.requests import RecurringIgnore
from app.services.query import build_filter, category_map, excluded_category_ids, load_transactions
from app.utils.dates import utcnow

router = APIRouter(tags=["recurring"])


@router.get("/recurring")
async def list_recurring(user=Depends(current_user), db=Depends(db_dep)):
    """Everything judged as of the newest transaction in the user's data, so statements that are a few months
    old don't make every subscription look cancelled."""
    uid = user["_id"]
    latest = await db[RAW_TRANSACTIONS].find_one({"user_id": uid}, {"transaction_date": 1},
                                                 sort=[("transaction_date", -1)])
    if latest is None:
        return {"as_of": None, "items": [], "summary": summarize([]), "ignored_count": 0}
    as_of = latest["transaction_date"]

    cats = await category_map(db, uid)
    excluded = await excluded_category_ids(db, uid)
    debits = await load_transactions(db, build_filter(uid, None, transaction_type="debit", exclude_category_ids=excluded))
    # cash withdrawals and payments to your own credit cards are money moving around, not a bill you owe
    debits = [t for t in debits if t.get("payment_method") != "ATM/Cash"
              and not cats.get(str(t.get("category_id")), {}).get("excluded_from_totals")]

    ignored = {d["merchant"] async for d in db[RECURRING_IGNORED].find({"user_id": uid}, {"merchant": 1})}
    items = detect_recurring(debits, cats, as_of)
    for i in items:
        i["ignored"] = i["merchant"] in ignored
    return {"as_of": as_of.strftime("%Y-%m-%d"), "items": items,
            "summary": summarize([i for i in items if not i["ignored"]]),
            "ignored_count": sum(1 for i in items if i["ignored"])}


@router.put("/recurring/ignored")
async def set_ignored(body: RecurringIgnore, user=Depends(current_user), db=Depends(db_dep)):
    """Mark a merchant as 'not recurring' (hides it and removes it from the totals), or bring it back."""
    key = {"user_id": user["_id"], "merchant": body.merchant.strip()}
    if body.ignored:
        await db[RECURRING_IGNORED].update_one(key, {"$setOnInsert": {"created_at": utcnow()}}, upsert=True)
    else:
        await db[RECURRING_IGNORED].delete_one(key)
    return {"merchant": key["merchant"], "ignored": body.ignored}
