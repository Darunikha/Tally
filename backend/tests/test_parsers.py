"""CSV/PDF parsing, bank recognition and normalization."""
import pytest

from app.parsers.base import ParseError
from app.parsers.readers import read_csv, read_text_lines
from app.parsers.registry import identify_bank, parse_statement
from app.utils.dates import parse_date
from app.utils.money import parse_amount

BANK_FILES = [
    ("hdfc_statement.csv", "hdfc", "HDFC Bank"),
    ("icici_statement.csv", "icici", "ICICI Bank"),
    ("sbi_statement.csv", "sbi", "State Bank of India"),
    ("axis_statement.csv", "axis", "Axis Bank"),
    ("kotak_statement.csv", "kotak", "Kotak Mahindra Bank"),
]


@pytest.mark.parametrize("fname,key,bank", BANK_FILES)
def test_bank_recognition(sample, fname, key, bank):
    table = read_csv(sample(fname))
    parser, score = identify_bank(table)
    assert parser.key == key and score >= 0.6


@pytest.mark.parametrize("fname,key,bank", BANK_FILES)
def test_csv_parsing_balances_reconcile(sample, fname, key, bank):
    res, parser = parse_statement(sample(fname), "csv")
    assert res.bank_name == bank
    assert len(res.transactions) > 100 and res.skipped_rows == 0
    # running balance must move exactly by each parsed amount -> debit/credit direction is right
    txns = res.transactions
    for prev, cur in zip(txns, txns[1:]):
        if key == "kotak":
            continue  # Kotak balance column is unsigned with separate Dr/Cr flag
        assert round(prev.balance + cur.credit_amount - cur.debit_amount, 2) == pytest.approx(cur.balance)
    assert all(t.debit_amount >= 0 and t.credit_amount >= 0 for t in txns)
    assert all((t.debit_amount > 0) != (t.credit_amount > 0) for t in txns)


def test_preamble_is_skipped_and_header_found(sample):
    t = read_csv(sample("hdfc_statement.csv"))
    assert t.headers[0] == "Date" and "Narration" in t.headers
    assert "HDFC BANK" in t.text


def test_generic_fallback_signed_amounts(sample):
    res, parser = parse_statement(sample("unknown_bank_statement.csv"), "csv")
    assert parser.key == "generic"
    assert res.bank_name == "Unknown Bank"
    salary = [t for t in res.transactions if "SALARY" in t.description]
    assert salary and all(t.credit_amount > 0 for t in salary)
    assert any(t.debit_amount > 0 for t in res.transactions)


def test_kotak_amount_with_drcr_indicator(sample):
    res, _ = parse_statement(sample("kotak_statement.csv"), "csv")
    sal = next(t for t in res.transactions if "SALARY" in t.description)
    assert sal.credit_amount == 58000 and sal.debit_amount == 0
    rent = next(t for t in res.transactions if "RENT" in t.description)
    assert rent.debit_amount == 18000


def test_pdf_table_parsing(sample):
    res, parser = parse_statement(sample("sbi_statement.pdf"), "pdf")
    assert parser.key == "sbi" and res.bank_name == "State Bank of India"
    assert len(res.transactions) == 60
    assert res.parser_used.endswith(":pdf")


def test_pdf_text_line_fallback_infers_direction(sample):
    res, parser = parse_statement(sample("plain_text_statement.pdf"), "pdf")
    assert res.parser_used == "generic:pdf-text"
    assert res.bank_name == "Unknown Bank"  # VPAs like @hdfcbank in narrations must not fool detection
    sal = next(t for t in res.transactions if "SALARY" in t.description)
    assert sal.credit_amount == 50000
    rent = next(t for t in res.transactions if "SURESH NAIR" in t.description.upper())
    assert rent.debit_amount == 18000 and rent.credit_amount == 0


def test_text_lines_with_wrapped_narration():
    text = "Opening Balance: 1,000.00\n01/10/2025 UPI/SWIGGY/529012345678 250.00 750.00\nPayment from Phone\n02/10/2025 SALARY ACME 5,000.00 5,750.00\n"
    t = read_text_lines(text)
    assert len(t.rows) == 2
    assert t.rows[0][3] == "0.00" and t.rows[0][2] == "250.00"
    assert t.rows[1][3] == "5000.00"
    assert "Payment from Phone" in t.rows[0][1]


def test_bank_hint_overrides_detection(sample):
    res, parser = parse_statement(sample("unknown_bank_statement.csv"), "csv", bank_hint="generic")
    assert parser.key == "generic"


def test_invalid_csv_raises():
    with pytest.raises(ParseError):
        parse_statement(b"hello,world\n1,2\n", "csv")


def test_corrupt_pdf_raises():
    with pytest.raises(ParseError):
        parse_statement(b"%PDF-1.4 garbage", "pdf")


def test_multiline_csv_narration_continuation():
    csv_bytes = (
        "Date,Narration,Withdrawal Amt.,Deposit Amt.,Closing Balance\n"
        "01/10/25,UPI-SWIGGY-swiggy@icici,250.00,,750.00\n"
        ",ORDER 12345,,,\n"
        "Total,,250.00,0.00,\n"
    ).encode()
    res, _ = parse_statement(csv_bytes, "csv")
    assert len(res.transactions) == 1
    assert res.transactions[0].description.endswith("ORDER 12345")
    assert res.skipped_rows == 1


@pytest.mark.parametrize("raw,expected", [
    ("1,23,456.78", 123456.78), ("(500.00)", -500.0), ("500.00 Dr", -500.0), ("500.00 Cr", 500.0),
    ("₹ 1,299", 1299.0), ("", None), ("-", None), ("INR 45.5", 45.5), ("250-", -250.0),
])
def test_parse_amount(raw, expected):
    assert parse_amount(raw) == expected


@pytest.mark.parametrize("raw,expected", [
    ("17/10/25", "2025-10-17"), ("17/10/2025", "2025-10-17"), ("1 Oct 2025", "2025-10-01"),
    ("17-Oct-2025", "2025-10-17"), ("2025-10-17", "2025-10-17"), ("17-10-2025 19:45", "2025-10-17"),
    ("05/04/2025", "2025-04-05"),  # day-first (Indian convention)
])
def test_parse_date(raw, expected):
    assert parse_date(raw).strftime("%Y-%m-%d") == expected


def test_parse_date_invalid():
    assert parse_date("Opening Balance") is None
