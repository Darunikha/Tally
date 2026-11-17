"""Pure analytics over transaction documents (dicts as stored in raw_transactions).

Definitions used everywhere:
  income   = sum of credit_amount
  expenses = sum of debit_amount
  net      = income - expenses
  avg daily spending = expenses / number of calendar days in the selected period
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta

from app.utils.dates import add_months, month_start, to_day, week_start
from app.utils.money import r2


def pct_change(current: float, previous: float) -> float | None:
    if not previous:
        return None
    return round((current - previous) / abs(previous) * 100, 1)


def totals(txns: list[dict], start: datetime | None = None, end: datetime | None = None) -> dict:
    income = sum(t.get("credit_amount", 0) or 0 for t in txns)
    expenses = sum(t.get("debit_amount", 0) or 0 for t in txns)
    debits = [t for t in txns if t.get("transaction_type") == "debit"]
    upi_debits = [t for t in debits if t.get("payment_method") == "UPI"]
    if start and end:
        days = (to_day(end) - to_day(start)).days + 1
    elif txns:
        dates = [t["transaction_date"] for t in txns]
        days = (max(dates) - min(dates)).days + 1
    else:
        days = 0
    return {
        "total_income": r2(income),
        "total_expenses": r2(expenses),
        "net_balance": r2(income - expenses),
        "transaction_count": len(txns),
        "debit_count": len(debits),
        "credit_count": len(txns) - len(debits),
        "upi_spending": r2(sum(t["debit_amount"] for t in upi_debits)),
        "upi_transaction_count": len(upi_debits),
        "avg_daily_spending": r2(expenses / days) if days > 0 else 0.0,
        "days": days,
        "savings_rate": round((income - expenses) / income * 100, 1) if income else None,
    }


def category_breakdown(txns: list[dict], categories: dict[str, dict], kind: str = "debit") -> list[dict]:
    field = "debit_amount" if kind == "debit" else "credit_amount"
    agg: dict[str, dict] = defaultdict(lambda: {"amount": 0.0, "count": 0})
    for t in txns:
        if t.get("transaction_type") != kind:
            continue
        cid = str(t.get("category_id")) if t.get("category_id") else "none"
        agg[cid]["amount"] += t.get(field, 0) or 0
        agg[cid]["count"] += 1
    total = sum(v["amount"] for v in agg.values())
    out = []
    for cid, v in agg.items():
        cat = categories.get(cid, {})
        out.append({
            "category_id": None if cid == "none" else cid,
            "name": cat.get("name", "Uncategorized"),
            "color": cat.get("color", "#B8B2A7"),
            "amount": r2(v["amount"]),
            "count": v["count"],
            "percentage": round(v["amount"] / total * 100, 1) if total else 0.0,
        })
    return sorted(out, key=lambda x: x["amount"], reverse=True)


def _bucket(d: datetime, granularity: str) -> datetime:
    if granularity == "day":
        return to_day(d)
    if granularity == "week":
        return week_start(d)
    return month_start(d)


def _step(d: datetime, granularity: str) -> datetime:
    if granularity == "day":
        return d + timedelta(days=1)
    if granularity == "week":
        return d + timedelta(days=7)
    return add_months(d, 1)


def _label(d: datetime, granularity: str) -> str:
    if granularity == "month":
        return d.strftime("%b %Y")
    return d.strftime("%d %b")


def time_series(txns: list[dict], granularity: str = "day", start: datetime | None = None,
                end: datetime | None = None) -> list[dict]:
    """Income/expense per bucket, with empty buckets filled so charts have continuous axes."""
    if not txns and not (start and end):
        return []
    dates = [t["transaction_date"] for t in txns]
    start = start or min(dates)
    end = end or max(dates)
    agg: dict[datetime, dict] = defaultdict(lambda: {"income": 0.0, "expense": 0.0, "count": 0})
    for t in txns:
        b = _bucket(t["transaction_date"], granularity)
        agg[b]["income"] += t.get("credit_amount", 0) or 0
        agg[b]["expense"] += t.get("debit_amount", 0) or 0
        agg[b]["count"] += 1
    out = []
    cur, last = _bucket(start, granularity), _bucket(end, granularity)
    guard = 0
    while cur <= last and guard < 2000:
        v = agg.get(cur, {"income": 0.0, "expense": 0.0, "count": 0})
        out.append({"period": cur.strftime("%Y-%m-%d"), "label": _label(cur, granularity),
                    "income": r2(v["income"]), "expense": r2(v["expense"]), "net": r2(v["income"] - v["expense"]),
                    "count": v["count"]})
        cur = _step(cur, granularity)
        guard += 1
    return out


def merchant_breakdown(txns: list[dict], limit: int | None = 10, upi_only: bool = False,
                       categories: dict[str, dict] | None = None) -> list[dict]:
    agg: dict[str, dict] = {}
    for t in txns:
        if t.get("transaction_type") != "debit":
            continue
        if upi_only and t.get("payment_method") != "UPI":
            continue
        m = t.get("normalized_merchant") or "Unknown"
        a = agg.setdefault(m, {"merchant": m, "total": 0.0, "count": 0, "upi_ids": set(), "last_date": None,
                               "category_ids": defaultdict(int)})
        a["total"] += t["debit_amount"]
        a["count"] += 1
        if t.get("upi_id"):
            a["upi_ids"].add(t["upi_id"])
        if a["last_date"] is None or t["transaction_date"] > a["last_date"]:
            a["last_date"] = t["transaction_date"]
        if t.get("category_id"):
            a["category_ids"][str(t["category_id"])] += 1
    out = []
    for a in agg.values():
        top_cat = max(a["category_ids"], key=a["category_ids"].get) if a["category_ids"] else None
        cat = (categories or {}).get(top_cat or "", {})
        out.append({
            "merchant": a["merchant"],
            "total": r2(a["total"]),
            "count": a["count"],
            "average": r2(a["total"] / a["count"]),
            "upi_ids": sorted(a["upi_ids"])[:5],
            "last_date": a["last_date"].strftime("%Y-%m-%d") if a["last_date"] else None,
            "category": cat.get("name"),
            "category_color": cat.get("color"),
        })
    out.sort(key=lambda x: x["total"], reverse=True)
    return out[:limit] if limit else out


def weekday_breakdown(txns: list[dict]) -> list[dict]:
    names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    totals_ = [0.0] * 7
    counts = [0] * 7
    for t in txns:
        if t.get("transaction_type") == "debit":
            wd = t["transaction_date"].weekday()
            totals_[wd] += t["debit_amount"]
            counts[wd] += 1
    return [{"day": names[i], "amount": r2(totals_[i]), "count": counts[i]} for i in range(7)]


AMOUNT_BUCKETS = [(0, 100), (100, 500), (500, 1000), (1000, 5000), (5000, 10000), (10000, 50000), (50000, None)]


def amount_distribution(txns: list[dict]) -> list[dict]:
    out = []
    debits = [t["debit_amount"] for t in txns if t.get("transaction_type") == "debit"]
    for lo, hi in AMOUNT_BUCKETS:
        sel = [a for a in debits if a >= lo and (hi is None or a < hi)]
        label = f"₹{lo:,}+" if hi is None else f"₹{lo:,}–{hi:,}"
        out.append({"range": label, "count": len(sel), "amount": r2(sum(sel))})
    return out


def payment_method_breakdown(txns: list[dict]) -> list[dict]:
    agg: dict[str, dict] = defaultdict(lambda: {"amount": 0.0, "count": 0})
    for t in txns:
        if t.get("transaction_type") == "debit":
            agg[t.get("payment_method") or "Other"]["amount"] += t["debit_amount"]
            agg[t.get("payment_method") or "Other"]["count"] += 1
    return sorted(({"method": k, "amount": r2(v["amount"]), "count": v["count"]} for k, v in agg.items()),
                  key=lambda x: x["amount"], reverse=True)
