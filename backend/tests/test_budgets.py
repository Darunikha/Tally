"""Budgets: pure calculation tests plus API tests against the in-memory database."""
from datetime import date, datetime

import pytest
from bson import ObjectId

from app.analytics.budgets import budget_status, history_average, history_window, spend_by_category
from tests.conftest import register
from tests.test_api import import_file

FOOD, SHOP = ObjectId(), ObjectId()
CATS = {str(FOOD): {"name": "Food", "color": "#1BAF7A"}, str(SHOP): {"name": "Shopping", "color": "#EB6834"}}
MAY = datetime(2026, 5, 1)


def tx(day, amount, cat=FOOD, month=5):
    return {"transaction_date": datetime(2026, month, day), "debit_amount": amount, "category_id": cat}


def budget(cat, limit, threshold=80):
    return {"_id": ObjectId(), "category_id": cat, "monthly_limit": limit, "alert_threshold": threshold}


def status(budgets, debits, today=date(2026, 6, 15), history=None):
    spend, total = spend_by_category(debits)
    h, ht = history or ({}, 0.0)
    return budget_status(budgets, spend, total, CATS, MAY, today, h, ht)


# ------------------------------------------------------------------ calculations
def test_status_thresholds():
    rows = {r["name"]: r for r in status(
        [budget(FOOD, 1000), budget(SHOP, 1000)], [tx(1, 500), tx(2, 300, SHOP), tx(3, 100, SHOP)])["budgets"]}
    assert rows["Food"]["status"] == "ok" and rows["Food"]["percent"] == 50.0
    assert rows["Shopping"]["status"] == "ok" and rows["Shopping"]["percent"] == 40.0
    s = status([budget(FOOD, 1000)], [tx(1, 800)])["budgets"][0]
    assert s["status"] == "warning"  # exactly at the 80% alert threshold
    s = status([budget(FOOD, 1000)], [tx(1, 1000)])["budgets"][0]
    assert s["status"] == "warning" and s["remaining"] == 0  # spending exactly the limit is not "over"
    s = status([budget(FOOD, 1000)], [tx(1, 1000.01)])["budgets"][0]
    assert s["status"] == "over" and s["remaining"] == -0.01


def test_custom_alert_threshold():
    s = status([budget(FOOD, 1000, threshold=50)], [tx(1, 500)])["budgets"][0]
    assert s["status"] == "warning"


def test_overall_budget_counts_all_debits_including_uncategorised():
    out = status([budget(None, 2000)], [tx(1, 500), tx(2, 700, SHOP), tx(3, 300, None)])
    assert out["overall"]["spent"] == 1500 and out["overall"]["percent"] == 75.0
    assert out["overall"]["name"] == "Overall spending" and out["budgets"] == []


def test_budget_without_spending_and_deleted_category():
    out = status([budget(FOOD, 1000), budget(ObjectId(), 500)], [])
    names = {r["name"]: r for r in out["budgets"]}
    assert names["Food"]["spent"] == 0 and names["Food"]["status"] == "ok"
    assert "Deleted category" in names  # a budget never crashes the page if its category vanished


def test_unbudgeted_categories_get_suggestions():
    out = status([budget(FOOD, 1000)], [tx(1, 100), tx(2, 1234, SHOP), tx(3, 50, None)],
                 history=({str(SHOP): 2480.0}, 3000.0))
    assert [u["name"] for u in out["unbudgeted"]] == ["Shopping"]  # budgeted and uncategorised are left out
    assert out["unbudgeted"][0]["suggested_limit"] == 2500  # history average rounded up to a 100
    assert out["suggested_overall"] == 3000


def test_projection_only_for_current_month_after_a_week():
    cur = datetime(2026, 5, 1)
    spend, total = spend_by_category([tx(1, 3100)])
    kw = dict(categories=CATS, month=cur, history={}, history_total=0.0)
    b = [budget(FOOD, 5000)]
    early = budget_status(b, spend, total, today=date(2026, 5, 5), **kw)["budgets"][0]
    assert early["projected"] is None  # too early to be meaningful
    mid = budget_status(b, spend, total, today=date(2026, 5, 10), **kw)["budgets"][0]
    assert mid["projected"] == 9610.0 and mid["projected_over"] is True and mid["status"] == "ok"
    assert mid["daily_allowance"] == pytest.approx(1900 / 21, abs=0.01)
    past = budget_status(b, spend, total, today=date(2026, 7, 1), **kw)
    assert past["budgets"][0]["projected"] is None and past["month"]["is_current"] is False
    assert past["budgets"][0]["daily_allowance"] is None and past["month"]["days_left"] == 0


def test_summary_counts():
    out = status([budget(None, 10_000), budget(FOOD, 100), budget(SHOP, 1000)], [tx(1, 500), tx(2, 900, SHOP)])
    assert out["summary"] == {"over": 1, "warning": 1, "ok": 1}


def test_history_average_ignores_empty_months():
    past = [tx(3, 600, month=2), tx(4, 200, SHOP, month=2), tx(5, 400, month=4)]  # no spending in March
    by_cat, total = history_average(past)
    assert by_cat[str(FOOD)] == 500 and by_cat[str(SHOP)] == 100 and total == 600
    assert history_average([]) == ({}, 0.0)


def test_history_window_is_three_full_months_before():
    start, end = history_window(datetime(2026, 1, 1))
    assert start == datetime(2025, 10, 1) and end == datetime(2025, 12, 31)


# ------------------------------------------------------------------ API
async def food_id(client, auth):
    return next(c["id"] for c in (await client.get("/api/categories", headers=auth)).json() if c["name"] == "Food & Dining")


async def imported_month(client, auth, sample):
    await import_file(client, auth, sample("hdfc_statement.csv"))
    m = (await client.get("/api/analytics/periods", headers=auth)).json()["latest"]
    return {"month": m["month"], "year": m["year"]}


async def test_budget_crud_and_status(client, auth, sample):
    q = await imported_month(client, auth, sample)
    fid = await food_id(client, auth)

    empty = (await client.get("/api/budgets/status", params=q, headers=auth)).json()
    assert empty["overall"] is None and empty["budgets"] == []
    spent = next(u["spent"] for u in empty["unbudgeted"] if u["category_id"] == fid)
    assert spent > 0 and empty["total_spent"] > 0 and empty["month"]["label"]

    r = await client.put("/api/budgets", headers=auth, json={"category_id": fid, "monthly_limit": 1000})
    assert r.status_code == 200 and r.json()["alert_threshold"] == 80
    s = (await client.get("/api/budgets/status", params=q, headers=auth)).json()
    row = s["budgets"][0]
    assert row["name"] == "Food & Dining" and row["spent"] == spent and row["monthly_limit"] == 1000
    assert all(u["category_id"] != fid for u in s["unbudgeted"])  # now budgeted

    # PUT again replaces rather than duplicating
    await client.put("/api/budgets", headers=auth, json={"category_id": fid, "monthly_limit": 999_999, "alert_threshold": 90})
    s = (await client.get("/api/budgets/status", params=q, headers=auth)).json()
    assert len(s["budgets"]) == 1 and s["budgets"][0]["monthly_limit"] == 999_999 and s["budgets"][0]["status"] == "ok"
    assert s["budgets"][0]["alert_threshold"] == 90

    await client.put("/api/budgets", headers=auth, json={"category_id": None, "monthly_limit": 1})
    s = (await client.get("/api/budgets/status", params=q, headers=auth)).json()
    assert s["overall"]["status"] == "over" and s["summary"]["over"] == 1

    assert (await client.delete(f"/api/budgets/{row['id']}", headers=auth)).status_code == 200
    assert (await client.delete(f"/api/budgets/{row['id']}", headers=auth)).status_code == 404
    s = (await client.get("/api/budgets/status", params=q, headers=auth)).json()
    assert s["budgets"] == [] and s["overall"] is not None


async def test_budget_validation(client, auth):
    fid = await food_id(client, auth)
    for body in ({"category_id": fid, "monthly_limit": 0}, {"category_id": fid, "monthly_limit": -5},
                 {"category_id": fid, "monthly_limit": 10**9}, {"category_id": fid, "monthly_limit": 100, "alert_threshold": 20},
                 {"category_id": fid, "monthly_limit": 100, "alert_threshold": 101}, {"category_id": fid}):
        assert (await client.put("/api/budgets", headers=auth, json=body)).status_code == 422, body
    assert (await client.put("/api/budgets", headers=auth, json={"category_id": "nope", "monthly_limit": 5})).status_code == 400
    assert (await client.put("/api/budgets", headers=auth, json={"category_id": str(ObjectId()), "monthly_limit": 5})).status_code == 404
    assert (await client.get("/api/budgets/status", params={"month": 5}, headers=auth)).status_code == 400
    assert (await client.get("/api/budgets/status", params={"month": 13, "year": 2026}, headers=auth)).status_code == 422
    assert (await client.delete("/api/budgets/nope", headers=auth)).status_code == 400


async def test_status_defaults_to_current_month_and_requires_auth(client, auth):
    r = await client.get("/api/budgets/status", headers=auth)
    assert r.status_code == 200 and r.json()["month"]["is_current"] is True
    assert (await client.get("/api/budgets/status")).status_code == 401
    assert (await client.put("/api/budgets", json={"monthly_limit": 5})).status_code == 401


async def test_budgets_are_private_to_each_user(client, auth):
    other = await register(client, "other@example.com")
    r = await client.put("/api/budgets", headers=auth, json={"category_id": None, "monthly_limit": 500})
    assert (await client.get("/api/budgets/status", headers=other)).json()["overall"] is None
    assert (await client.delete(f"/api/budgets/{r.json()['id']}", headers=other)).status_code == 404
    # a category belonging to someone else can't be budgeted either
    their_cat = await food_id(client, auth)
    assert (await client.put("/api/budgets", headers=other, json={"category_id": their_cat, "monthly_limit": 5})).status_code == 404
    assert (await client.get("/api/budgets/status", headers=auth)).json()["overall"]["monthly_limit"] == 500


async def test_deleting_a_category_removes_its_budget(client, auth):
    fid = await food_id(client, auth)
    await client.put("/api/budgets", headers=auth, json={"category_id": fid, "monthly_limit": 100})
    assert (await client.delete(f"/api/categories/{fid}", headers=auth)).status_code == 200
    assert (await client.get("/api/budgets/status", headers=auth)).json()["budgets"] == []


async def test_budgets_in_export_and_survive_data_delete_but_not_account_delete(client, auth, db, sample):
    await imported_month(client, auth, sample)
    await client.put("/api/budgets", headers=auth, json={"category_id": None, "monthly_limit": 12345})
    exported = (await client.get("/api/settings/export", headers=auth)).json()
    assert [b["monthly_limit"] for b in exported["budgets"]] == [12345]

    await client.delete("/api/settings/data", headers=auth)  # wipes statements, keeps setup
    assert (await client.get("/api/budgets/status", headers=auth)).json()["overall"]["monthly_limit"] == 12345

    r = await client.request("DELETE", "/api/settings/account", headers=auth, json={"password": "secret123"})
    assert r.status_code == 200, r.text
    assert await db["budgets"].count_documents({}) == 0
