"""Credit card statements: parsing, direction (purchase vs payment), categorisation and not double counting."""
import pytest

from app.parsers.adapters.cards import CreditCardParser, split_card_amount
from app.parsers.base import StatementTable
from app.parsers.registry import identify_bank, parse_statement
from app.services.query import excluded_category_ids
from tests.conftest import register
from tests.test_api import import_file

# the generator writes the same month of activity in every layout, so every issuer must agree on these
ROWS, DEBITS, CREDITS = 34, 35228.22, 41299.00
ISSUERS = [
    ("hdfc_credit_card.csv", "hdfc_card", "HDFC Bank Credit Card"),
    ("icici_credit_card.csv", "icici_card", "ICICI Bank Credit Card"),
    ("sbi_credit_card.csv", "sbi_card", "SBI Card"),
    ("axis_credit_card.csv", "axis_card", "Axis Bank Credit Card"),
]


# ------------------------------------------------------------------ amounts
@pytest.mark.parametrize("raw,expected", [
    ("1,299.00", (1299.0, False)),            # a plain amount is a purchase
    ("5,000.00 Cr", (5000.0, True)),
    ("5,000.00CR", (5000.0, True)),
    ("250.00 C", (250.0, True)),
    ("250.00 D", (250.0, False)),
    ("250.00 Dr", (250.0, False)),
    ("-250.00", (250.0, True)),               # a minus sign marks a payment or refund
    ("(250.00)", (250.0, True)),
    ("₹ 1,299.00", (1299.0, False)),
    ("Rs.1,00,000.50 Cr", (100000.5, True)),  # Indian digit grouping
])
def test_split_card_amount(raw, expected):
    assert split_card_amount(raw) == expected


@pytest.mark.parametrize("raw", ["", None, "abc", "-"])
def test_split_card_amount_unreadable(raw):
    assert split_card_amount(raw) is None


# ------------------------------------------------------------------ parsing
@pytest.mark.parametrize("fname,key,bank", ISSUERS)
def test_issuer_detected_and_parsed(sample, fname, key, bank):
    result, parser = parse_statement(sample(fname), "csv")
    assert (parser.key, result.bank_name, result.account_type) == (key, bank, "credit_card")
    assert len(result.transactions) == ROWS
    assert sum(t.debit_amount for t in result.transactions) == pytest.approx(DEBITS)
    assert sum(t.credit_amount for t in result.transactions) == pytest.approx(CREDITS)
    assert not result.warnings


@pytest.mark.parametrize("fname,key,bank", ISSUERS)
def test_purchases_are_debits_and_payments_are_credits(sample, fname, key, bank):
    result, _ = parse_statement(sample(fname), "csv")
    by_desc = {t.description: t for t in result.transactions}
    payment = next(t for d, t in by_desc.items() if "PAYMENT" in d.upper() and "RECEIVED" in d.upper())
    assert (payment.credit_amount, payment.debit_amount) == (40000.0, 0.0)
    refund = next(t for d, t in by_desc.items() if d.startswith("REFUND"))
    assert (refund.credit_amount, refund.debit_amount) == (1299.0, 0.0)
    fee = by_desc["ANNUAL FEE"]
    assert (fee.debit_amount, fee.credit_amount) == (499.0, 0.0)
    assert all(t.balance is None for t in result.transactions)  # cards carry no running balance


def test_icici_is_recognised_from_its_headers_alone(sample):
    """The ICICI export has no issuer text; its SerNo./BillingAmountSign columns identify it."""
    table = parse_statement.__globals__["read_table"](sample("icici_credit_card.csv"), "csv")
    assert table.text == "" and identify_bank(table)[0].key == "icici_card"


def test_hdfc_timestamps_in_the_date_column(sample):
    result, _ = parse_statement(sample("hdfc_credit_card.csv"), "csv")
    assert {t.transaction_date.strftime("%Y-%m") for t in result.transactions} == {"2025-08"}


def test_unknown_issuer_needs_the_format_list(sample):
    """With no issuer name, an unsigned amount column reads as all credits; the user is told how to fix it."""
    result, _ = parse_statement(sample("card_unknown_issuer.csv"), "csv")
    assert result.account_type == "bank" and sum(t.debit_amount for t in result.transactions) == 0
    assert any("credit card" in w for w in result.warnings)

    result, parser = parse_statement(sample("card_unknown_issuer.csv"), "csv", bank_hint="generic_card")
    assert (parser.key, result.account_type, result.bank_name) == ("generic_card", "credit_card", "Credit Card")
    assert sum(t.debit_amount for t in result.transactions) == pytest.approx(DEBITS)
    assert not result.warnings


def test_card_pdf_without_tables_is_read_as_a_card(sample):
    result, parser = parse_statement(sample("credit_card_statement.pdf"), "pdf")
    assert (parser.key, result.account_type) == ("generic_card", "credit_card")
    assert len(result.transactions) == ROWS
    assert sum(t.debit_amount for t in result.transactions) == pytest.approx(DEBITS)
    assert sum(t.credit_amount for t in result.transactions) == pytest.approx(CREDITS)


def test_hint_overrides_detection(sample):
    result, parser = parse_statement(sample("hdfc_credit_card.csv"), "csv", bank_hint="generic_card")
    assert parser.key == "generic_card" and len(result.transactions) == ROWS


# ------------------------------------------------------------------ detection must not claim bank statements
def test_bank_statements_are_never_taken_for_cards(sample):
    for fname, key in [("hdfc_statement.csv", "hdfc"), ("icici_statement.csv", "icici"), ("sbi_statement.csv", "sbi"),
                       ("axis_statement.csv", "axis"), ("kotak_statement.csv", "kotak")]:
        result, parser = parse_statement(sample(fname), "csv")
        assert (parser.key, result.account_type) == (key, "bank")


def test_card_words_in_narrations_do_not_make_a_bank_statement_a_card():
    """Page-one text of a bank statement can include 'CREDIT CARD PAYMENT' narrations."""
    table = StatementTable(headers=["Date", "Narration", "Withdrawal Amt.", "Deposit Amt.", "Closing Balance"], rows=[],
                           text="HDFC BANK CREDIT CARD PAYMENT 12/08/2025 NEFT CREDIT CARD BILL")
    assert not identify_bank(table)[0].account_type == "credit_card"


def test_generic_headers_without_issuer_stay_with_the_generic_bank_parser():
    table = StatementTable(headers=["Date", "Transaction Details", "Amount"], rows=[], text="")
    assert identify_bank(table)[0].key == "generic"


def test_card_shape_needs_no_running_balance():
    assert CreditCardParser.card_shaped(["date", "transactiondescription", "amountinrs", "debitcredit"])
    assert not CreditCardParser.card_shaped(["date", "description", "amount", "balance"])
    assert not CreditCardParser.card_shaped(["date", "narration", "withdrawalamt", "depositamt", "closingbalance"])


# ------------------------------------------------------------------ API
BANK_CSV = (
    "Posting Date,Transaction Details,Amount,Running Balance\n"
    "2025-08-01,SALARY ACME TECHNOLOGIES,85000.00,185000.00\n"
    "2025-08-06,HOUSE RENT,-18000.00,167000.00\n"
    "2025-08-10,CREDIT CARD PAYMENT HDFC CARD,-40000.00,127000.00\n"
    "2025-08-12,BESCOM ELECTRICITY,-1500.00,125500.00\n"
).encode()


async def dashboard(client, auth):
    r = await client.get("/api/analytics/dashboard", params={"month": 8, "year": 2025}, headers=auth)
    assert r.status_code == 200
    return r.json()


async def cat_by_name(client, auth, name):
    return next(c for c in (await client.get("/api/categories", headers=auth)).json() if c["name"] == name)


async def test_supported_formats_list_cards_separately(client, auth):
    banks = (await client.get("/api/statements/banks", headers=auth)).json()
    cards = {b["key"] for b in banks if b["account_type"] == "credit_card"}
    assert cards == {"hdfc_card", "icici_card", "sbi_card", "axis_card", "generic_card"}
    assert {"hdfc", "generic"} <= {b["key"] for b in banks if b["account_type"] == "bank"}


async def test_card_statement_import_end_to_end(client, auth, sample):
    done = await import_file(client, auth, sample("hdfc_credit_card.csv"), "hdfc_credit_card.csv")
    assert (done["account_type"], done["bank_name"], done["transaction_count"]) == ("credit_card", "HDFC Bank Credit Card", ROWS)
    assert done["total_debits"] == pytest.approx(DEBITS) and done["total_credits"] == pytest.approx(CREDITS)

    items = (await client.get("/api/transactions", params={"page_size": 200}, headers=auth)).json()["items"]
    assert {t["payment_method"] for t in items} == {"Credit Card"} and {t["account_type"] for t in items} == {"credit_card"}
    by = {t["raw_description"]: t for t in items}
    assert by["PAYMENT RECEIVED - THANK YOU"]["category_name"] == "Credit Card Payments"
    assert by["PAYMENT RECEIVED - THANK YOU"]["normalized_merchant"] == "Credit Card Payment"
    assert by["ANNUAL FEE"]["category_name"] == "Bills & Utilities"       # a real charge, not a card payment
    assert by["FINANCE CHARGES"]["category_name"] == "Bills & Utilities"
    swiggy = next(t for t in items if "SWIGGY" in t["raw_description"])
    assert (swiggy["normalized_merchant"], swiggy["category_name"]) == ("Swiggy", "Food & Dining")  # city and country dropped


async def test_card_statement_cannot_be_imported_twice(client, auth, sample):
    await import_file(client, auth, sample("sbi_credit_card.csv"), "sbi_credit_card.csv")
    r = await client.post("/api/statements/preview", headers=auth,
                          files={"file": ("again.csv", sample("sbi_credit_card.csv"), "text/csv")})
    assert r.status_code == 409 and r.json()["error"]["code"] == "duplicate_statement"


async def test_bill_paid_from_the_bank_counts_as_spending_until_a_card_statement_is_added(client, auth, db, sample):
    await import_file(client, auth, BANK_CSV, "bank.csv")
    t = (await dashboard(client, auth))["totals"]
    assert t["total_expenses"] == 18000 + 40000 + 1500 and t["total_income"] == 85000
    assert await excluded_category_ids(db, (await db["users"].find_one())["_id"]) == []

    # the bank-side payment is already filed under Credit Card Payments, ready for when cards are tracked
    pay = next(x for x in (await client.get("/api/transactions", headers=auth)).json()["items"] if "CREDIT CARD" in x["raw_description"])
    assert pay["category_name"] == "Credit Card Payments"


async def test_card_payments_are_left_out_once_a_card_statement_is_imported(client, auth, db, sample):
    await import_file(client, auth, BANK_CSV, "bank.csv")
    card = await import_file(client, auth, sample("hdfc_credit_card.csv"), "hdfc_credit_card.csv")
    d = await dashboard(client, auth)
    # spending: rent + electricity + every card purchase; the 40,000 paid from the bank is not counted again
    assert d["totals"]["total_expenses"] == pytest.approx(18000 + 1500 + DEBITS)
    # income: salary + the Amazon refund; the 40,000 "payment received" on the card is not income
    assert d["totals"]["total_income"] == pytest.approx(85000 + 1299)
    assert d["excluded_payments"]["count"] == 2  # the bank debit and the card credit
    assert sum(c["amount"] for c in d["category_breakdown"]) == pytest.approx(d["totals"]["total_expenses"])
    assert all(c["name"] != "Credit Card Payments" for c in d["category_breakdown"])

    # the transactions list still shows everything
    total = (await client.get("/api/transactions", params={"page_size": 1}, headers=auth)).json()["total"]
    assert total == 4 + ROWS

    # removing the card statement brings the bank-side payment back into spending
    assert (await client.delete(f"/api/statements/{card['id']}", headers=auth)).status_code == 200
    d = await dashboard(client, auth)
    assert d["totals"]["total_expenses"] == 18000 + 40000 + 1500 and d["excluded_payments"]["count"] == 0


async def test_budgets_ignore_card_payments_once_cards_are_tracked(client, auth, sample):
    await import_file(client, auth, BANK_CSV, "bank.csv")
    await import_file(client, auth, sample("hdfc_credit_card.csv"), "hdfc_credit_card.csv")
    await client.put("/api/budgets", headers=auth, json={"category_id": None, "monthly_limit": 100000})
    s = (await client.get("/api/budgets/status", params={"month": 8, "year": 2025}, headers=auth)).json()
    assert s["overall"]["spent"] == pytest.approx(18000 + 1500 + DEBITS)
    assert all(u["name"] != "Credit Card Payments" for u in s["unbudgeted"])


async def test_exclusion_follows_the_category_after_a_rename(client, auth, sample):
    cat = await cat_by_name(client, auth, "Credit Card Payments")
    assert cat["excluded_from_totals"] is True
    await client.patch(f"/api/categories/{cat['id']}", headers=auth, json={"name": "Card bills"})
    await import_file(client, auth, BANK_CSV, "bank.csv")
    await import_file(client, auth, sample("hdfc_credit_card.csv"), "hdfc_credit_card.csv")
    assert (await dashboard(client, auth))["excluded_payments"]["count"] == 2


async def test_card_payments_category_cannot_be_deleted(client, auth):
    cat = await cat_by_name(client, auth, "Credit Card Payments")
    r = await client.delete(f"/api/categories/{cat['id']}", headers=auth)
    assert r.status_code == 400 and r.json()["error"]["code"] == "protected"
    assert (await cat_by_name(client, auth, "Credit Card Payments"))["id"] == cat["id"]


async def test_exclusion_is_per_user(client, auth, db, sample):
    other = await register(client, "other@example.com")
    await import_file(client, other, sample("hdfc_credit_card.csv"), "hdfc_credit_card.csv")
    await import_file(client, auth, BANK_CSV, "bank.csv")  # this user never added a card
    assert (await dashboard(client, auth))["totals"]["total_expenses"] == 18000 + 40000 + 1500


async def test_older_accounts_are_topped_up_once(client, auth, db, sample):
    """An account created before cards existed has no payments category or rules; the first import adds them."""
    uid = (await db["users"].find_one({"email": "demo@example.com"}))["_id"]
    await db["categories"].delete_one({"user_id": uid, "name": "Credit Card Payments"})
    await db["categorization_rules"].delete_many({"user_id": uid, "rule_name": {"$regex": "^Credit card"}})
    await db["users"].update_one({"_id": uid}, {"$unset": {"defaults_version": ""}})

    await import_file(client, auth, sample("hdfc_credit_card.csv"), "hdfc_credit_card.csv")
    cat = await cat_by_name(client, auth, "Credit Card Payments")
    assert cat["excluded_from_totals"] is True
    names = {r["rule_name"] for r in (await client.get("/api/rules", headers=auth)).json()}
    assert {"Credit card payment received", "Credit card bill payment", "Credit card fees & interest"} <= names
    assert (await db["users"].find_one({"_id": uid}))["defaults_version"] == 2

    # a rule the user removes afterwards is not resurrected by later imports
    await db["categorization_rules"].delete_one({"user_id": uid, "rule_name": "Credit card fees & interest"})
    await import_file(client, auth, BANK_CSV, "bank.csv")
    names = {r["rule_name"] for r in (await client.get("/api/rules", headers=auth)).json()}
    assert "Credit card fees & interest" not in names


async def test_existing_category_is_flagged_not_duplicated(client, auth, db, sample):
    uid = (await db["users"].find_one({"email": "demo@example.com"}))["_id"]
    await db["categories"].update_one({"user_id": uid, "name": "Credit Card Payments"}, {"$unset": {"excluded_from_totals": ""}})
    await db["users"].update_one({"_id": uid}, {"$unset": {"defaults_version": ""}})
    await import_file(client, auth, sample("sbi_credit_card.csv"), "sbi_credit_card.csv")
    cats = [c for c in (await client.get("/api/categories", headers=auth)).json() if c["name"] == "Credit Card Payments"]
    assert len(cats) == 1 and cats[0]["excluded_from_totals"] is True

