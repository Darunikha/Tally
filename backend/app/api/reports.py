"""Downloadable reports. The numbers come from the same functions as the dashboard, so they always agree."""
from fastapi import APIRouter, Depends, Response

from app.analytics import calculations as calc
from app.api.analytics import Scope, _effective_period, _scoped
from app.api.budgets import compute_budget_status
from app.api.deps import current_user, db_dep
from app.core.ratelimit import limit as rate_limit
from app.database.mongo import ACCOUNTS, RAW_TRANSACTIONS, STATEMENT_UPLOADS
from app.services.query import Period, build_filter, category_map, excluded_category_ids, oid
from app.services.report_pdf import build_summary_pdf
from app.utils.dates import month_end, now_ist

router = APIRouter(tags=["reports"])


def period_label(p: Period, scoped: bool) -> str:
    if not (p.start and p.end):
        return "All time"
    if scoped and p.start.day == 1 and p.end == month_end(p.start):
        return f"{p.start:%B %Y}"
    if scoped and (p.start.month, p.start.day, p.end.month, p.end.day) == (1, 1, 12, 31) and p.start.year == p.end.year:
        return f"Year {p.start.year}"
    span = f"{p.start:%d %b %Y} to {p.end:%d %b %Y}"
    return span if scoped else f"All time ({span})"


def _file_token(p: Period, scoped: bool) -> str:
    if not scoped or not (p.start and p.end):
        return "all-time"
    if p.start.day == 1 and p.end == month_end(p.start):
        return f"{p.start:%Y-%m}"
    if (p.start.month, p.start.day, p.end.month, p.end.day) == (1, 1, 12, 31):
        return f"{p.start.year}"
    return f"{p.start:%Y-%m-%d}_to_{p.end:%Y-%m-%d}"


@router.get("/reports/summary.pdf")
async def summary_report(scope: Scope = Depends(), user=Depends(current_user), db=Depends(db_dep)):
    uid = user["_id"]
    await rate_limit(db, "export:report", str(uid), 30, 3600)
    txns = await _scoped(db, user, scope)
    period = _effective_period(scope, txns)
    scoped = bool(scope.period.start and scope.period.end)
    prev_period = period.previous()
    prev = await _scoped(db, user, scope, prev_period) if prev_period.start else []
    cats = await category_map(db, uid)
    totals = calc.totals(txns, period.start, period.end)
    prev_totals = calc.totals(prev, prev_period.start, prev_period.end) if prev else None
    changes = {k: calc.pct_change(totals[k], prev_totals[k]) for k in ("total_income", "total_expenses")} if prev_totals else None

    one_month = bool(period.start and period.end and period.start.day == 1 and period.end == month_end(period.start))
    # budgets cover all spending, so they would sit oddly beside figures narrowed to one account or statement
    whole_picture = not scope.account_id and not scope.upload_id
    budgets = await compute_budget_status(db, uid, period.start.month, period.start.year) if one_month and scoped and whole_picture else None

    excluded = await excluded_category_ids(db, uid)
    left_out = await db[RAW_TRANSACTIONS].count_documents(
        {**build_filter(uid, scope.period, upload_id=scope.upload_id, account_id=scope.account_id), "category_id": {"$in": excluded}}) if excluded else 0
    statement = None
    if scope.upload_id:
        up = await db[STATEMENT_UPLOADS].find_one({"_id": oid(scope.upload_id, "statement id"), "user_id": uid}, {"file_name": 1})
        statement = (up or {}).get("file_name")

    account = None
    if scope.account_id == "none":
        account = "Not filed under an account"
    elif scope.account_id:
        acc = await db[ACCOUNTS].find_one({"_id": oid(scope.account_id, "account id"), "user_id": uid}, {"name": 1})
        account = (acc or {}).get("name")

    pdf = build_summary_pdf({
        "period_label": period_label(period, scoped), "generated": f"{now_ist():%d %b %Y, %H:%M} IST", "statement": statement, "account": account,
        "totals": totals, "changes": changes, "categories": calc.category_breakdown(txns, cats),
        "merchants": calc.merchant_breakdown(txns, limit=10, categories=cats),
        "monthly": calc.time_series(txns, "month", period.start, period.end) if txns else [],
        "budgets": budgets, "excluded_payments": left_out,
    })
    return Response(content=pdf, media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="tally-report-{_file_token(period, scoped)}.pdf"'})
