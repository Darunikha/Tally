"""Budget progress: pure functions over a month's debit transactions (no database access)."""
from __future__ import annotations

import math
from collections import defaultdict
from datetime import date, datetime, timedelta

from app.utils.dates import add_months, month_end
from app.utils.money import r2

MIN_DAYS_FOR_PROJECTION = 7  # earlier in the month a projection is mostly noise


def spend_by_category(debits: list[dict]) -> tuple[dict[str, float], float]:
    """Per-category and total spend from debit transactions."""
    by_cat: dict[str, float] = defaultdict(float)
    total = 0.0
    for t in debits:
        amt = t.get("debit_amount") or 0
        total += amt
        by_cat[str(t["category_id"]) if t.get("category_id") else "none"] += amt
    return dict(by_cat), r2(total)


def history_average(debits: list[dict]) -> tuple[dict[str, float], float]:
    """Average monthly spend per category (and overall) across the months that actually have spending."""
    months: dict[tuple[int, int], list[dict]] = defaultdict(list)
    for t in debits:
        d = t["transaction_date"]
        months[(d.year, d.month)].append(t)
    if not months:
        return {}, 0.0
    cat_sum: dict[str, float] = defaultdict(float)
    total = 0.0
    for rows in months.values():
        by_cat, tot = spend_by_category(rows)
        total += tot
        for k, v in by_cat.items():
            cat_sum[k] += v
    n = len(months)
    return {k: v / n for k, v in cat_sum.items()}, total / n


def _round_up(value: float, step: int) -> int:
    return int(math.ceil(value / step) * step) if value > 0 else 0


def _status(spent: float, limit: float, threshold: int) -> str:
    if spent > limit:
        return "over"
    if spent / limit * 100 >= threshold:
        return "warning"
    return "ok"


def _row(budget: dict, spent: float, cat: dict | None, month: datetime, today: date) -> dict:
    limit = float(budget["monthly_limit"])
    threshold = int(budget.get("alert_threshold", 80))
    dim = month_end(month).day
    first, last = month.date(), month_end(month).date()
    in_month = first <= today <= last
    elapsed = today.day if in_month else (dim if today > last else 0)
    days_left = dim - today.day if in_month else 0
    remaining = limit - spent

    projected = None
    if in_month and elapsed >= MIN_DAYS_FOR_PROJECTION and spent > 0:
        projected = r2(spent / elapsed * dim)

    return {
        "id": str(budget["_id"]),
        "category_id": str(budget["category_id"]) if budget.get("category_id") else None,
        "name": (cat or {}).get("name", "Deleted category") if budget.get("category_id") else "Overall spending",
        "color": (cat or {}).get("color", "#2F7D55") if budget.get("category_id") else "#2F7D55",
        "monthly_limit": r2(limit),
        "alert_threshold": threshold,
        "spent": r2(spent),
        "remaining": r2(remaining),
        "percent": round(spent / limit * 100, 1),
        "status": _status(spent, limit, threshold),
        "projected": projected,
        "projected_over": projected is not None and projected > limit,
        "daily_allowance": r2(remaining / days_left) if days_left > 0 and remaining > 0 else None,
    }


def budget_status(budgets: list[dict], spend: dict[str, float], total_spend: float, categories: dict[str, dict],
                  month: datetime, today: date, history: dict[str, float], history_total: float) -> dict:
    """Progress for every budget in `month`, plus categories with spending but no budget."""
    overall = None
    rows = []
    budgeted = set()
    for b in budgets:
        cid = str(b["category_id"]) if b.get("category_id") else None
        if cid is None:
            overall = _row(b, total_spend, None, month, today)
            continue
        budgeted.add(cid)
        rows.append(_row(b, spend.get(cid, 0.0), categories.get(cid), month, today))
    rows.sort(key=lambda r: r["percent"], reverse=True)

    unbudgeted = []
    for cid, amount in spend.items():
        if cid in budgeted or cid == "none" or amount <= 0:
            continue
        cat = categories.get(cid, {})
        unbudgeted.append({
            "category_id": cid, "name": cat.get("name", "Uncategorized"), "color": cat.get("color", "#B8B2A7"),
            "spent": r2(amount), "suggested_limit": _round_up(max(history.get(cid, 0.0), amount), 100),
        })
    unbudgeted.sort(key=lambda r: r["spent"], reverse=True)

    everything = ([overall] if overall else []) + rows
    dim = month_end(month).day
    in_month = month.date() <= today <= month_end(month).date()
    return {
        "month": {
            "year": month.year, "month": month.month, "label": month.strftime("%B %Y"),
            "is_current": in_month, "days_in_month": dim, "days_left": dim - today.day if in_month else 0,
        },
        "overall": overall,
        "budgets": rows,
        "unbudgeted": unbudgeted[:8],
        "suggested_overall": _round_up(history_total, 500) or None,
        "total_spent": r2(total_spend),
        "summary": {
            "over": sum(1 for r in everything if r["status"] == "over"),
            "warning": sum(1 for r in everything if r["status"] == "warning"),
            "ok": sum(1 for r in everything if r["status"] == "ok"),
        },
    }


def history_window(month: datetime, months: int = 3) -> tuple[datetime, datetime]:
    """The `months` full calendar months before `month` (start, inclusive end)."""
    return add_months(month, -months), month - timedelta(days=1)
