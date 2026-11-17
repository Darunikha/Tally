"""Plain-language insights computed strictly from the user's transactions (no generic advice)."""
from __future__ import annotations

from collections import defaultdict

from app.analytics.calculations import category_breakdown, merchant_breakdown, pct_change, totals


def _inr(v: float) -> str:
    """Indian digit grouping: 123456.7 -> ₹1,23,457"""
    n = int(round(abs(v)))
    s = str(n)
    if len(s) > 3:
        head, tail = s[:-3], s[-3:]
        parts = []
        while len(head) > 2:
            parts.insert(0, head[-2:])
            head = head[:-2]
        if head:
            parts.insert(0, head)
        s = ",".join(parts) + "," + tail
    return f"{'-' if v < 0 else ''}₹{s}"


FOOD_DELIVERY = {"Swiggy", "Zomato", "Swiggy Instamart", "Domino's", "McDonald's", "KFC", "Pizza Hut"}


def generate_insights(current: list[dict], previous: list[dict], categories: dict[str, dict],
                      period_label: str, start=None, end=None) -> list[dict]:
    """Each insight: {id, type, tone (positive|negative|neutral), title, message, value}."""
    out: list[dict] = []
    if not current:
        return out
    cur_tot = totals(current, start, end)
    prev_tot = totals(previous) if previous else None
    cur_cats = category_breakdown(current, categories)
    prev_cats = {c["name"]: c["amount"] for c in category_breakdown(previous, categories)} if previous else {}

    # 1. category month-over-month changes (largest absolute change among meaningful categories)
    changes = []
    for c in cur_cats:
        prev_amt = prev_cats.get(c["name"])
        if prev_amt and c["amount"] >= 500 and c["name"] not in ("Transfers", "Other"):
            ch = pct_change(c["amount"], prev_amt)
            if ch is not None and abs(ch) >= 10:
                changes.append((abs(c["amount"] - prev_amt), c["name"], ch))
    for _, name, ch in sorted(changes, reverse=True)[:2]:
        up = ch > 0
        out.append({
            "id": f"cat_change_{name}", "type": "category_change", "tone": "negative" if up else "positive",
            "title": f"{name} {'up' if up else 'down'} {abs(ch):.0f}%",
            "message": f"Your {name.lower()} spending {'increased' if up else 'decreased'} by {abs(ch):.0f}% compared to the previous period.",
            "value": ch,
        })

    # 2. top category
    spend_cats = [c for c in cur_cats if c["name"] not in ("Transfers",)]
    if spend_cats:
        top = spend_cats[0]
        out.append({
            "id": "top_category", "type": "top_category", "tone": "neutral",
            "title": f"Most spent on {top['name']}",
            "message": f"You spent the most on {top['name'].lower()} {period_label}: {_inr(top['amount'])} across {top['count']} transactions ({top['percentage']:.0f}% of spending).",
            "value": top["amount"],
        })

    # 3. food delivery frequency
    fd = [t for t in current if t.get("transaction_type") == "debit" and t.get("normalized_merchant") in FOOD_DELIVERY]
    if len(fd) >= 3:
        out.append({
            "id": "food_delivery", "type": "frequency", "tone": "neutral",
            "title": f"{len(fd)} food delivery orders",
            "message": f"You made {len(fd)} transactions to food delivery merchants, totalling {_inr(sum(t['debit_amount'] for t in fd))}.",
            "value": len(fd),
        })

    # 4. average daily spending vs previous
    msg = f"Your average daily spending is {_inr(cur_tot['avg_daily_spending'])}."
    if prev_tot and prev_tot["avg_daily_spending"]:
        ch = pct_change(cur_tot["avg_daily_spending"], prev_tot["avg_daily_spending"])
        if ch is not None:
            msg += f" That's {abs(ch):.0f}% {'higher' if ch > 0 else 'lower'} than the previous period."
    out.append({"id": "avg_daily", "type": "average", "tone": "neutral", "title": "Average daily spending",
                "message": msg, "value": cur_tot["avg_daily_spending"]})

    # 5. subscriptions
    subs = next((c for c in cur_cats if c["name"] == "Subscriptions"), None)
    if subs:
        merchants = sorted({t.get("normalized_merchant") for t in current
                            if str(t.get("category_id")) == str(subs["category_id"]) and t.get("normalized_merchant")})
        out.append({
            "id": "subscriptions", "type": "subscriptions", "tone": "neutral",
            "title": f"Subscriptions: {_inr(subs['amount'])}",
            "message": f"Your subscription expenses total {_inr(subs['amount'])} {period_label}"
                       + (f" ({', '.join(merchants[:4])})." if merchants else "."),
            "value": subs["amount"],
        })

    # 6. top merchant
    tm = merchant_breakdown(current, limit=1)
    if tm and tm[0]["merchant"] not in ("Unknown", "ATM Withdrawal"):
        m = tm[0]
        out.append({
            "id": "top_merchant", "type": "merchant", "tone": "neutral", "title": f"Top merchant: {m['merchant']}",
            "message": f"{m['merchant']} received {_inr(m['total'])} from you over {m['count']} transactions (avg {_inr(m['average'])}).",
            "value": m["total"],
        })

    # 7. savings rate / net
    if cur_tot["total_income"] > 0:
        rate = cur_tot["savings_rate"]
        tone = "positive" if rate and rate > 0 else "negative"
        out.append({
            "id": "savings", "type": "savings", "tone": tone,
            "title": f"Net {'saved' if cur_tot['net_balance'] >= 0 else 'overspent'} {_inr(abs(cur_tot['net_balance']))}",
            "message": (f"You kept {rate:.0f}% of your income {period_label}." if rate and rate > 0
                        else f"Expenses exceeded income by {_inr(abs(cur_tot['net_balance']))} {period_label}."),
            "value": rate,
        })

    # 8. items to review
    review = sum(1 for t in current if t.get("needs_review"))
    if review:
        out.append({"id": "review", "type": "review", "tone": "neutral", "title": f"{review} to review",
                    "message": f"{review} transaction{'s' if review != 1 else ''} could not be categorised automatically and {'are' if review != 1 else 'is'} marked Other.",
                    "value": review})

    # 9. weekend vs weekday
    by = defaultdict(float)
    for t in current:
        if t.get("transaction_type") == "debit":
            by["weekend" if t["transaction_date"].weekday() >= 5 else "weekday"] += t["debit_amount"]
    if by["weekend"] and by["weekday"]:
        # per-day comparison
        wk_end, wk_day = by["weekend"] / 2, by["weekday"] / 5
        if wk_end > wk_day * 1.25:
            out.append({"id": "weekend", "type": "pattern", "tone": "neutral", "title": "Weekend spender",
                        "message": f"On average you spend {wk_end / wk_day:.1f}× more per weekend day than per weekday.",
                        "value": round(wk_end / wk_day, 2)})
    return out
