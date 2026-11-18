"""Monthly budgets: one per category plus an optional overall budget."""
from datetime import datetime

from fastapi import APIRouter, Depends, Query

from app.analytics.budgets import budget_status, history_average, history_window, spend_by_category
from app.api.deps import current_user, db_dep
from app.core.errors import AppError
from app.database.mongo import BUDGETS, CATEGORIES
from app.models.documents import budget_doc
from app.schemas.requests import BudgetUpsert
from app.services.query import Period, build_filter, category_map, load_transactions, oid
from app.utils.dates import month_end, today_ist, utcnow
from app.utils.money import r2

router = APIRouter(tags=["budgets"])


async def _debits(db, user_id, start: datetime, end: datetime) -> list[dict]:
    return await load_transactions(db, build_filter(user_id, Period(start, end), transaction_type="debit"))


@router.get("/budgets/status")
async def budgets_status(month: int | None = Query(None, ge=1, le=12), year: int | None = Query(None, ge=1990, le=2100),
                         user=Depends(current_user), db=Depends(db_dep)):
    """Progress of every budget for one calendar month (defaults to the current month in IST)."""
    today = today_ist()
    if (month is None) != (year is None):
        raise AppError("Provide both month and year", 400, "invalid_date")
    start = datetime(year or today.year, month or today.month, 1)
    uid = user["_id"]

    this_month = await _debits(db, uid, start, month_end(start))
    h_start, h_end = history_window(start)
    past = await _debits(db, uid, h_start, h_end)

    spend, total = spend_by_category(this_month)
    hist, hist_total = history_average(past)
    budgets = await db[BUDGETS].find({"user_id": uid}).to_list(None)
    return budget_status(budgets, spend, total, await category_map(db, uid), start, today, hist, hist_total)


@router.put("/budgets")
async def set_budget(body: BudgetUpsert, user=Depends(current_user), db=Depends(db_dep)):
    """Create or replace the budget for a category (category_id null = overall)."""
    uid = user["_id"]
    cid = None
    if body.category_id:
        cid = oid(body.category_id, "category id")
        if not await db[CATEGORIES].find_one({"_id": cid, "user_id": uid}):
            raise AppError("Category not found", 404, "not_found")
    limit = r2(body.monthly_limit)
    existing = await db[BUDGETS].find_one({"user_id": uid, "category_id": cid})
    if existing:
        await db[BUDGETS].update_one({"_id": existing["_id"]}, {"$set": {
            "monthly_limit": limit, "alert_threshold": body.alert_threshold, "updated_at": utcnow()}})
        doc = await db[BUDGETS].find_one({"_id": existing["_id"]})
    else:
        doc = budget_doc(uid, cid, limit, body.alert_threshold)
        await db[BUDGETS].insert_one(doc)
    return {"id": str(doc["_id"]), "category_id": str(cid) if cid else None,
            "monthly_limit": doc["monthly_limit"], "alert_threshold": doc["alert_threshold"]}


@router.delete("/budgets/{budget_id}")
async def delete_budget(budget_id: str, user=Depends(current_user), db=Depends(db_dep)):
    res = await db[BUDGETS].delete_one({"_id": oid(budget_id, "budget id"), "user_id": user["_id"]})
    if not res.deleted_count:
        raise AppError("Budget not found", 404, "not_found")
    return {"ok": True}
