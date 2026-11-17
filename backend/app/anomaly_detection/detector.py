"""Rule-based anomaly detection.

Anomalies are *indicators for review*, never fraud verdicts. Each detector uses the user's own
history as the baseline, so thresholds adapt to how the user normally spends.
"""
from __future__ import annotations

import hashlib
import statistics
from collections import defaultdict
from datetime import datetime, timedelta

from app.utils.dates import month_start
from app.utils.money import r2

DISCLAIMER = (
    "Anomalies are automated indicators based on your own spending patterns. They are not a judgement "
    "of fraud - please review each one and dismiss it if it is expected."
)

SENSITIVITY = {
    #           IQR k  merchant z  burst n  spike ratio  min freq/day
    "low":    {"k": 6.0, "z": 4.0, "burst": 5, "spike": 2.0, "freq": 12},
    "medium": {"k": 4.5, "z": 3.0, "burst": 3, "spike": 1.5, "freq": 8},
    "high":   {"k": 3.0, "z": 2.5, "burst": 3, "spike": 1.3, "freq": 6},
}

TYPE_LABELS = {
    "high_amount": "Unusually high amount",
    "above_normal": "Higher than your usual spend",
    "rapid_repeat": "Repeated payments in a short period",
    "duplicate_like": "Possible duplicate",
    "high_frequency": "Unusually many transactions",
    "category_spike": "Category spending spike",
}

EXCLUDED_SPIKE_CATEGORIES = {"Transfers", "Income"}


def _key(kind: str, *parts) -> str:
    return hashlib.sha1("|".join([kind, *map(str, parts)]).encode()).hexdigest()[:20]


def _brief(t: dict, categories: dict[str, dict]) -> dict:
    cat = categories.get(str(t.get("category_id")), {})
    return {
        "id": str(t["_id"]),
        "date": t["transaction_date"].strftime("%Y-%m-%d"),
        "merchant": t.get("normalized_merchant"),
        "description": t.get("raw_description"),
        "amount": r2(t.get("debit_amount") or t.get("credit_amount")),
        "payment_method": t.get("payment_method"),
        "category": cat.get("name"),
        "upi_id": t.get("upi_id"),
    }


def _severity_from_ratio(ratio: float, high: float = 3.0, medium: float = 1.5) -> str:
    return "high" if ratio >= high else "medium" if ratio >= medium else "low"


def _is_recurring(t: dict, by_merchant: dict[str, list[dict]]) -> bool:
    """A payment that repeats at a similar amount (rent, SIP, EMI) is not unusual."""
    m = t.get("normalized_merchant")
    if not m or m == "Unknown":
        return False
    similar = [o for o in by_merchant.get(m, []) if o["_id"] != t["_id"]
               and abs(o["debit_amount"] - t["debit_amount"]) <= 0.1 * t["debit_amount"]]
    return len(similar) >= 2


def detect_anomalies(history: list[dict], categories: dict[str, dict], start: datetime | None = None,
                     end: datetime | None = None, sensitivity: str = "medium",
                     large_threshold: float | None = None) -> list[dict]:
    cfg = SENSITIVITY.get(sensitivity, SENSITIVITY["medium"])
    debits = sorted((t for t in history if t.get("transaction_type") == "debit" and t.get("debit_amount", 0) > 0),
                    key=lambda t: t["transaction_date"])

    def in_range(d: datetime) -> bool:
        return (start is None or d >= start) and (end is None or d <= end)

    anomalies: list[dict] = []
    flagged_amount: set = set()
    by_merchant: dict[str, list[dict]] = defaultdict(list)
    for t in debits:
        by_merchant[t.get("normalized_merchant") or "Unknown"].append(t)

    # 1) unusually high amounts relative to all of the user's debits
    amounts = [t["debit_amount"] for t in debits]
    if len(amounts) >= 15:
        q = statistics.quantiles(amounts, n=4)
        q1, med, q3 = q[0], q[1], q[2]
        threshold = max(q3 + cfg["k"] * (q3 - q1), med * 8, 1000.0)
        for t in debits:
            if not in_range(t["transaction_date"]):
                continue
            over_user = large_threshold and t["debit_amount"] >= large_threshold
            if (t["debit_amount"] > threshold and not _is_recurring(t, by_merchant)) or over_user:
                ratio = t["debit_amount"] / threshold
                reason = (f"₹{t['debit_amount']:,.0f} is {t['debit_amount'] / med:.0f}× your median transaction "
                          f"(₹{med:,.0f}) and above your usual upper range (₹{threshold:,.0f}).")
                if over_user:
                    reason = f"₹{t['debit_amount']:,.0f} exceeds your large-transaction alert of ₹{large_threshold:,.0f}. " + reason
                anomalies.append({
                    "key": _key("high_amount", t["_id"]), "type": "high_amount",
                    "severity": _severity_from_ratio(ratio), "reason": reason,
                    "date": t["transaction_date"], "amount": r2(t["debit_amount"]),
                    "transactions": [_brief(t, categories)],
                    "metrics": {"threshold": r2(threshold), "median": r2(med)},
                })
                flagged_amount.add(t["_id"])

    # 2) higher than usual for this category (z-score against prior history in the category)
    by_cat: dict[str, list[dict]] = defaultdict(list)
    for t in debits:
        cid = str(t.get("category_id"))
        prior = by_cat[cid]
        if len(prior) >= 6 and in_range(t["transaction_date"]) and t["_id"] not in flagged_amount:
            vals = [p["debit_amount"] for p in prior]
            mean, sd, med = statistics.fmean(vals), statistics.pstdev(vals), statistics.median(vals)
            if sd > 0 and t["debit_amount"] > mean + cfg["z"] * sd and t["debit_amount"] > 2 * med \
                    and t["debit_amount"] >= 500 and not _is_recurring(t, by_merchant):
                cname = categories.get(cid, {}).get("name", "this category")
                z = (t["debit_amount"] - mean) / sd
                anomalies.append({
                    "key": _key("above_normal", t["_id"]), "type": "above_normal",
                    "severity": "high" if z >= cfg["z"] * 2 else "medium" if z >= cfg["z"] * 1.3 else "low",
                    "reason": f"₹{t['debit_amount']:,.0f} is well above your typical {cname} spend "
                              f"(average ₹{mean:,.0f}, usually up to ₹{mean + sd:,.0f}).",
                    "date": t["transaction_date"], "amount": r2(t["debit_amount"]),
                    "transactions": [_brief(t, categories)],
                    "metrics": {"category_average": r2(mean), "z_score": round(z, 1)},
                })
        prior.append(t)

    # 3) many payments to the same merchant within ~24h, and 4) duplicate-looking payments
    for merchant, txns in by_merchant.items():
        if merchant in ("Unknown",):
            continue
        i = 0
        while i < len(txns):
            j = i
            while j + 1 < len(txns) and txns[j + 1]["transaction_date"] - txns[i]["transaction_date"] <= timedelta(days=1):
                j += 1
            window = txns[i:j + 1]
            if len(window) >= cfg["burst"] and any(in_range(t["transaction_date"]) for t in window):
                total = sum(t["debit_amount"] for t in window)
                anomalies.append({
                    "key": _key("rapid_repeat", *[t["_id"] for t in window]), "type": "rapid_repeat",
                    "severity": "high" if len(window) >= cfg["burst"] + 3 else "medium" if len(window) >= cfg["burst"] + 1 else "low",
                    "reason": f"{len(window)} payments to {merchant} within 24 hours, totalling ₹{total:,.0f}.",
                    "date": window[0]["transaction_date"], "amount": r2(total),
                    "transactions": [_brief(t, categories) for t in window],
                    "metrics": {"count": len(window)},
                })
                i = j + 1
            else:
                i += 1

        # same account (bank), same day, same amount: payments from two different accounts are not a double charge
        groups: dict[tuple, list[dict]] = defaultdict(list)
        for t in txns:
            groups[(t["transaction_date"], round(t["debit_amount"], 2), t.get("bank_name"))].append(t)
        for (d, amt, _bank), g in groups.items():
            if len(g) >= 2 and in_range(d):
                anomalies.append({
                    "key": _key("duplicate_like", *[t["_id"] for t in g]), "type": "duplicate_like",
                    "severity": "high" if amt >= 5000 else "medium" if amt >= 500 else "low",
                    "reason": f"{len(g)} identical payments of ₹{amt:,.2f} to {merchant} on the same day. "
                              "This may be a double charge - check with the merchant if unexpected.",
                    "date": d, "amount": r2(amt * len(g)),
                    "transactions": [_brief(t, categories) for t in g],
                    "metrics": {"count": len(g)},
                })

    # 5) unusually many transactions in a single day
    per_day: dict[datetime, list[dict]] = defaultdict(list)
    for t in debits:
        per_day[t["transaction_date"]].append(t)
    if len(per_day) >= 10:
        counts = [len(v) for v in per_day.values()]
        mean, sd = statistics.fmean(counts), statistics.pstdev(counts)
        limit = max(cfg["freq"], mean + 3 * sd)
        for d, v in per_day.items():
            if len(v) > limit and in_range(d):
                anomalies.append({
                    "key": _key("high_frequency", d.date()), "type": "high_frequency",
                    "severity": "medium" if len(v) > limit * 1.5 else "low",
                    "reason": f"{len(v)} debit transactions on one day, versus about {mean:.1f} on a typical active day.",
                    "date": d, "amount": r2(sum(t["debit_amount"] for t in v)),
                    "transactions": [_brief(t, categories) for t in sorted(v, key=lambda x: -x["debit_amount"])[:10]],
                    "metrics": {"count": len(v), "typical": round(mean, 1)},
                })

    # 6) category spending spikes vs the average of the previous 3 months
    monthly: dict[str, dict[datetime, list[dict]]] = defaultdict(lambda: defaultdict(list))
    for t in debits:
        monthly[str(t.get("category_id"))][month_start(t["transaction_date"])].append(t)
    for cid, months in monthly.items():
        cname = categories.get(cid, {}).get("name", "Uncategorized")
        if cname in EXCLUDED_SPIKE_CATEGORIES:
            continue
        ordered = sorted(months)
        for idx, m in enumerate(ordered):
            if idx < 2:
                continue
            prev = [sum(x["debit_amount"] for x in months.get(p, [])) for p in ordered[max(0, idx - 3):idx]]
            baseline = statistics.fmean(prev) if prev else 0
            cur = sum(x["debit_amount"] for x in months[m])
            m_end = (m.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)
            overlaps = (end is None or m <= end) and (start is None or m_end >= start)
            if baseline > 0 and cur > baseline * cfg["spike"] and cur - baseline >= 2000 and overlaps:
                ratio = cur / baseline
                top = sorted(months[m], key=lambda x: -x["debit_amount"])[:5]
                anomalies.append({
                    "key": _key("category_spike", cid, m.date()), "type": "category_spike",
                    "severity": _severity_from_ratio(ratio, high=3.0, medium=2.0),
                    "reason": f"{cname} spending in {m:%B %Y} was ₹{cur:,.0f}, {ratio:.1f}× your recent monthly "
                              f"average of ₹{baseline:,.0f}.",
                    "date": m, "amount": r2(cur),
                    "transactions": [_brief(t, categories) for t in top],
                    "metrics": {"baseline": r2(baseline), "ratio": round(ratio, 2), "category": cname},
                })

    sev_rank = {"high": 0, "medium": 1, "low": 2}
    for a in anomalies:
        a["type_label"] = TYPE_LABELS[a["type"]]
        a["date"] = a["date"].strftime("%Y-%m-%d")
    anomalies.sort(key=lambda a: a["date"], reverse=True)      # newest first...
    anomalies.sort(key=lambda a: sev_rank[a["severity"]])      # ...within each severity (stable sort)
    return anomalies
