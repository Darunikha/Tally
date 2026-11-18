"""Recurring payments (subscriptions, bills, rent, SIPs) found in the user's own debit history.

Pure functions over transaction dicts - no database access. A payment is recurring when the same merchant
is paid on a steady cadence (weekly, monthly, quarterly or yearly) and for a steady amount. "Steady" is
deliberately strict so that frequent but irregular spending (food delivery, cabs, shopping) is not reported;
the user can still dismiss anything that slips through.
"""
from __future__ import annotations

import calendar
import statistics
from collections import defaultdict
from datetime import datetime, timedelta

from app.utils.money import r2

# name, nominal days, accepted interval band (days), grace days before it counts as stopped, min occurrences
CADENCES = [
    ("weekly", 7, (6, 8), 3, 6),
    ("monthly", 30, (26, 35), 7, 3),
    ("quarterly", 91, (84, 98), 14, 3),
    ("yearly", 365, (350, 380), 30, 2),
]
MONTHLY_FACTOR = {"weekly": 52 / 12, "monthly": 1.0, "quarterly": 1 / 3, "yearly": 1 / 12}

FIXED_TOLERANCE = 0.03      # amounts within 3% of each other are "the same price"
VARIABLE_TOLERANCE = 0.35   # a bill like electricity swings, but not wildly
MIN_REGULAR_SHARE = 0.6     # share of gaps between payments that must match the cadence
MIN_REGULAR_SHARE_VARIABLE = 0.8
BILL_CATEGORIES = {"Bills & Utilities", "Rent"}
UPCOMING_DAYS = 30


def add_months(d: datetime, months: int, day: int | None = None) -> datetime:
    """Same day-of-month `months` later, clamped to the month's length (31 Jan + 1 month = 28/29 Feb)."""
    idx = d.year * 12 + (d.month - 1) + months
    year, month = idx // 12, idx % 12 + 1
    return datetime(year, month, min(day or d.day, calendar.monthrange(year, month)[1]))


def _cadence(median_gap: float):
    return next((c for c in CADENCES if c[2][0] <= median_gap <= c[2][1]), None)


def _by_date(txns: list[dict]) -> list[tuple[datetime, float]]:
    """One (date, amount) per day: several payments on the same day count as one occurrence."""
    days: dict[datetime, float] = defaultdict(float)
    for t in txns:
        days[t["transaction_date"]] += t["debit_amount"]
    return sorted(days.items())


def _within(amount: float, ref: float, tol: float) -> bool:
    return abs(amount - ref) <= tol * ref


def _next_expected(dates: list[datetime], cadence: str) -> datetime:
    last = dates[-1]
    if cadence == "weekly":
        return last + timedelta(days=7)
    anchor = int(statistics.median(d.day for d in dates))  # paid "around the 5th" even if one month slipped a day
    step = {"monthly": 1, "quarterly": 3, "yearly": 12}[cadence]
    return add_months(last, step, anchor)


def _evaluate(series: list[tuple[datetime, float]], allow_variable: bool,
              min_regular: float = MIN_REGULAR_SHARE) -> dict | None:
    """Cadence and amount pattern of a (date, amount) series, or None if it is not recurring."""
    if len(series) < 2:
        return None
    dates = [d for d, _ in series]
    amounts = [a for _, a in series]
    gaps = [(b - a).days for a, b in zip(dates, dates[1:])]
    cadence = _cadence(statistics.median(gaps))
    if cadence is None:
        return None
    name, _nominal, (lo, hi), grace, min_occ = cadence
    if len(series) < min_occ:
        return None
    regular = sum(1 for g in gaps if lo <= g <= hi) / len(gaps)
    if regular < min_regular:
        return None

    med = statistics.median(amounts)
    before = statistics.median(amounts[:-1])
    price_change = None
    if (all(_within(a, before, FIXED_TOLERANCE) for a in amounts[:-1]) and not _within(amounts[-1], before, FIXED_TOLERANCE)
            and 0.5 * before <= amounts[-1] <= 2 * before):
        kind = "fixed"  # the same price until the latest payment, which differs: a price change
        price_change = {"from": r2(before), "to": r2(amounts[-1]), "percent": round((amounts[-1] - before) / before * 100, 1)}
    elif sum(_within(a, med, FIXED_TOLERANCE) for a in amounts) / len(amounts) >= 0.75 and all(
            _within(a, med, VARIABLE_TOLERANCE) for a in amounts):
        kind = "fixed"
    elif (allow_variable and name != "weekly" and regular >= MIN_REGULAR_SHARE_VARIABLE
          and sum(_within(a, med, VARIABLE_TOLERANCE) for a in amounts) / len(amounts) >= 0.75):
        kind = "variable"
    else:
        return None

    amount = amounts[-1] if kind == "fixed" else med
    return {
        "cadence": name, "amount_kind": kind, "amount": r2(amount), "last_amount": r2(amounts[-1]),
        "occurrences": len(series), "first_date": dates[0], "last_date": dates[-1],
        "next_expected": _next_expected(dates, name), "grace_days": grace, "price_change": price_change,
        "history": [{"date": d.strftime("%Y-%m-%d"), "amount": r2(a)} for d, a in series[-6:]],
    }


def _amount_clusters(txns: list[dict], min_occ: int) -> list[list[dict]]:
    """Payments of (almost) the same amount, largest group first - finds a fixed subscription hiding among
    a merchant's other purchases (e.g. a monthly app subscription next to one-off app purchases)."""
    remaining = sorted(txns, key=lambda t: t["debit_amount"])
    clusters = []
    for ref in sorted({t["debit_amount"] for t in remaining}, key=lambda a: -sum(
            _within(t["debit_amount"], a, FIXED_TOLERANCE) for t in remaining)):
        group = [t for t in remaining if _within(t["debit_amount"], ref, FIXED_TOLERANCE)]
        if len(group) >= min_occ:
            clusters.append(group)
            ids = {id(t) for t in group}
            remaining = [t for t in remaining if id(t) not in ids]
    return clusters


def _group(category: str | None) -> str:
    return "subscription" if category == "Subscriptions" else "bill" if category in BILL_CATEGORIES else "other"


def _finish(found: dict, merchant: str, cat: dict, as_of: datetime) -> dict:
    due = (found["next_expected"] - as_of).days
    monthly = found["amount"] * MONTHLY_FACTOR[found["cadence"]]
    return {
        "merchant": merchant,
        "category": cat.get("name"), "category_color": cat.get("color"), "group": _group(cat.get("name")),
        "cadence": found["cadence"], "amount_kind": found["amount_kind"], "amount": found["amount"],
        "last_amount": found["last_amount"], "occurrences": found["occurrences"],
        "first_date": found["first_date"].strftime("%Y-%m-%d"), "last_date": found["last_date"].strftime("%Y-%m-%d"),
        "next_expected": found["next_expected"].strftime("%Y-%m-%d"), "due_in_days": due,
        "status": "active" if due >= -found["grace_days"] else "lapsed",
        "monthly_cost": r2(monthly), "yearly_cost": r2(monthly * 12),
        "price_change": found["price_change"], "history": found["history"],
    }


def detect_recurring(debits: list[dict], categories: dict[str, dict], as_of: datetime) -> list[dict]:
    """Recurring payments among `debits`, judged as of `as_of` (the newest date in the user's data)."""
    by_merchant: dict[str, list[dict]] = defaultdict(list)
    for t in debits:
        m = t.get("normalized_merchant")
        if m and m != "Unknown" and (t.get("debit_amount") or 0) > 0:
            by_merchant[m].append(t)

    items = []
    for merchant, txns in by_merchant.items():
        if len(txns) < 2:
            continue
        cat_ids = [str(t["category_id"]) for t in txns if t.get("category_id")]
        cat = categories.get(max(set(cat_ids), key=cat_ids.count), {}) if cat_ids else {}
        found = _evaluate(_by_date(txns), allow_variable=True)
        if found:
            items.append(_finish(found, merchant, cat, as_of))
            continue
        for cluster in _amount_clusters(txns, min_occ=3):
            found = _evaluate(_by_date(cluster), allow_variable=False, min_regular=MIN_REGULAR_SHARE_VARIABLE)
            if found:
                items.append(_finish(found, merchant, cat, as_of))

    items.sort(key=lambda i: (i["status"] != "active", -i["monthly_cost"], i["merchant"]))
    return items


def summarize(items: list[dict]) -> dict:
    """Totals and the next 30 days, over active items only."""
    active = [i for i in items if i["status"] == "active"]
    monthly = sum(i["monthly_cost"] for i in active)
    upcoming = sorted((i for i in active if i["due_in_days"] <= UPCOMING_DAYS), key=lambda i: i["next_expected"])
    return {
        "active_count": len(active),
        "lapsed_count": len(items) - len(active),
        "monthly_total": r2(monthly),
        "yearly_total": r2(monthly * 12),
        "upcoming_total": r2(sum(i["amount"] for i in upcoming)),
        "upcoming": [{"merchant": i["merchant"], "amount": i["amount"], "date": i["next_expected"],
                      "due_in_days": i["due_in_days"], "amount_kind": i["amount_kind"],
                      "category_color": i["category_color"]} for i in upcoming],
        "price_changes": sum(1 for i in active if i["price_change"]),
    }
