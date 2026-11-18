"""Accounts: creating them, filing statements under them, and viewing money per account or combined."""
import csv
import io

import pytest
from openpyxl import load_workbook
from pypdf import PdfReader

from app.parsers.registry import parse_statement
from tests.conftest import register
from tests.test_api import import_file, upload


async def new_account(client, auth, name="HDFC Savings", **extra):
    r = await client.post("/api/accounts", headers=auth, json={"name": name, **extra})
    assert r.status_code == 201, r.text
    return r.json()


async def import_to(client, auth, content, name, account_id=None):
    r = await upload(client, auth, content, name)
    assert r.status_code == 201, r.text
    body = {"account_id": account_id} if account_id else {}
    c = await client.post(f"/api/statements/{r.json()['upload']['id']}/confirm", headers=auth, json=body)
    assert c.status_code == 200, c.text
    return c.json()


async def summaries(client, auth):
    r = await client.get("/api/accounts", headers=auth)
    assert r.status_code == 200
    return r.json()


async def txns(client, auth, **params):
    r = await client.get("/api/transactions", headers=auth, params={"page_size": 200, **params})
    assert r.status_code == 200, r.text
    return r.json()


async def dash(client, auth, **params):
    return (await client.get("/api/analytics/dashboard", headers=auth, params={"month": 10, "year": 2025, **params})).json()["totals"]


# ------------------------------------------------------------------ creating and editing
async def test_create_edit_and_delete(client, auth):
    a = await new_account(client, auth, "  HDFC Savings  ", bank_name="HDFC Bank", last4="1234")
    assert (a["name"], a["account_type"], a["bank_name"], a["last4"]) == ("HDFC Savings", "bank", "HDFC Bank", "1234")
    b = await new_account(client, auth, "SBI Salary", account_type="credit_card")
    assert b["account_type"] == "credit_card" and b["color"] != a["color"]  # each account gets its own colour

    r = await client.patch(f"/api/accounts/{a['id']}", headers=auth, json={"name": "HDFC Salary", "color": "#2A78D6"})
    assert (r.json()["name"], r.json()["color"], r.json()["last4"]) == ("HDFC Salary", "#2A78D6", "1234")
    r = await client.patch(f"/api/accounts/{a['id']}", headers=auth, json={"last4": ""})
    assert r.json()["last4"] is None  # an empty string clears it

    assert (await client.delete(f"/api/accounts/{b['id']}", headers=auth)).status_code == 200
    assert [x["name"] for x in (await summaries(client, auth))["accounts"]] == ["HDFC Salary"]


@pytest.mark.parametrize("body", [
    {"name": ""}, {"name": "   "}, {"name": "x" * 61}, {"name": "A", "last4": "123"}, {"name": "A", "last4": "12345"},
    {"name": "A", "last4": "12ab"}, {"name": "A", "color": "green"}, {"name": "A", "account_type": "wallet"}, {},
])
async def test_validation(client, auth, body):
    assert (await client.post("/api/accounts", headers=auth, json=body)).status_code == 422


async def test_names_are_unique_per_user_ignoring_case(client, auth):
    a = await new_account(client, auth, "HDFC Savings")
    r = await client.post("/api/accounts", headers=auth, json={"name": "hdfc savings"})
    assert r.status_code == 409 and "already have an account" in r.json()["error"]["message"]
    b = await new_account(client, auth, "SBI Salary")
    r = await client.patch(f"/api/accounts/{b['id']}", headers=auth, json={"name": "HDFC SAVINGS"})
    assert r.status_code == 409
    await client.patch(f"/api/accounts/{a['id']}", headers=auth, json={"name": "HDFC savings"})  # renaming to itself is fine
    other = await register(client, "other@example.com")
    await new_account(client, other, "HDFC Savings")  # another user may use the same name


async def test_auth_and_ids(client, auth):
    assert (await client.get("/api/accounts")).status_code == 401
    assert (await client.post("/api/accounts", json={"name": "A"})).status_code == 401
    assert (await client.patch("/api/accounts/nope", headers=auth, json={"name": "A"})).status_code == 400
    assert (await client.delete("/api/accounts/000000000000000000000000", headers=auth)).status_code == 404


async def test_accounts_are_private(client, auth, sample):
    a = await new_account(client, auth)
    other = await register(client, "other@example.com")
    assert (await summaries(client, other))["accounts"] == []
    assert (await client.patch(f"/api/accounts/{a['id']}", headers=other, json={"name": "Mine"})).status_code == 404
    assert (await client.delete(f"/api/accounts/{a['id']}", headers=other)).status_code == 404
    r = await upload(client, other, sample("hdfc_statement.csv"))  # cannot file a statement under someone else's account
    c = await client.post(f"/api/statements/{r.json()['upload']['id']}/confirm", headers=other, json={"account_id": a["id"]})
    assert c.status_code == 404


# ------------------------------------------------------------------ filing statements
async def test_confirming_with_an_account_files_the_statement_and_its_transactions(client, auth, sample):
    a = await new_account(client, auth, bank_name="HDFC Bank")
    done = await import_to(client, auth, sample("hdfc_statement.csv"), "hdfc.csv", a["id"])
    assert done["account_id"] == a["id"]
    items = (await txns(client, auth))["items"]
    assert items and {t["account_id"] for t in items} == {a["id"]}
    assert [s["account_id"] for s in (await client.get("/api/statements", headers=auth)).json()] == [a["id"]]


async def test_confirming_without_an_account_leaves_it_unassigned(client, auth, sample):
    await import_to(client, auth, sample("hdfc_statement.csv"), "hdfc.csv")
    assert {t["account_id"] for t in (await txns(client, auth))["items"]} == {None}


async def test_statement_and_account_must_be_the_same_kind(client, auth, sample):
    bank = await new_account(client, auth, "HDFC Savings")
    card = await new_account(client, auth, "HDFC Card", account_type="credit_card")
    r = await upload(client, auth, sample("hdfc_credit_card.csv"), "card.csv")
    up = r.json()["upload"]["id"]
    bad = await client.post(f"/api/statements/{up}/confirm", headers=auth, json={"account_id": bank["id"]})
    assert bad.status_code == 400 and bad.json()["error"]["code"] == "account_type_mismatch"
    assert "credit card" in bad.json()["error"]["message"]
    ok = await client.post(f"/api/statements/{up}/confirm", headers=auth, json={"account_id": card["id"]})  # still importable
    assert ok.status_code == 200 and ok.json()["account_id"] == card["id"]


async def test_unknown_account_ids_are_refused_and_nothing_is_imported(client, auth, sample):
    r = await upload(client, auth, sample("hdfc_statement.csv"), "hdfc.csv")
    up = r.json()["upload"]["id"]
    for bad, code in (("nope", 400), ("000000000000000000000000", 404)):
        assert (await client.post(f"/api/statements/{up}/confirm", headers=auth, json={"account_id": bad})).status_code == code
    assert (await txns(client, auth))["total"] == 0


async def test_suggestion_is_the_only_matching_account(client, auth, sample):
    r = await upload(client, auth, sample("hdfc_statement.csv"), "hdfc.csv")
    assert r.json()["suggested_account_id"] is None                       # no accounts yet
    await client.delete(f"/api/statements/{r.json()['upload']['id']}/preview", headers=auth)

    hdfc = await new_account(client, auth, "HDFC Savings", bank_name="HDFC Bank")
    await new_account(client, auth, "ICICI Salary", bank_name="ICICI Bank")
    r = await upload(client, auth, sample("hdfc_statement.csv"), "hdfc.csv")
    assert r.json()["suggested_account_id"] == hdfc["id"]
    await client.delete(f"/api/statements/{r.json()['upload']['id']}/preview", headers=auth)

    await new_account(client, auth, "HDFC Joint", bank_name="hdfc bank")  # two candidates: don't guess
    r = await upload(client, auth, sample("hdfc_statement.csv"), "hdfc.csv")
    assert r.json()["suggested_account_id"] is None


async def test_a_card_statement_is_not_suggested_a_bank_account(client, auth, sample):
    await new_account(client, auth, "HDFC Savings", bank_name="HDFC Bank Credit Card")  # a bank account, whatever its label
    r = await upload(client, auth, sample("hdfc_credit_card.csv"), "card.csv")
    assert r.json()["suggested_account_id"] is None
    card = await new_account(client, auth, "My card", account_type="credit_card", bank_name="HDFC Bank Credit Card")
    await client.delete(f"/api/statements/{r.json()['upload']['id']}/preview", headers=auth)
    r = await upload(client, auth, sample("hdfc_credit_card.csv"), "card.csv")
    assert r.json()["suggested_account_id"] == card["id"]


async def test_moving_a_statement_moves_its_transactions(client, auth, sample):
    a = await new_account(client, auth, "A")
    b = await new_account(client, auth, "B")
    done = await import_to(client, auth, sample("hdfc_statement.csv"), "hdfc.csv", a["id"])
    n = done["transaction_count"]
    r = await client.put(f"/api/statements/{done['id']}/account", headers=auth, json={"account_id": b["id"]})
    assert r.status_code == 200 and r.json() == {"account_id": b["id"], "moved_transactions": n}
    assert (await txns(client, auth, account_id=a["id"]))["total"] == 0
    assert (await txns(client, auth, account_id=b["id"]))["total"] == n
    r = await client.put(f"/api/statements/{done['id']}/account", headers=auth, json={"account_id": None})
    assert r.json()["account_id"] is None
    assert (await txns(client, auth, account_id="none"))["total"] == n


async def test_moving_validates(client, auth, sample):
    bank = await new_account(client, auth, "Bank")
    card = await new_account(client, auth, "Card", account_type="credit_card")
    done = await import_to(client, auth, sample("hdfc_statement.csv"), "hdfc.csv", bank["id"])
    assert (await client.put(f"/api/statements/{done['id']}/account", headers=auth, json={"account_id": card["id"]})).status_code == 400
    assert (await client.put("/api/statements/000000000000000000000000/account", headers=auth, json={"account_id": None})).status_code == 404
    other = await register(client, "other@example.com")
    assert (await client.put(f"/api/statements/{done['id']}/account", headers=other, json={"account_id": None})).status_code == 404
    assert (await txns(client, auth, account_id=bank["id"]))["total"] == done["transaction_count"]  # untouched


async def test_deleting_an_account_keeps_the_data(client, auth, sample):
    a = await new_account(client, auth)
    done = await import_to(client, auth, sample("hdfc_statement.csv"), "hdfc.csv", a["id"])
    r = await client.delete(f"/api/accounts/{a['id']}", headers=auth)
    assert r.json() == {"unassigned_statements": 1, "unassigned_transactions": done["transaction_count"]}
    assert (await txns(client, auth, account_id="none"))["total"] == done["transaction_count"]
    s = await summaries(client, auth)
    assert s["accounts"] == [] and s["unassigned"]["transaction_count"] == done["transaction_count"] and s["unassigned"]["statement_count"] == 1


# ------------------------------------------------------------------ viewing per account or combined
async def two_accounts(client, auth, sample):
    a = await new_account(client, auth, "HDFC Savings", bank_name="HDFC Bank")
    b = await new_account(client, auth, "ICICI Salary", bank_name="ICICI Bank")
    await import_to(client, auth, sample("hdfc_statement.csv"), "hdfc.csv", a["id"])
    await import_to(client, auth, sample("icici_statement.csv"), "icici.csv", b["id"])
    return a, b


async def test_account_totals_add_up_to_the_combined_totals(client, auth, sample):
    a, b = await two_accounts(client, auth, sample)
    both, ta, tb = await dash(client, auth), await dash(client, auth, account_id=a["id"]), await dash(client, auth, account_id=b["id"])
    assert ta["transaction_count"] and tb["transaction_count"]
    for key in ("total_income", "total_expenses", "transaction_count", "upi_spending"):
        assert ta[key] + tb[key] == pytest.approx(both[key]), key
    assert ta["total_expenses"] != tb["total_expenses"]                 # they really are different accounts


async def test_every_filter_honours_the_account(client, auth, sample):
    a, b = await two_accounts(client, auth, sample)
    ta = await txns(client, auth, account_id=a["id"])
    tb = await txns(client, auth, account_id=b["id"])
    assert ta["total"] + tb["total"] == (await txns(client, auth))["total"]
    assert {t["account_id"] for t in ta["items"]} == {a["id"]}
    assert (await txns(client, auth, account_id="none"))["total"] == 0
    for path in ("/api/analytics/overview", "/api/analytics/insights", "/api/upi/summary", "/api/anomalies"):
        assert (await client.get(path, headers=auth, params={"account_id": a["id"]})).status_code == 200, path
    # a different user's account id matches nothing rather than leaking data
    other = await register(client, "other@example.com")
    assert (await txns(client, other, account_id=a["id"]))["total"] == 0
    assert (await client.get("/api/transactions", headers=auth, params={"account_id": "nope"})).status_code == 400


async def test_anomalies_only_involve_the_selected_accounts_transactions(client, auth, sample):
    a, b = await two_accounts(client, auth, sample)
    mine = {x: {t["id"] for t in (await txns(client, auth, account_id=x))["items"]} for x in (a["id"], b["id"])}
    found = {}
    for key in (a["id"], b["id"]):
        items = (await client.get("/api/anomalies", headers=auth, params={"account_id": key})).json()["items"]
        found[key] = {t["id"] for x in items for t in x["transactions"]}
    assert found[a["id"]] and found[b["id"]]                       # both statements contain deliberate anomalies
    assert found[a["id"]] <= mine[a["id"]] and found[b["id"]] <= mine[b["id"]]


async def test_balances_and_latest_month_per_account(client, auth, sample):
    a, b = await two_accounts(client, auth, sample)
    s = await summaries(client, auth)
    rows = {r["name"]: r for r in s["accounts"]}
    parsed, _ = parse_statement(sample("hdfc_statement.csv"), "csv")
    last_row = max(parsed.transactions, key=lambda t: t.transaction_date)  # the final row of the statement
    hdfc = rows["HDFC Savings"]
    assert hdfc["balance"] == {"amount": last_row.balance, "as_of": last_row.transaction_date.strftime("%Y-%m-%d")}
    assert hdfc["statement_count"] == 1 and hdfc["transaction_count"] == len(parsed.transactions)
    assert hdfc["date_range"]["end"] == hdfc["balance"]["as_of"] and hdfc["bank_name"] == "HDFC Bank"
    month = hdfc["latest_month"]
    assert month["label"] == "October 2025" and month["money_out"] > 0 and month["money_in"] > 0
    assert s["totals"]["bank_balance"] == pytest.approx(sum(r["balance"]["amount"] for r in rows.values()))
    assert (s["totals"]["bank_account_count"], s["totals"]["bank_accounts_with_balance"], s["totals"]["card_count"]) == (2, 2, 0)
    assert s["unassigned"] is None


async def test_card_accounts_have_no_balance_and_stay_out_of_the_bank_total(client, auth, sample):
    bank = await new_account(client, auth, "HDFC Savings")
    card = await new_account(client, auth, "HDFC Card", account_type="credit_card")
    await import_to(client, auth, sample("hdfc_statement.csv"), "hdfc.csv", bank["id"])
    await import_to(client, auth, sample("hdfc_credit_card.csv"), "card.csv", card["id"])
    s = await summaries(client, auth)
    rows = {r["name"]: r for r in s["accounts"]}
    assert rows["HDFC Card"]["balance"] is None and rows["HDFC Card"]["transaction_count"] == 34
    assert rows["HDFC Card"]["latest_month"]["money_out"] == pytest.approx(35228.22)
    assert s["totals"]["bank_balance"] == rows["HDFC Savings"]["balance"]["amount"]
    assert (s["totals"]["bank_account_count"], s["totals"]["card_count"]) == (1, 1)


async def test_empty_accounts_are_listed_without_activity(client, auth):
    await new_account(client, auth, "Brand new")
    r = (await summaries(client, auth))["accounts"][0]
    assert (r["transaction_count"], r["statement_count"], r["balance"], r["latest_month"]) == (0, 0, None, None)


# ------------------------------------------------------------------ setting accounts up from existing statements
async def test_auto_setup_files_existing_statements_by_bank(client, auth, sample):
    await import_file(client, auth, sample("hdfc_statement.csv"), "hdfc.csv")
    await import_file(client, auth, sample("icici_statement.csv"), "icici.csv")
    await import_file(client, auth, sample("hdfc_credit_card.csv"), "card.csv")
    r = await client.post("/api/accounts/auto-setup", headers=auth)
    assert r.json() == {"created_accounts": 3, "assigned_statements": 3}
    rows = {x["name"]: x for x in (await summaries(client, auth))["accounts"]}
    assert set(rows) == {"HDFC Bank", "ICICI Bank", "HDFC Bank Credit Card"}
    assert rows["HDFC Bank Credit Card"]["account_type"] == "credit_card" and rows["HDFC Bank"]["account_type"] == "bank"
    assert all(x["statement_count"] == 1 for x in rows.values()) and (await summaries(client, auth))["unassigned"] is None
    assert (await client.post("/api/accounts/auto-setup", headers=auth)).json() == {"created_accounts": 0, "assigned_statements": 0}


async def test_auto_setup_reuses_an_account_with_the_bank_name(client, auth, sample):
    existing = await new_account(client, auth, "HDFC Bank")
    await import_file(client, auth, sample("hdfc_statement.csv"), "hdfc.csv")
    await import_file(client, auth, sample("icici_statement.csv"), "icici.csv")
    assert (await client.post("/api/accounts/auto-setup", headers=auth)).json() == {"created_accounts": 1, "assigned_statements": 2}
    assert (await txns(client, auth, account_id=existing["id"]))["total"] > 0


async def test_auto_setup_never_mixes_a_card_into_a_bank_account(client, auth, sample):
    await new_account(client, auth, "HDFC Bank Credit Card")  # a *bank* account that happens to use the card's name
    await import_file(client, auth, sample("hdfc_credit_card.csv"), "card.csv")
    assert (await client.post("/api/accounts/auto-setup", headers=auth)).json() == {"created_accounts": 0, "assigned_statements": 0}
    assert (await summaries(client, auth))["unassigned"]["statement_count"] == 1


# ------------------------------------------------------------------ exports, reports, data rights
async def test_export_names_the_account(client, auth, sample):
    a, b = await two_accounts(client, auth, sample)
    r = await client.get("/api/transactions/export", headers=auth, params={"account_id": a["id"]})
    rows = list(csv.reader(io.StringIO(r.content.decode("utf-8-sig"))))
    col = rows[0].index("Account")
    assert rows[0][col - 1] == "Bank" and {x[col] for x in rows[1:]} == {"HDFC Savings"}
    wb = load_workbook(io.BytesIO((await client.get("/api/transactions/export", headers=auth,
                                                     params={"account_id": b["id"], "format": "xlsx"})).content))
    assert {x.value: y.value for x, y in wb["About this export"].iter_rows()}["Account"] == "ICICI Salary"


async def test_pdf_report_names_the_account_and_skips_budgets(client, auth, sample):
    a, _ = await two_accounts(client, auth, sample)
    await client.put("/api/budgets", headers=auth, json={"category_id": None, "monthly_limit": 50000})
    q = {"month": 10, "year": 2025}
    whole = " ".join(" ".join(p.extract_text() for p in PdfReader(io.BytesIO((await client.get("/api/reports/summary.pdf", headers=auth, params=q)).content)).pages).split())
    one = " ".join(" ".join(p.extract_text() for p in PdfReader(io.BytesIO((await client.get("/api/reports/summary.pdf", headers=auth, params={**q, "account_id": a["id"]})).content)).pages).split())
    assert "Budgets - October 2025" in whole and "Account:" not in whole
    assert "Account: HDFC Savings" in one and "Budgets -" not in one  # budgets cover everything, so not beside one account


async def test_accounts_are_exported_kept_on_data_delete_and_removed_with_the_account(client, auth, db, sample):
    a = await new_account(client, auth, "HDFC Savings", last4="4321")
    await import_to(client, auth, sample("hdfc_statement.csv"), "hdfc.csv", a["id"])
    exported = (await client.get("/api/settings/export", headers=auth)).json()
    assert [(x["name"], x["last4"]) for x in exported["accounts"]] == [("HDFC Savings", "4321")]
    await client.delete("/api/settings/data", headers=auth)
    assert [x["name"] for x in (await summaries(client, auth))["accounts"]] == ["HDFC Savings"]  # setup survives a data wipe
    r = await client.request("DELETE", "/api/settings/account", headers=auth, json={"password": "secret123"})
    assert r.status_code == 200 and await db["accounts"].count_documents({}) == 0
