"""First-run checklist: steps tick off from real data; what the user dismissed is remembered."""
import pytest

from tests.conftest import register
from tests.test_api import import_file

KEYS = ["statement", "account", "review", "budget"]
# two merchants no default rule recognises, so they land in "Other" and are flagged for review
UNSORTED = (
    "Posting Date,Transaction Details,Amount,Running Balance\n"
    "2025-08-01,SALARY ACME TECHNOLOGIES,50000.00,60000.00\n"
    "2025-08-03,ZXQV QWERTY 4412,-700.00,59300.00\n"
    "2025-08-04,PLUGH XYZZY 9921,-350.00,58950.00\n"
).encode()


async def get(client, auth):
    r = await client.get("/api/onboarding", headers=auth)
    assert r.status_code == 200, r.text
    return r.json()


def done(o):
    return {s["key"]: s["done"] for s in o["steps"]}


async def test_a_new_account_starts_from_the_beginning(client, auth):
    o = await get(client, auth)
    assert [s["key"] for s in o["steps"]] == KEYS and done(o) == dict.fromkeys(KEYS, False)
    assert (o["completed"], o["total"], o["welcome_seen"], o["checklist_dismissed"], o["show_checklist"]) == (0, 4, False, False, True)
    assert all(s["title"] and s["description"] and s["href"].startswith("/") for s in o["steps"])
    assert [s["href"] for s in o["steps"]] == ["/upload", "/accounts", "/transactions?needs_review=true", "/budgets"]


async def test_requires_sign_in(client):
    assert (await client.get("/api/onboarding")).status_code == 401
    assert (await client.patch("/api/onboarding", json={"welcome_seen": True})).status_code == 401


async def test_importing_a_statement_ticks_the_first_step_and_counts_what_needs_review(client, auth):
    await import_file(client, auth, UNSORTED, "unsorted.csv")
    o = await get(client, auth)
    assert done(o) == {"statement": True, "account": False, "review": False, "budget": False}
    waiting = (await client.get("/api/transactions", headers=auth, params={"needs_review": "true", "page_size": 1})).json()["total"]
    assert waiting == 2
    review = next(s for s in o["steps"] if s["key"] == "review")
    assert f"{waiting:,} transaction" in review["description"]


async def test_someone_who_already_has_data_is_not_given_the_welcome_tour(client, auth, sample):
    assert (await get(client, auth))["welcome_seen"] is False
    await import_file(client, auth, sample("hdfc_statement.csv"))
    assert (await get(client, auth))["welcome_seen"] is True


async def test_filing_a_statement_under_an_account_ticks_the_account_step(client, auth, sample):
    acc = (await client.post("/api/accounts", headers=auth, json={"name": "HDFC Savings"})).json()
    assert done(await get(client, auth))["account"] is False                 # an empty account is not enough
    up = await client.post("/api/statements/preview", headers=auth, files={"file": ("h.csv", sample("hdfc_statement.csv"), "text/csv")})
    await client.post(f"/api/statements/{up.json()['upload']['id']}/confirm", headers=auth, json={})
    assert done(await get(client, auth))["account"] is False                 # imported but not filed
    await client.put(f"/api/statements/{up.json()['upload']['id']}/account", headers=auth, json={"account_id": acc["id"]})
    assert done(await get(client, auth))["account"] is True


async def test_a_budget_ticks_the_budget_step(client, auth):
    await client.put("/api/budgets", headers=auth, json={"category_id": None, "monthly_limit": 50000})
    assert done(await get(client, auth))["budget"] is True


async def test_review_is_done_only_once_nothing_is_left_to_categorise(client, auth):
    await import_file(client, auth, UNSORTED, "unsorted.csv")
    items = (await client.get("/api/transactions", headers=auth, params={"needs_review": "true", "page_size": 200})).json()["items"]
    cat = next(c for c in (await client.get("/api/categories", headers=auth)).json() if c["name"] == "Shopping")
    assert len(items) == 2 and done(await get(client, auth))["review"] is False
    await client.post("/api/transactions/bulk-category", headers=auth, json={"transaction_ids": [t["id"] for t in items], "category_id": cat["id"]})
    o = await get(client, auth)
    assert done(o)["review"] is True
    assert "check anything Tally could not categorise" in next(s for s in o["steps"] if s["key"] == "review")["description"]


async def test_review_is_not_done_for_an_empty_account(client, auth):
    assert done(await get(client, auth))["review"] is False  # nothing to review is not the same as having reviewed


async def test_finishing_every_step_retires_the_checklist(client, auth):
    acc = (await client.post("/api/accounts", headers=auth, json={"name": "HDFC Savings"})).json()
    r = await client.post("/api/statements/preview", headers=auth, files={"file": ("u.csv", UNSORTED, "text/csv")})
    await client.post(f"/api/statements/{r.json()['upload']['id']}/confirm", headers=auth, json={"account_id": acc["id"]})
    items = (await client.get("/api/transactions", headers=auth, params={"needs_review": "true", "page_size": 200})).json()["items"]
    cat = next(c for c in (await client.get("/api/categories", headers=auth)).json() if c["name"] == "Shopping")
    await client.post("/api/transactions/bulk-category", headers=auth, json={"transaction_ids": [t["id"] for t in items], "category_id": cat["id"]})
    await client.put("/api/budgets", headers=auth, json={"category_id": None, "monthly_limit": 50000})
    o = await get(client, auth)
    assert (o["completed"], o["show_checklist"]) == (4, False) and all(done(o).values())


async def test_progress_follows_the_data(client, auth, sample):
    await import_file(client, auth, sample("hdfc_statement.csv"))
    assert done(await get(client, auth))["statement"] is True
    await client.delete("/api/settings/data", headers=auth)
    assert done(await get(client, auth))["statement"] is False


async def test_dismissals_are_remembered(client, auth):
    r = await client.patch("/api/onboarding", headers=auth, json={"welcome_seen": True})
    assert r.status_code == 200 and r.json()["welcome_seen"] is True and r.json()["show_checklist"] is True
    assert (await get(client, auth))["welcome_seen"] is True
    r = await client.patch("/api/onboarding", headers=auth, json={"checklist_dismissed": True})
    assert (r.json()["checklist_dismissed"], r.json()["show_checklist"], r.json()["welcome_seen"]) == (True, False, True)
    r = await client.patch("/api/onboarding", headers=auth, json={"checklist_dismissed": False})   # it can be brought back
    assert r.json()["show_checklist"] is True


async def test_an_empty_update_changes_nothing(client, auth):
    before = await get(client, auth)
    assert (await client.patch("/api/onboarding", headers=auth, json={})).json() == before


async def test_an_explicit_choice_beats_the_default(client, auth, sample):
    await client.patch("/api/onboarding", headers=auth, json={"welcome_seen": False})
    await import_file(client, auth, sample("hdfc_statement.csv"))
    assert (await get(client, auth))["welcome_seen"] is False


@pytest.mark.parametrize("body", [{"welcome_seen": "maybe"}, {"checklist_dismissed": [1]}, {"welcome_seen": {"a": 1}}])
async def test_bad_updates_are_rejected(client, auth, body):
    assert (await client.patch("/api/onboarding", headers=auth, json=body)).status_code == 422


async def test_each_user_has_their_own_progress(client, auth, sample):
    await client.patch("/api/onboarding", headers=auth, json={"welcome_seen": True, "checklist_dismissed": True})
    await import_file(client, auth, sample("hdfc_statement.csv"))
    other = await register(client, "other@example.com")
    o = await get(client, other)
    assert (o["welcome_seen"], o["checklist_dismissed"], done(o)["statement"]) == (False, False, False)
