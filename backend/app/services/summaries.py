"""SpendingSummaries: cached monthly roll-ups, always rebuildable from raw_transactions."""
from __future__ import annotations

from collections import defaultdict

from bson import ObjectId
from pymongo import UpdateOne

from app.analytics.calculations import category_breakdown, merchant_breakdown, totals
from app.database.mongo import SPENDING_SUMMARIES
from app.services.query import category_map, load_transactions
from app.utils.dates import month_end, month_start, utcnow


async def refresh_summaries(db, user_id: ObjectId) -> int:
    """Recompute every monthly summary for a user and drop summaries for months with no data."""
    txns = await load_transactions(db, {"user_id": user_id})
    cats = await category_map(db, user_id)
    by_month: dict = defaultdict(list)
    for t in txns:
        by_month[month_start(t["transaction_date"])].append(t)

    ops = []
    for m, items in by_month.items():
        end = month_end(m)
        tot = totals(items, m, end)
        ops.append(UpdateOne(
            {"user_id": user_id, "period": "month", "period_start": m},
            {"$set": {
                "period_end": end,
                "total_income": tot["total_income"],
                "total_expenses": tot["total_expenses"],
                "net_balance": tot["net_balance"],
                "transaction_count": tot["transaction_count"],
                "upi_spending": tot["upi_spending"],
                "category_breakdown": [{k: c[k] for k in ("category_id", "name", "amount", "count")}
                                       for c in category_breakdown(items, cats)],
                "merchant_breakdown": [{k: x[k] for k in ("merchant", "total", "count")}
                                       for x in merchant_breakdown(items, limit=15)],
                "updated_at": utcnow(),
            }},
            upsert=True,
        ))
    if ops:
        await db[SPENDING_SUMMARIES].bulk_write(ops, ordered=False)
    await db[SPENDING_SUMMARIES].delete_many(
        {"user_id": user_id, "period": "month", "period_start": {"$nin": list(by_month.keys())}}
    )
    return len(ops)
