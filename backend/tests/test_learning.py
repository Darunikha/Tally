"""Learning from corrections: suggested rules, one-click rules, and merchants that need a category."""
import pytest
from bson import ObjectId

from app.categorization.engine import validate_pattern
from app.services.learning import LEARNED_PRIORITY, learnable, merchant_pattern, suggestion_after_correction
from tests.conftest import register
from tests.test_api import import_file

CSV = (
    "Posting Date,Transaction Details,Amount,Running Balance\n"
    "2025-08-01,SWIGGY ORDER 111,-300.00,9700.00\n"
    "2025-08-02,SWIGGY ORDER 222,-400.00,9300.00\n"
    "2025-08-03,SWIGGY ORDER 333,-500.00,8800.00\n"
    "2025-08-04,SWIGGY ORDER 444,-250.00,8550.00\n"
    "2025-08-05,SWIGGY REFUND 555,120.00,8670.00\n"
    "2025-08-06,ZOMATO ORDER 666,-350.00,8320.00\n"
    "2025-08-07,ZXQV QWERTY 1,-100.00,8220.00\n"
    "2025-08-08,ZXQV QWERTY 2,-200.00,8020.00\n"
    "2025-08-09,ZXQV QWERTY 3,-300.00,7720.00\n"
    "2025-08-10,PLUGH XYZZY 1,-50.00,7670.00\n"
).encode()


async def setup(client, auth):
    await import_file(client, auth, CSV, "learn.csv")


async def cat_id(client, auth, name):
    return next(c["id"] for c in (await client.get("/api/categories", headers=auth)).json() if c["name"] == name)


async def txns(client, auth, merchant=None, **params):
    if merchant:
        params["merchant"] = merchant
    r = await client.get("/api/transactions", headers=auth, params={"page_size": 200, "sort": "date", "order": "asc", **params})
    return r.json()["items"]


async def move(client, auth, txn_id, category_id):
    r = await client.patch(f"/api/transactions/{txn_id}", headers=auth, json={"category_id": category_id})
    assert r.status_code == 200, r.text
    return r.json()


async def swiggy_debits(client, auth):
    return [t for t in await txns(client, auth, "Swiggy") if t["transaction_type"] == "debit"]


# ------------------------------------------------------------------ the pattern
def test_pattern_matches_the_merchant_and_nothing_else():
    rx = validate_pattern(merchant_pattern("Swiggy"))
    assert rx.search("SWIGGY | SWIGGY ORDER 111")
    assert rx.search("swiggy | whatever".upper())
    assert not rx.search("SWIGGY INSTAMART | ORDER")           # a different merchant that starts the same
    assert not rx.search("ZOMATO | PAID VIA SWIGGY | X")       # a word in someone else's narration
    assert not rx.search("MYSWIGGY | X")


@pytest.mark.parametrize("name", ["A.B (C)+ [x]", "Tea & Co.", "R*D | Labs", "Cafe (Main St)", "50% Off $hop", "a\\b"])
def test_pattern_is_safe_for_awkward_merchant_names(name):
    rx = validate_pattern(merchant_pattern(name))                # never rejected, never a regex injection
    assert rx.search(f"{name.upper()} | DESC")
    assert not rx.search(f"X{name.upper()} | DESC")


def test_pattern_cannot_be_widened_by_the_merchant_name():
    rx = validate_pattern(merchant_pattern(".*"))
    assert not rx.search("SWIGGY | DESC")                       # ".*" is a literal name, not "match everything"


@pytest.mark.parametrize("value,ok", [("Swiggy", True), ("Priya S", True), ("Unknown", False), (" unknown ", False), ("", False),
                                      (None, False), ("x" * 121, False), ("x" * 120, True)])
def test_learnable(value, ok):
    assert learnable(value) is ok


# ------------------------------------------------------------------ offering a rule after a correction
async def test_a_correction_offers_to_remember_it(client, auth):
    await setup(client, auth)
    first, *others = await swiggy_debits(client, auth)
    groceries = await cat_id(client, auth, "Groceries")
    out = await move(client, auth, first["id"], groceries)
    s = out["suggestion"]
    assert (s["merchant"], s["category_id"], s["category_name"], s["applies_to"]) == ("Swiggy", groceries, "Groceries", "debit")
    assert s["similar_count"] == len(others) == 3                # the other debits, not the one just moved, not the refund


async def test_no_offer_when_nothing_would_be_learned(client, auth):
    await setup(client, auth)
    first, *_ = await swiggy_debits(client, auth)
    groceries, food = await cat_id(client, auth, "Groceries"), await cat_id(client, auth, "Food & Dining")
    r = await client.patch(f"/api/transactions/{first['id']}", headers=auth, json={"notes": "just a note"})
    assert r.json().get("suggestion") is None                    # no category change
    out = await move(client, auth, first["id"], groceries)
    assert out["suggestion"] is not None
    again = await move(client, auth, first["id"], groceries)     # moving to where it already is
    assert again.get("suggestion") is None
    back = await move(client, auth, first["id"], food)           # back to what the rules already say
    assert back["suggestion"] is None
    r = await client.patch(f"/api/transactions/{first['id']}", headers=auth, json={"reset_category": True})
    assert r.json().get("suggestion") is None


async def test_no_offer_when_a_rule_already_does_it(client, auth):
    await setup(client, auth)
    first, *_ = await swiggy_debits(client, auth)
    groceries = await cat_id(client, auth, "Groceries")
    await client.post("/api/rules/learn", headers=auth, json={"merchant": "Swiggy", "category_id": groceries, "applies_to": "debit"})
    other = (await swiggy_debits(client, auth))[1]
    entertainment = await cat_id(client, auth, "Entertainment")
    assert (await move(client, auth, other["id"], entertainment))["suggestion"] is not None   # against the rule: worth offering
    assert (await move(client, auth, other["id"], groceries))["suggestion"] is None           # with the rule: nothing to add


async def test_no_offer_for_an_unreadable_payee(client, db):
    uid = ObjectId()
    txn = {"_id": ObjectId(), "normalized_merchant": "Unknown", "transaction_type": "debit"}
    assert await suggestion_after_correction(db, uid, txn, {"_id": ObjectId(), "name": "Shopping"}) is None


async def test_the_offer_for_a_credit_is_for_credits(client, auth):
    await setup(client, auth)
    refund = next(t for t in await txns(client, auth, "Swiggy") if t["transaction_type"] == "credit")
    shopping = await cat_id(client, auth, "Shopping")
    s = (await move(client, auth, refund["id"], shopping))["suggestion"]
    assert s["applies_to"] == "credit" and s["similar_count"] == 0


# ------------------------------------------------------------------ making the rule
async def test_learning_a_rule_moves_the_merchants_other_transactions(client, auth):
    await setup(client, auth)
    first, second, *rest = await swiggy_debits(client, auth)
    groceries, entertainment = await cat_id(client, auth, "Groceries"), await cat_id(client, auth, "Entertainment")
    await move(client, auth, first["id"], groceries)
    await move(client, auth, second["id"], entertainment)       # a manual choice that must survive
    r = await client.post("/api/rules/learn", headers=auth, json={"merchant": "Swiggy", "category_id": groceries, "applies_to": "debit"})
    assert r.status_code == 200
    body = r.json()
    assert (body["created"], body["rule_name"], body["category_name"], body["recategorized"]) == (True, "Learned: Swiggy", "Groceries", len(rest))

    now = {t["id"]: t for t in await swiggy_debits(client, auth)}
    assert now[first["id"]]["category_name"] == "Groceries" and now[first["id"]]["manual_override"]
    assert now[second["id"]]["category_name"] == "Entertainment" and now[second["id"]]["manual_override"]   # your word stands
    for t in rest:
        assert now[t["id"]]["category_name"] == "Groceries" and now[t["id"]]["categorization_source"] == "custom_rule"
    zomato = (await txns(client, auth, "Zomato"))[0]
    assert zomato["category_name"] == "Food & Dining"             # other merchants are untouched


async def test_the_learned_rule_is_an_ordinary_visible_rule(client, auth):
    await setup(client, auth)
    groceries = await cat_id(client, auth, "Groceries")
    await client.post("/api/rules/learn", headers=auth, json={"merchant": "Swiggy", "category_id": groceries, "applies_to": "debit"})
    rule = next(r for r in (await client.get("/api/rules", headers=auth)).json() if r["rule_name"] == "Learned: Swiggy")
    assert (rule["priority"], rule["applies_to"], rule["enabled"], rule["is_default"]) == (LEARNED_PRIORITY, "debit", True, False)
    assert rule["regex_pattern"] == merchant_pattern("Swiggy") and rule["category_name"] == "Groceries"
    assert rule["match_count"] == 4
    assert all(rule["priority"] > r["priority"] for r in (await client.get("/api/rules", headers=auth)).json() if r["is_default"])
    assert (await client.patch(f"/api/rules/{rule['id']}", headers=auth, json={"enabled": False})).status_code == 200   # editable as any rule


async def test_teaching_the_same_merchant_again_changes_the_rule_instead_of_duplicating(client, auth):
    await setup(client, auth)
    groceries, shopping = await cat_id(client, auth, "Groceries"), await cat_id(client, auth, "Shopping")
    body = {"merchant": "Swiggy", "category_id": groceries, "applies_to": "debit"}
    assert (await client.post("/api/rules/learn", headers=auth, json=body)).json()["created"] is True
    second = (await client.post("/api/rules/learn", headers=auth, json={**body, "category_id": shopping})).json()
    assert second["created"] is False
    learned = [r for r in (await client.get("/api/rules", headers=auth)).json() if r["rule_name"].startswith("Learned: Swiggy")]
    assert len(learned) == 1 and learned[0]["category_name"] == "Shopping"
    assert {t["category_name"] for t in await swiggy_debits(client, auth)} == {"Shopping"}


async def test_re_enables_a_learned_rule_you_had_switched_off(client, auth):
    await setup(client, auth)
    groceries = await cat_id(client, auth, "Groceries")
    body = {"merchant": "Swiggy", "category_id": groceries, "applies_to": "debit"}
    await client.post("/api/rules/learn", headers=auth, json=body)
    rule = next(r for r in (await client.get("/api/rules", headers=auth)).json() if r["rule_name"] == "Learned: Swiggy")
    await client.patch(f"/api/rules/{rule['id']}", headers=auth, json={"enabled": False})
    await client.post("/api/rules/apply", headers=auth)                     # switching a rule off takes effect when rules are re-applied
    assert {t["category_name"] for t in await swiggy_debits(client, auth)} == {"Food & Dining"}
    again = (await client.post("/api/rules/learn", headers=auth, json=body)).json()
    assert again["created"] is False                                        # the same rule, switched back on
    assert {t["category_name"] for t in await swiggy_debits(client, auth)} == {"Groceries"}


async def test_a_debit_rule_leaves_refunds_alone_and_a_both_rule_does_not(client, auth):
    await setup(client, auth)
    shopping = await cat_id(client, auth, "Shopping")
    refund = lambda: next(t for t in client_txns if t["transaction_type"] == "credit")  # noqa: E731
    await client.post("/api/rules/learn", headers=auth, json={"merchant": "Swiggy", "category_id": shopping, "applies_to": "debit"})
    client_txns = await txns(client, auth, "Swiggy")
    assert refund()["category_name"] == "Income"                  # the refund keeps the category the rules gave it
    await client.post("/api/rules/learn", headers=auth, json={"merchant": "Swiggy", "category_id": shopping, "applies_to": "any"})
    client_txns = await txns(client, auth, "Swiggy")
    assert refund()["category_name"] == "Shopping"


async def test_future_statements_use_what_you_taught(client, auth):
    await setup(client, auth)
    groceries = await cat_id(client, auth, "Groceries")
    await client.post("/api/rules/learn", headers=auth, json={"merchant": "Swiggy", "category_id": groceries, "applies_to": "debit"})
    later = (b"Posting Date,Transaction Details,Amount,Running Balance\n"
             b"2025-09-01,SWIGGY ORDER 999,-640.00,5000.00\n2025-09-02,ZOMATO ORDER 998,-210.00,4790.00\n")
    await import_file(client, auth, later, "september.csv")
    sept = [t for t in await txns(client, auth) if t["transaction_date"].startswith("2025-09")]
    by = {t["normalized_merchant"]: t for t in sept}
    assert (by["Swiggy"]["category_name"], by["Swiggy"]["categorization_source"]) == ("Groceries", "custom_rule")
    assert by["Zomato"]["category_name"] == "Food & Dining"


async def test_learning_refreshes_the_summaries(client, auth):
    await setup(client, auth)
    groceries = await cat_id(client, auth, "Groceries")
    before = (await client.get("/api/analytics/dashboard", headers=auth, params={"month": 8, "year": 2025})).json()["category_breakdown"]
    await client.post("/api/rules/learn", headers=auth, json={"merchant": "Swiggy", "category_id": groceries, "applies_to": "debit"})
    after = {c["name"]: c["amount"] for c in (await client.get("/api/analytics/dashboard", headers=auth, params={"month": 8, "year": 2025})).json()["category_breakdown"]}
    assert after["Groceries"] == 1450 and "Food & Dining" in after and {c["name"] for c in before} >= {"Food & Dining"}


@pytest.mark.parametrize("body,status", [
    ({"merchant": "", "category_id": "x"}, 422), ({"merchant": "x" * 121, "category_id": "x"}, 422),
    ({"merchant": "Swiggy", "category_id": "x", "applies_to": "sideways"}, 422), ({"merchant": "Swiggy"}, 422),
    ({"merchant": "Swiggy", "category_id": "not-an-id"}, 400), ({"merchant": "Swiggy", "category_id": "000000000000000000000000"}, 404),
    ({"merchant": "Unknown", "category_id": "000000000000000000000000"}, 400),
])
async def test_learn_validation(client, auth, body, status):
    assert (await client.post("/api/rules/learn", headers=auth, json=body)).status_code == status


async def test_learn_requires_sign_in_and_own_category(client, auth):
    assert (await client.post("/api/rules/learn", json={"merchant": "Swiggy", "category_id": "x"})).status_code == 401
    other = await register(client, "other@example.com")
    theirs = await cat_id(client, other, "Groceries")
    assert (await client.post("/api/rules/learn", headers=auth, json={"merchant": "Swiggy", "category_id": theirs})).status_code == 404


# ------------------------------------------------------------------ suggestions from repeated corrections
async def suggest(client, auth):
    r = await client.get("/api/categories/suggestions", headers=auth)
    assert r.status_code == 200, r.text
    return r.json()


async def test_nothing_is_suggested_from_a_single_correction(client, auth):
    await setup(client, auth)
    groceries = await cat_id(client, auth, "Groceries")
    await move(client, auth, (await swiggy_debits(client, auth))[0]["id"], groceries)
    assert await suggest(client, auth) == []


async def test_repeated_corrections_become_a_suggestion(client, auth):
    await setup(client, auth)
    groceries = await cat_id(client, auth, "Groceries")
    a, b, *rest = await swiggy_debits(client, auth)
    await move(client, auth, a["id"], groceries)
    await move(client, auth, b["id"], groceries)
    s = await suggest(client, auth)
    assert len(s) == 1
    assert (s[0]["merchant"], s[0]["category_name"], s[0]["evidence"], s[0]["applies_to"], s[0]["affected"]) == ("Swiggy", "Groceries", 2, "debit", len(rest))
    assert s[0]["category_color"] and s[0]["category_id"] == groceries


async def test_conflicting_corrections_are_not_guessed_at(client, auth):
    await setup(client, auth)
    groceries, shopping = await cat_id(client, auth, "Groceries"), await cat_id(client, auth, "Shopping")
    a, b, c, d = await swiggy_debits(client, auth)
    for t, cat in ((a, groceries), (b, groceries), (c, shopping), (d, shopping)):
        await move(client, auth, t["id"], cat)
    assert await suggest(client, auth) == []                      # two against two: Tally will not pick a side


async def test_the_majority_wins(client, auth):
    await setup(client, auth)
    groceries, shopping = await cat_id(client, auth, "Groceries"), await cat_id(client, auth, "Shopping")
    a, b, c, d = await swiggy_debits(client, auth)
    for t, cat in ((a, groceries), (b, groceries), (c, groceries), (d, shopping)):
        await move(client, auth, t["id"], cat)
    s = await suggest(client, auth)
    assert [(x["category_name"], x["evidence"]) for x in s] == [("Groceries", 3)]


async def test_no_suggestion_when_the_rules_already_agree_with_you(client, auth):
    await setup(client, auth)
    food = await cat_id(client, auth, "Food & Dining")           # what the built-in rules already say for Swiggy
    a, b, *_ = await swiggy_debits(client, auth)
    await move(client, auth, a["id"], food)
    await move(client, auth, b["id"], food)
    assert await suggest(client, auth) == []


async def test_accepting_removes_the_suggestion(client, auth):
    await setup(client, auth)
    groceries = await cat_id(client, auth, "Groceries")
    a, b, *_ = await swiggy_debits(client, auth)
    await move(client, auth, a["id"], groceries)
    await move(client, auth, b["id"], groceries)
    s = (await suggest(client, auth))[0]
    await client.post("/api/rules/learn", headers=auth, json={"merchant": s["merchant"], "category_id": s["category_id"], "applies_to": s["applies_to"]})
    assert await suggest(client, auth) == []


async def test_dismissing_hides_that_suggestion_only(client, auth):
    await setup(client, auth)
    groceries, shopping = await cat_id(client, auth, "Groceries"), await cat_id(client, auth, "Shopping")
    for t in (await swiggy_debits(client, auth))[:2]:
        await move(client, auth, t["id"], groceries)
    for t in (await txns(client, auth, (await uncategorised(client, auth))[0]["merchant"]))[:2]:
        await move(client, auth, t["id"], shopping)
    both = await suggest(client, auth)
    assert sorted(x["category_name"] for x in both) == ["Groceries", "Shopping"]

    # saying no to Swiggy -> Shopping (a different answer) hides nothing that was offered
    await client.post("/api/categories/suggestions/dismiss", headers=auth, json={"merchant": "Swiggy", "category_id": shopping})
    assert len(await suggest(client, auth)) == 2

    r = await client.post("/api/categories/suggestions/dismiss", headers=auth, json={"merchant": "Swiggy", "category_id": groceries})
    assert r.status_code == 204
    again = await client.post("/api/categories/suggestions/dismiss", headers=auth, json={"merchant": "Swiggy", "category_id": groceries})
    assert again.status_code == 204                                            # saying it twice is harmless
    assert [x["category_name"] for x in await suggest(client, auth)] == ["Shopping"]


async def test_dismiss_validation_and_privacy(client, auth):
    assert (await client.post("/api/categories/suggestions/dismiss", headers=auth, json={"merchant": "", "category_id": "x"})).status_code == 422
    assert (await client.post("/api/categories/suggestions/dismiss", headers=auth, json={"merchant": "A", "category_id": "bad"})).status_code == 400
    assert (await client.post("/api/categories/suggestions/dismiss", json={"merchant": "A", "category_id": "x"})).status_code == 401
    assert (await client.get("/api/categories/suggestions")).status_code == 401


async def test_suggestions_are_private(client, auth):
    await setup(client, auth)
    groceries = await cat_id(client, auth, "Groceries")
    for t in (await swiggy_debits(client, auth))[:2]:
        await move(client, auth, t["id"], groceries)
    other = await register(client, "other@example.com")
    assert await suggest(client, other) == []
    assert len(await suggest(client, auth)) == 1


# ------------------------------------------------------------------ merchants that need a category
async def uncategorised(client, auth):
    r = await client.get("/api/categories/uncategorised", headers=auth)
    assert r.status_code == 200, r.text
    return r.json()


async def test_uncategorised_merchants_are_grouped_and_ranked(client, auth):
    await setup(client, auth)
    rows = await uncategorised(client, auth)
    assert [(r["count"], r["total"], r["applies_to"]) for r in rows] == [(3, 600.0, "debit"), (1, 50.0, "debit")]
    assert "ZXQV" in rows[0]["sample"].upper() and "PLUGH" in rows[1]["sample"].upper()
    assert all(r["merchant"] for r in rows)


async def test_one_choice_sorts_every_transaction_from_a_merchant(client, auth):
    await setup(client, auth)
    top = (await uncategorised(client, auth))[0]
    shopping = await cat_id(client, auth, "Shopping")
    r = await client.post("/api/rules/learn", headers=auth, json={"merchant": top["merchant"], "category_id": shopping, "applies_to": top["applies_to"]})
    assert r.json()["recategorized"] == top["count"]
    assert [x["merchant"] for x in await uncategorised(client, auth)] != [top["merchant"]]
    mine = await txns(client, auth, top["merchant"])
    assert {t["category_name"] for t in mine} == {"Shopping"} and not any(t["needs_review"] for t in mine)
    assert len(await uncategorised(client, auth)) == 1            # only the other one is left


async def test_nothing_to_categorise_is_an_empty_list(client, auth):
    assert await uncategorised(client, auth) == []
    assert (await client.get("/api/categories/uncategorised")).status_code == 401


async def test_uncategorised_is_private(client, auth):
    await setup(client, auth)
    other = await register(client, "other@example.com")
    assert await uncategorised(client, other) == []


# ------------------------------------------------------------------ data rights
async def test_dismissals_are_exported_and_deleted_with_the_account(client, auth, db):
    groceries = await cat_id(client, auth, "Groceries")
    await client.post("/api/categories/suggestions/dismiss", headers=auth, json={"merchant": "Swiggy", "category_id": groceries})
    exported = (await client.get("/api/settings/export", headers=auth)).json()
    assert [d["merchant"] for d in exported["dismissed_rule_suggestions"]] == ["Swiggy"]
    r = await client.request("DELETE", "/api/settings/account", headers=auth, json={"password": "secret123"})
    assert r.status_code == 200 and await db["learning_dismissed"].count_documents({}) == 0


async def test_the_offer_does_not_count_transactions_you_set_by_hand(client, auth):
    """A rule never moves a manual choice, so promising to move it would overstate what accepting does."""
    await setup(client, auth)
    a, b, c, d = await swiggy_debits(client, auth)
    groceries, entertainment = await cat_id(client, auth, "Groceries"), await cat_id(client, auth, "Entertainment")
    await move(client, auth, b["id"], entertainment)           # set by hand: a rule would leave it alone
    out = await move(client, auth, a["id"], groceries)
    assert out["suggestion"]["similar_count"] == 2             # c and d only; not b
