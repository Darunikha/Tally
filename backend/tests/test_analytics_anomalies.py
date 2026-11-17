from datetime import datetime, timedelta

from bson import ObjectId

from app.analytics.calculations import (amount_distribution, category_breakdown, merchant_breakdown, pct_change,
                                        time_series, totals, weekday_breakdown)
from app.analytics.insights import _inr, generate_insights
from app.anomaly_detection.detector import detect_anomalies
from app.services.query import Period

FOOD, SHOP, OTHER = str(ObjectId()), str(ObjectId()), str(ObjectId())
CATS = {FOOD: {"name": "Food & Dining", "color": "#111111"}, SHOP: {"name": "Shopping", "color": "#222222"},
        OTHER: {"name": "Other", "color": "#333333"}}


def tx(day, debit=0.0, credit=0.0, merchant="Swiggy", cat=FOOD, method="UPI", month=10, needs_review=False):
    return {"_id": ObjectId(), "transaction_date": datetime(2025, month, day), "debit_amount": debit,
            "credit_amount": credit, "transaction_type": "credit" if credit else "debit", "category_id": ObjectId(cat),
            "normalized_merchant": merchant, "payment_method": method, "upi_id": "swiggy@icici" if method == "UPI" else None,
            "needs_review": needs_review}


def test_totals():
    txns = [tx(1, credit=50000, merchant="Acme", method="NEFT"), tx(2, 300), tx(3, 700, merchant="Amazon", cat=SHOP, method="Card")]
    t = totals(txns, datetime(2025, 10, 1), datetime(2025, 10, 31))
    assert t["total_income"] == 50000 and t["total_expenses"] == 1000 and t["net_balance"] == 49000
    assert t["upi_spending"] == 300 and t["transaction_count"] == 3
    assert t["avg_daily_spending"] == round(1000 / 31, 2)
    assert t["savings_rate"] == 98.0


def test_category_breakdown_percentages():
    rows = category_breakdown([tx(1, 300), tx(2, 100), tx(3, 600, cat=SHOP)], CATS)
    assert [r["name"] for r in rows] == ["Shopping", "Food & Dining"]
    assert rows[0]["percentage"] == 60.0 and rows[1]["amount"] == 400 and rows[1]["count"] == 2


def test_time_series_fills_gaps():
    s = time_series([tx(1, 100), tx(3, 50)], "day", datetime(2025, 10, 1), datetime(2025, 10, 4))
    assert [p["expense"] for p in s] == [100, 0, 50, 0]
    m = time_series([tx(1, 100), tx(5, 10, month=12)], "month", datetime(2025, 10, 1), datetime(2025, 12, 31))
    assert [p["label"] for p in m] == ["Oct 2025", "Nov 2025", "Dec 2025"] and m[1]["expense"] == 0


def test_merchant_aggregation():
    rows = merchant_breakdown([tx(1, 100), tx(2, 300), tx(3, 50, merchant="Uber"), tx(4, credit=10)], categories=CATS)
    assert rows[0]["merchant"] == "Swiggy" and rows[0]["total"] == 400 and rows[0]["count"] == 2 and rows[0]["average"] == 200
    assert rows[0]["category"] == "Food & Dining"
    upi_only = merchant_breakdown([tx(1, 100), tx(2, 999, merchant="Amazon", method="Card")], upi_only=True)
    assert [r["merchant"] for r in upi_only] == ["Swiggy"]


def test_weekday_and_distribution():
    w = weekday_breakdown([tx(13, 100)])  # 13 Oct 2025 is a Monday
    assert w[0]["day"] == "Mon" and w[0]["amount"] == 100
    d = amount_distribution([tx(1, 50), tx(2, 750), tx(3, 60000)])
    assert sum(b["count"] for b in d) == 3 and d[-1]["count"] == 1


def test_pct_change_and_inr():
    assert pct_change(118, 100) == 18.0 and pct_change(5, 0) is None
    assert _inr(123456.7) == "₹1,23,457" and _inr(999) == "₹999" and _inr(10000000) == "₹1,00,00,000"


def test_previous_period_month_aligned():
    p = Period(datetime(2025, 10, 1), datetime(2025, 10, 31)).previous()
    assert (p.start, p.end) == (datetime(2025, 9, 1), datetime(2025, 9, 30))
    p2 = Period(datetime(2025, 10, 10), datetime(2025, 10, 19)).previous()
    assert (p2.start, p2.end) == (datetime(2025, 9, 30), datetime(2025, 10, 9))


def test_insights_use_real_numbers():
    prev = [tx(d, 100, month=9) for d in range(1, 11)]  # food 1000 in Sep
    cur = [tx(d, 118, month=10) for d in range(1, 11)] + [tx(5, 5000, merchant="Amazon", cat=SHOP, method="Card")]
    ins = {i["id"]: i for i in generate_insights(cur, prev, CATS, "in October 2025",
                                                datetime(2025, 10, 1), datetime(2025, 10, 31))}
    assert ins["cat_change_Food & Dining"]["message"].startswith("Your food & dining spending increased by 18%")
    assert "shopping" in ins["top_category"]["message"]
    assert ins["food_delivery"]["value"] == 10


# ---------------------------------------------------------------- anomalies
def _history():
    base = [tx(d % 28 + 1, 200 + (d % 7) * 30, month=7 + d // 28) for d in range(84)]  # ~3 months of small food spends
    return base


def test_high_amount_flagged_and_recurring_ignored():
    h = _history()
    big = tx(15, 48999, merchant="Flipkart", cat=SHOP, month=9)
    rent = [tx(5, 18000, merchant="Landlord", cat=OTHER, month=m) for m in (7, 8, 9)]
    found = detect_anomalies(h + [big] + rent, CATS)
    high = [a for a in found if a["type"] == "high_amount"]
    assert [a["transactions"][0]["merchant"] for a in high] == ["Flipkart"]
    assert high[0]["severity"] == "high" and "median" in high[0]["reason"]


def test_rapid_repeat_and_duplicates():
    h = _history() + [tx(20, 300 + i, month=9) for i in range(4)]
    h += [tx(22, 455, merchant="Zomato", month=9), tx(22, 455, merchant="Zomato", month=9)]
    types = {a["type"] for a in detect_anomalies(h, CATS)}
    assert {"rapid_repeat", "duplicate_like"} <= types


def test_category_spike():
    h = [tx(d, 100, merchant="Amazon", cat=SHOP, month=m) for m in (6, 7, 8) for d in range(1, 21)]  # 2000/month
    h += [tx(d, 600, merchant="Amazon", cat=SHOP, month=9) for d in range(1, 21)]  # 12000 in Sep
    spikes = [a for a in detect_anomalies(h, CATS) if a["type"] == "category_spike"]
    assert spikes and spikes[0]["metrics"]["ratio"] == 6.0 and spikes[0]["severity"] == "high"


def test_period_filter_and_sensitivity():
    h = _history() + [tx(15, 48999, merchant="Flipkart", cat=SHOP, month=9)]
    none = detect_anomalies(h, CATS, start=datetime(2025, 7, 1), end=datetime(2025, 7, 31))
    assert not [a for a in none if a["type"] == "high_amount"]
    user_threshold = detect_anomalies(_history(), CATS, large_threshold=300)
    assert any("large-transaction alert" in a["reason"] for a in user_threshold)


def test_no_anomalies_on_tiny_history():
    assert detect_anomalies([tx(1, 100), tx(2, 50000)], CATS) == []
