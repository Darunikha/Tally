"""Dashboard, analytics, insights and UPI endpoints - all computed live from raw_transactions."""
from fastapi import APIRouter, Depends, Query

from app.analytics import calculations as calc
from app.analytics.insights import generate_insights
from app.api.deps import current_user, db_dep
from app.database.mongo import RAW_TRANSACTIONS, SPENDING_SUMMARIES, STATEMENT_UPLOADS
from app.services.query import (Period, build_filter, category_map, excluded_category_ids, load_transactions,
                                resolve_period)
from app.utils.dates import add_months, month_start, today_ist, to_day
from app.utils.serialize import to_json

router = APIRouter(tags=["analytics"])


class Scope:
    """Common scope: explicit range, or month/year, optionally narrowed to one statement."""

    def __init__(self, start: str | None = None, end: str | None = None,
                 month: int | None = Query(None, ge=1, le=12), year: int | None = Query(None, ge=1990, le=2100),
                 upload_id: str | None = None, account_id: str | None = None):
        self.period = resolve_period(start, end, month, year)
        self.upload_id = upload_id
        self.account_id = account_id


async def _scoped(db, user, scope: Scope, period: Period | None = None):
    p = period if period is not None else scope.period
    excluded = await excluded_category_ids(db, user["_id"])
    return await load_transactions(db, build_filter(user["_id"], p, upload_id=scope.upload_id, account_id=scope.account_id, exclude_category_ids=excluded))


def _effective_period(scope: Scope, txns: list[dict]) -> Period:
    """'All time' -> span of the data, so averages use real day counts."""
    if scope.period.start and scope.period.end:
        return scope.period
    if not txns:
        return scope.period
    s = scope.period.start or min(t["transaction_date"] for t in txns)
    e = scope.period.end or max(t["transaction_date"] for t in txns)
    return Period(s, e)


def _label(p: Period) -> str:
    if p.start and p.end and p.start.day == 1 and p.start.month == p.end.month and p.start.year == p.end.year:
        return f"in {p.start:%B %Y}"
    return "in this period"


@router.get("/analytics/periods")
async def available_periods(user=Depends(current_user), db=Depends(db_dep)):
    """Months that have data (for month/year pickers) + the latest month."""
    sums = await db[SPENDING_SUMMARIES].find({"user_id": user["_id"], "period": "month"},
                                             {"period_start": 1, "transaction_count": 1}).sort("period_start", -1).to_list(None)
    months = [{"year": s["period_start"].year, "month": s["period_start"].month,
               "label": s["period_start"].strftime("%B %Y"), "transaction_count": s["transaction_count"]} for s in sums]
    return {"months": months, "latest": months[0] if months else None,
            "today": today_ist().isoformat()}


@router.get("/analytics/dashboard")
async def dashboard(scope: Scope = Depends(), user=Depends(current_user), db=Depends(db_dep)):
    txns = await _scoped(db, user, scope)
    period = _effective_period(scope, txns)
    prev_period = period.previous()
    prev = await _scoped(db, user, scope, prev_period) if prev_period.start else []
    cats = await category_map(db, user["_id"])
    cur_tot = calc.totals(txns, period.start, period.end)
    prev_tot = calc.totals(prev, prev_period.start, prev_period.end) if prev else None

    def ch(key):
        return calc.pct_change(cur_tot[key], prev_tot[key]) if prev_tot else None

    # monthly income vs expense: 6 months ending at the period end (or latest data)
    anchor = period.end or (max((t["transaction_date"] for t in txns), default=None)) or to_day(today_ist())
    six_start = add_months(month_start(anchor), -5)
    excluded = await excluded_category_ids(db, user["_id"])
    six = await load_transactions(db, build_filter(user["_id"], Period(six_start, anchor), upload_id=scope.upload_id, account_id=scope.account_id,
                                                   exclude_category_ids=excluded))
    left_out = await db[RAW_TRANSACTIONS].count_documents(
        {**build_filter(user["_id"], scope.period, upload_id=scope.upload_id, account_id=scope.account_id), "category_id": {"$in": excluded}}) if excluded else 0
    granularity = "day" if period.days and period.days <= 62 else "week" if period.days <= 200 else "month"
    recent = await (db[RAW_TRANSACTIONS].find(build_filter(user["_id"], scope.period, upload_id=scope.upload_id, account_id=scope.account_id),
                                              {"raw_bank_fields": 0})
                    .sort([("transaction_date", -1), ("_id", -1)]).limit(6).to_list(None))
    for r in recent:
        c = cats.get(str(r.get("category_id")), {})
        r["category_name"], r["category_color"] = c.get("name"), c.get("color")
    insights = generate_insights(txns, prev, cats, _label(period), period.start, period.end)
    return {
        "period": to_json({"start": period.start, "end": period.end}) if period.start else None,
        "previous_period": to_json({"start": prev_period.start, "end": prev_period.end}) if prev_period.start else None,
        "totals": cur_tot,
        "changes": {k: ch(k) for k in ("total_income", "total_expenses", "net_balance", "transaction_count",
                                        "upi_spending", "avg_daily_spending")},
        "category_breakdown": calc.category_breakdown(txns, cats),
        "daily_trend": calc.time_series(txns, granularity, period.start, period.end),
        "trend_granularity": granularity,
        "monthly": calc.time_series(six, "month", six_start, anchor),
        "top_merchants": calc.merchant_breakdown(txns, limit=6, categories=cats),
        "recent_transactions": to_json(recent),
        "insights": insights,
        "excluded_payments": {"count": left_out},
    }


@router.get("/analytics/overview")
async def analytics_overview(scope: Scope = Depends(), granularity: str = Query("auto", pattern="^(auto|day|week|month)$"),
                             user=Depends(current_user), db=Depends(db_dep)):
    txns = await _scoped(db, user, scope)
    period = _effective_period(scope, txns)
    prev_period = period.previous()
    prev = await _scoped(db, user, scope, prev_period) if prev_period.start else []
    cats = await category_map(db, user["_id"])
    if granularity == "auto":
        granularity = "day" if period.days and period.days <= 62 else "week" if period.days <= 200 else "month"

    prev_cats = {c["name"]: c["amount"] for c in calc.category_breakdown(prev, cats)}
    cat_rows = calc.category_breakdown(txns, cats)
    for c in cat_rows:
        c["previous_amount"] = prev_cats.get(c["name"], 0.0)
        c["change"] = calc.pct_change(c["amount"], c["previous_amount"])
    cur_tot = calc.totals(txns, period.start, period.end)
    prev_tot = calc.totals(prev, prev_period.start, prev_period.end) if prev else None
    return {
        "period": to_json({"start": period.start, "end": period.end}) if period.start else None,
        "previous_period": to_json({"start": prev_period.start, "end": prev_period.end}) if prev_period.start else None,
        "totals": cur_tot,
        "previous_totals": prev_tot,
        "granularity": granularity,
        "trend": calc.time_series(txns, granularity, period.start, period.end),
        "daily": calc.time_series(txns, "day", period.start, period.end) if period.days <= 400 else [],
        "weekly": calc.time_series(txns, "week", period.start, period.end),
        "monthly": calc.time_series(txns, "month", period.start, period.end),
        "categories": cat_rows,
        "income_categories": calc.category_breakdown(txns, cats, kind="credit"),
        "merchants": calc.merchant_breakdown(txns, limit=15, categories=cats),
        "weekday": calc.weekday_breakdown(txns),
        "distribution": calc.amount_distribution(txns),
        "payment_methods": calc.payment_method_breakdown(txns),
    }


@router.get("/analytics/insights")
async def insights(scope: Scope = Depends(), user=Depends(current_user), db=Depends(db_dep)):
    txns = await _scoped(db, user, scope)
    period = _effective_period(scope, txns)
    prev_period = period.previous()
    prev = await _scoped(db, user, scope, prev_period) if prev_period.start else []
    return generate_insights(txns, prev, await category_map(db, user["_id"]), _label(period), period.start, period.end)


@router.get("/analytics/statements-filter")
async def statements_for_filter(user=Depends(current_user), db=Depends(db_dep)):
    ups = await db[STATEMENT_UPLOADS].find({"user_id": user["_id"], "processing_status": "completed"},
                                           {"file_name": 1, "bank_name": 1, "date_range": 1, "account_id": 1, "account_type": 1}).sort("upload_date", -1).to_list(None)
    return to_json(ups)


@router.get("/upi/summary")
async def upi_summary(scope: Scope = Depends(), user=Depends(current_user), db=Depends(db_dep)):
    txns = await _scoped(db, user, scope)
    period = _effective_period(scope, txns)
    cats = await category_map(db, user["_id"])
    upi = [t for t in txns if t.get("payment_method") == "UPI"]
    upi_debits = [t for t in upi if t["transaction_type"] == "debit"]
    total_debits = sum(t["debit_amount"] for t in txns)
    merchants = calc.merchant_breakdown(upi, limit=None, upi_only=True, categories=cats)
    p2m = [t for t in upi_debits if t.get("upi_flow") == "P2M"]
    p2a = [t for t in upi_debits if t.get("upi_flow") == "P2A"]
    by_freq = sorted(merchants, key=lambda m: (m["count"], m["total"]), reverse=True)[:10]
    return {
        "totals": {
            "upi_spent": round(sum(t["debit_amount"] for t in upi_debits), 2),
            "upi_received": round(sum(t["credit_amount"] for t in upi if t["transaction_type"] == "credit"), 2),
            "upi_debit_count": len(upi_debits),
            "upi_credit_count": len(upi) - len(upi_debits),
            "share_of_spending": round(sum(t["debit_amount"] for t in upi_debits) / total_debits * 100, 1) if total_debits else 0,
            "unique_merchants": len(merchants),
            "average_ticket": round(sum(t["debit_amount"] for t in upi_debits) / len(upi_debits), 2) if upi_debits else 0,
            "p2m_amount": round(sum(t["debit_amount"] for t in p2m), 2),
            "p2a_amount": round(sum(t["debit_amount"] for t in p2a), 2),
            "unknown_flow_amount": round(sum(t["debit_amount"] for t in upi_debits if not t.get("upi_flow")), 2),
        },
        "top_by_amount": merchants[:10],
        "top_by_frequency": by_freq,
        "merchants": merchants,
        "trend": calc.time_series(upi_debits, "day" if period.days and period.days <= 62 else "week",
                                  period.start, period.end),
        "categories": calc.category_breakdown(upi_debits, cats),
    }
