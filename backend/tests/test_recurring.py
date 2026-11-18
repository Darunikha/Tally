"""Recurring payments: detection rules (pure) and the API."""
from datetime import datetime, timedelta

import pytest
from bson import ObjectId

from app.analytics.recurring import add_months, detect_recurring, summarize
from tests.conftest import register
from tests.test_api import import_file

SUBS, BILLS = ObjectId(), ObjectId()
CATS = {str(SUBS): {"name": "Subscriptions", "color": "#A07AA8"}, str(BILLS): {"name": "Bills & Utilities", "color": "#6250D6"}}
AS_OF = datetime(2026, 5, 31)


def d(y, m, day):
    return datetime(y, m, day)


def pay(merchant, when, amount, cat=SUBS):
    return {"normalized_merchant": merchant, "transaction_date": when, "debit_amount": float(amount), "category_id": cat}


def monthly(merchant, amounts, start=(2026, 1, 5), cat=SUBS, day=None):
    y, m, dd = start
    out = []
    for i, a in enumerate(amounts):
        idx = (y * 12 + m - 1) + i
        out.append(pay(merchant, d(idx // 12, idx % 12 + 1, day or dd), a, cat))
    return out


def find(items, merchant):
    return next((i for i in items if i["merchant"] == merchant), None)


# ------------------------------------------------------------------ what counts as recurring
def test_fixed_monthly_subscription():
    item = find(detect_recurring(monthly("Netflix", [649] * 4), CATS, AS_OF), "Netflix")
    assert (item["cadence"], item["amount_kind"], item["amount"], item["occurrences"]) == ("monthly", "fixed", 649.0, 4)
    assert (item["first_date"], item["last_date"], item["next_expected"]) == ("2026-01-05", "2026-04-05", "2026-05-05")
    assert (item["monthly_cost"], item["yearly_cost"], item["group"], item["price_change"]) == (649.0, 7788.0, "subscription", None)
    assert item["history"][-1] == {"date": "2026-04-05", "amount": 649.0}


def test_payment_dates_may_drift_around_weekends_and_month_lengths():
    rows = [pay("Gym", d(2026, 1, 5), 1500), pay("Gym", d(2026, 2, 7), 1500), pay("Gym", d(2026, 3, 5), 1500), pay("Gym", d(2026, 4, 4), 1500)]
    assert find(detect_recurring(rows, CATS, AS_OF), "Gym")["cadence"] == "monthly"


def test_a_bill_that_varies_is_recurring_but_flagged_variable():
    item = find(detect_recurring(monthly("BESCOM", [1363, 1176, 1238, 1410], cat=BILLS), CATS, AS_OF), "BESCOM")
    assert (item["amount_kind"], item["amount"], item["group"]) == ("variable", pytest.approx(1300.5), "bill")


def test_quarterly_and_yearly():
    q = [pay("Insurance", d(2026, 1, 10), 3000), pay("Insurance", d(2026, 4, 11), 3000), pay("Insurance", d(2026, 7, 10), 3000)]
    item = find(detect_recurring(q, CATS, datetime(2026, 8, 1)), "Insurance")
    assert (item["cadence"], item["monthly_cost"], item["next_expected"]) == ("quarterly", 1000.0, "2026-10-10")

    y = [pay("Prime", d(2025, 3, 2), 1499), pay("Prime", d(2026, 3, 2), 1499)]
    item = find(detect_recurring(y, CATS, AS_OF), "Prime")
    assert (item["cadence"], item["next_expected"], item["monthly_cost"]) == ("yearly", "2027-03-02", pytest.approx(124.92, abs=0.01))
    assert detect_recurring([pay("Prime", d(2026, 3, 2), 1499)], CATS, AS_OF) == []  # one payment proves nothing


def test_weekly_needs_a_long_run():
    rows = lambda n: [pay("Paper", d(2026, 3, 1) + timedelta(days=7 * i), 120) for i in range(n)]  # noqa: E731
    assert detect_recurring(rows(5), CATS, AS_OF) == []
    assert find(detect_recurring(rows(6), CATS, AS_OF), "Paper")["cadence"] == "weekly"


# ------------------------------------------------------------------ what must NOT be reported
def test_frequent_but_irregular_spending_is_not_recurring():
    days = [1, 2, 4, 9, 11, 12, 17, 23, 24, 29]
    rows = [pay("Swiggy", d(2026, 3, x), 300 + 17 * x) for x in days]
    assert detect_recurring(rows, CATS, AS_OF) == []


def test_one_monthly_looking_gap_among_erratic_ones_is_not_a_cadence():
    """The median gap is 29 days, but only one of five gaps is actually monthly."""
    when, rows = d(2026, 1, 1), []
    for gap in [0, 12, 14, 29, 45, 60]:
        when += timedelta(days=gap)
        rows.append(pay("Mystery", when, 500))
    assert detect_recurring(rows, CATS, datetime(2026, 12, 31)) == []


def test_two_payments_are_not_enough_for_monthly():
    assert detect_recurring(monthly("Netflix", [649, 649]), CATS, AS_OF) == []


def test_regular_dates_with_wildly_different_amounts_are_not_a_subscription():
    assert detect_recurring(monthly("Amazon", [500, 5200, 1500, 90]), CATS, AS_OF) == []


def test_a_weekly_payment_that_varies_is_not_recurring():
    rows = [pay("Grocer", d(2026, 3, 1) + timedelta(days=7 * i), a) for i, a in enumerate([300, 450, 380, 520, 410, 290, 480])]
    assert detect_recurring(rows, CATS, AS_OF) == []


def test_unknown_merchants_and_zero_amounts_are_skipped():
    assert detect_recurring(monthly("Unknown", [100] * 4), CATS, AS_OF) == []
    assert detect_recurring(monthly("Free Trial", [0] * 4), CATS, AS_OF) == []


# ------------------------------------------------------------------ price changes and mixed merchants
@pytest.mark.parametrize("amounts,before,after,pct", [
    ([649, 649, 649, 799], 649, 799, 23.1),
    ([649, 649, 799], 649, 799, 23.1),
    ([799, 799, 799, 699], 799, 699, -12.5),
])
def test_price_change_on_the_latest_payment(amounts, before, after, pct):
    item = find(detect_recurring(monthly("Netflix", amounts), CATS, AS_OF), "Netflix")
    assert item["amount_kind"] == "fixed" and item["amount"] == after  # the current price, not the old one
    assert item["price_change"] == {"from": float(before), "to": float(after), "percent": pct}


def test_an_old_price_change_is_not_flagged_again():
    item = find(detect_recurring(monthly("Netflix", [649, 649, 799, 799, 799]), CATS, AS_OF), "Netflix")
    assert item["price_change"] is None and item["amount"] == 799


def test_subscription_hidden_among_a_merchants_other_purchases():
    """An app-store style merchant: a fixed monthly charge amid irregular one-off purchases."""
    noise = [pay("Google Play", d(2026, 1, x), a) for x, a in [(2, 349), (13, 59), (21, 1200), (28, 89)]]
    noise += [pay("Google Play", d(2026, 3, x), a) for x, a in [(3, 410), (16, 29), (25, 640)]]
    items = detect_recurring(monthly("Google Play", [75] * 4, start=(2026, 1, 9)) + noise, CATS, AS_OF)
    assert [(i["merchant"], i["amount"], i["cadence"]) for i in items] == [("Google Play", 75.0, "monthly")]


# ------------------------------------------------------------------ dates and status
@pytest.mark.parametrize("start,months,expected", [
    (d(2026, 1, 31), 1, d(2026, 2, 28)), (d(2024, 1, 31), 1, d(2024, 2, 29)),
    (d(2026, 11, 30), 3, d(2027, 2, 28)), (d(2026, 12, 15), 1, d(2027, 1, 15)), (d(2026, 3, 31), 12, d(2027, 3, 31)),
])
def test_add_months_clamps_to_month_length(start, months, expected):
    assert add_months(start, months) == expected


def test_month_end_payments_keep_their_day():
    rows = [pay("Loan", d(2025, 12, 31), 8000), pay("Loan", d(2026, 1, 31), 8000), pay("Loan", d(2026, 2, 28), 8000)]
    assert find(detect_recurring(rows, CATS, AS_OF), "Loan")["next_expected"] == "2026-03-31"


def test_active_due_soon_and_lapsed():
    rows = monthly("Netflix", [649] * 4)  # last paid 5 Apr, next due 5 May
    status = lambda as_of: find(detect_recurring(rows, CATS, as_of), "Netflix")  # noqa: E731
    soon = status(datetime(2026, 4, 30))
    assert (soon["status"], soon["due_in_days"]) == ("active", 5)
    late = status(datetime(2026, 5, 10))  # 5 days after the due date is inside the 7-day grace period
    assert (late["status"], late["due_in_days"]) == ("active", -5)
    gone = status(datetime(2026, 5, 13))
    assert (gone["status"], gone["due_in_days"]) == ("lapsed", -8)


def test_ordering_active_first_then_by_monthly_cost():
    rows = (monthly("Cheap", [100] * 4) + monthly("Pricey", [900] * 4) + monthly("Old", [5000] * 4, start=(2025, 1, 5)))
    items = detect_recurring(rows, CATS, datetime(2026, 4, 30))
    assert [(i["merchant"], i["status"]) for i in items] == [("Pricey", "active"), ("Cheap", "active"), ("Old", "lapsed")]


# ------------------------------------------------------------------ summary
def test_summary_counts_only_active_items_and_lists_the_next_30_days():
    rows = (monthly("Netflix", [649, 649, 649, 799]) + monthly("Rent", [18000] * 4, start=(2026, 1, 25), cat=BILLS)
            + monthly("Old", [300] * 4, start=(2025, 1, 5)))
    items = detect_recurring(rows, CATS, datetime(2026, 4, 28))
    s = summarize(items)
    assert (s["active_count"], s["lapsed_count"], s["price_changes"]) == (2, 1, 1)
    assert s["monthly_total"] == 18000 + 799 and s["yearly_total"] == (18000 + 799) * 12
    assert [(u["merchant"], u["date"], u["due_in_days"]) for u in s["upcoming"]] == [("Rent", "2026-05-25", 27), ("Netflix", "2026-05-05", 7)][::-1] \
        or [u["merchant"] for u in s["upcoming"]] == ["Netflix", "Rent"]
    assert s["upcoming_total"] == 18799


def test_summary_of_nothing():
    assert summarize([]) == {"active_count": 0, "lapsed_count": 0, "monthly_total": 0.0, "yearly_total": 0.0,
                             "upcoming_total": 0.0, "upcoming": [], "price_changes": 0}


# ------------------------------------------------------------------ API
EXPECTED_FIXED = {"Suresh Nair": 18000.0, "Netflix": 649.0, "Spotify": 119.0, "Airtel": 599.0, "Groww": 5000.0}


async def recurring(client, auth):
    r = await client.get("/api/recurring", headers=auth)
    assert r.status_code == 200, r.text
    return r.json()


async def test_sample_statement_finds_the_real_commitments_and_nothing_else(client, auth, sample):
    await import_file(client, auth, sample("hdfc_statement.csv"))
    data = await recurring(client, auth)
    items = {i["merchant"]: i for i in data["items"]}
    assert data["as_of"] == "2025-10-31"
    assert {k: i["amount"] for k, i in items.items() if i["amount_kind"] == "fixed"} == EXPECTED_FIXED
    assert items["BESCOM"]["amount_kind"] == "variable"
    assert all(i["cadence"] == "monthly" and i["status"] == "active" for i in items.values())
    # frequent but irregular spending and cash withdrawals are not recurring
    assert not {"Swiggy", "Zomato", "Uber", "Amazon", "Blinkit", "DMart", "BigBasket", "ATM Withdrawal", "Indian Oil"} & items.keys()
    assert (items["Netflix"]["group"], items["Suresh Nair"]["group"], items["Groww"]["group"]) == ("subscription", "bill", "other")
    assert data["summary"]["monthly_total"] == pytest.approx(sum(i["monthly_cost"] for i in items.values()))
    assert data["summary"]["active_count"] == 6 and data["ignored_count"] == 0
    assert {u["merchant"] for u in data["summary"]["upcoming"]} == set(items)  # all fall due within 30 days of 31 Oct


async def test_ignore_and_restore(client, auth, sample):
    await import_file(client, auth, sample("hdfc_statement.csv"))
    before = await recurring(client, auth)
    r = await client.put("/api/recurring/ignored", headers=auth, json={"merchant": "Airtel"})
    assert r.status_code == 200 and r.json() == {"merchant": "Airtel", "ignored": True}
    await client.put("/api/recurring/ignored", headers=auth, json={"merchant": "Airtel"})  # idempotent

    data = await recurring(client, auth)
    assert next(i for i in data["items"] if i["merchant"] == "Airtel")["ignored"] is True
    assert data["ignored_count"] == 1 and data["summary"]["active_count"] == 5
    assert data["summary"]["monthly_total"] == pytest.approx(before["summary"]["monthly_total"] - 599)

    await client.put("/api/recurring/ignored", headers=auth, json={"merchant": "Airtel", "ignored": False})
    assert (await recurring(client, auth))["summary"] == before["summary"]


async def test_validation_and_auth(client, auth):
    for body in ({"merchant": ""}, {"merchant": "x" * 101}, {}):
        assert (await client.put("/api/recurring/ignored", headers=auth, json=body)).status_code == 422
    assert (await client.get("/api/recurring")).status_code == 401
    assert (await client.put("/api/recurring/ignored", json={"merchant": "A"})).status_code == 401


async def test_empty_account(client, auth):
    data = await recurring(client, auth)
    assert data["as_of"] is None and data["items"] == [] and data["summary"]["monthly_total"] == 0


async def test_each_users_data_and_ignores_are_private(client, auth, sample):
    await import_file(client, auth, sample("hdfc_statement.csv"))
    await client.put("/api/recurring/ignored", headers=auth, json={"merchant": "Netflix"})
    other = await register(client, "other@example.com")
    assert (await recurring(client, other))["items"] == []
    await import_file(client, other, sample("hdfc_statement.csv"))
    assert next(i for i in (await recurring(client, other))["items"] if i["merchant"] == "Netflix")["ignored"] is False


MONTHLY_CARD_BILL = "Posting Date,Transaction Details,Amount,Running Balance\n" + "\n".join(
    f"2025-{m:02d}-10,CREDIT CARD PAYMENT HDFC CARD,-{a}.00,{100000 - i}.00" for i, (m, a) in enumerate([(6, 21000), (7, 21000), (8, 21000), (9, 21000)])
).encode().decode()


async def test_card_bill_payments_are_never_listed_as_recurring(client, auth, sample):
    await import_file(client, auth, MONTHLY_CARD_BILL.encode(), "bills.csv")
    assert (await recurring(client, auth))["items"] == []  # money moving to your own card is not a bill you owe


async def test_ignored_merchants_are_exported_and_deleted_with_the_account(client, auth, db, sample):
    await import_file(client, auth, sample("hdfc_statement.csv"))
    await client.put("/api/recurring/ignored", headers=auth, json={"merchant": "Netflix"})
    exported = (await client.get("/api/settings/export", headers=auth)).json()
    assert [r["merchant"] for r in exported["recurring_ignored"]] == ["Netflix"]
    r = await client.request("DELETE", "/api/settings/account", headers=auth, json={"password": "secret123"})
    assert r.status_code == 200
    assert await db["recurring_ignored"].count_documents({}) == 0
