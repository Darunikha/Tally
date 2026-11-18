"""Exports: CSV and Excel transactions (including formula-injection safety) and the PDF spending report."""
import csv
import io
from datetime import datetime

import pytest
from openpyxl import load_workbook
from pypdf import PdfReader

from app.services.exports import HEADERS, build_csv, export_row, neutralize
from app.services.report_pdf import build_summary_pdf, inr
from tests.conftest import register
from tests.test_api import import_file

PAYLOADS = [
    '=HYPERLINK("http://evil.example","click to verify")',
    "=cmd|' /C calc'!A0",
    "+1+1 CMD",
    "@SUM(1+1)",
    "-2+3 REFUND",
]
BANK_CSV = (
    "Posting Date,Transaction Details,Amount,Running Balance\n"
    + "".join(f'2025-08-{i + 1:02d},"{p.replace(chr(34), chr(34) * 2)}",-{100 * (i + 1)}.00,{10000 - 100 * (i + 1)}.00\n' for i, p in enumerate(PAYLOADS))
    + "2025-08-09,SALARY ACME TECHNOLOGIES,50000.00,60000.00\n"
).encode()
TRIGGERS = ("=", "+", "-", "@")


async def get_export(client, auth, fmt="csv", **params):
    return await client.get("/api/transactions/export", headers=auth, params={"format": fmt, **params})


def read_csv(resp):
    text = resp.content.decode("utf-8-sig")
    return list(csv.reader(io.StringIO(text)))


def read_xlsx(resp):
    return load_workbook(io.BytesIO(resp.content))


# ------------------------------------------------------------------ safety
@pytest.mark.parametrize("value", PAYLOADS + ["\tTAB", "\rCR"])
def test_neutralize_prefixes_anything_a_spreadsheet_could_run(value):
    assert neutralize(value) == "'" + value


@pytest.mark.parametrize("value", ["SALARY", "Swiggy", "UPI-SWIGGY-1", "a=b", "100 + 200", "", " =leading space"])
def test_neutralize_leaves_ordinary_text_alone(value):
    assert neutralize(value) == value


async def test_csv_has_no_cell_that_a_spreadsheet_would_evaluate(client, auth):
    await import_file(client, auth, BANK_CSV, "payloads.csv")
    rows = read_csv(await get_export(client, auth))
    assert rows[0] == HEADERS and len(rows) == 7
    assert not [c for row in rows[1:] for c in row if c.startswith(TRIGGERS + ("\t", "\r"))]
    descriptions = {r[2] for r in rows[1:]}
    assert {"'" + p for p in PAYLOADS} <= descriptions                # kept, visibly marked as text
    assert "SALARY ACME TECHNOLOGIES" in descriptions                 # ordinary text is untouched


async def test_user_notes_are_neutralised_too(client, auth):
    await import_file(client, auth, BANK_CSV, "payloads.csv")
    tid = (await client.get("/api/transactions", headers=auth, params={"search": "SALARY"})).json()["items"][0]["id"]
    await client.patch(f"/api/transactions/{tid}", headers=auth, json={"notes": "=1+1"})
    salary = next(r for r in read_csv(await get_export(client, auth)) if r[2].startswith("SALARY"))
    assert salary[HEADERS.index("Notes")] == "'=1+1"


async def test_excel_stores_every_formula_looking_value_as_text(client, auth):
    await import_file(client, auth, BANK_CSV, "payloads.csv")
    wb = read_xlsx(await get_export(client, auth, "xlsx"))
    cells = [c for ws in wb for row in ws.iter_rows() for c in row if c.value is not None]
    assert not [c for c in cells if c.data_type == "f"]               # no formulas anywhere in the workbook
    ws = wb["Transactions"]
    by_desc = {ws.cell(r, 3).value: ws.cell(r, 3) for r in range(2, ws.max_row + 1)}
    for p in PAYLOADS:
        assert by_desc[p].data_type == "s" and by_desc[p].value == p  # exact text, no apostrophe needed in Excel


# ------------------------------------------------------------------ CSV
async def test_csv_download(client, auth, sample):
    await import_file(client, auth, sample("hdfc_statement.csv"))
    r = await get_export(client, auth)
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/csv")
    assert r.headers["content-disposition"] == 'attachment; filename="tally-transactions-all-time.csv"'
    assert r.content.startswith(b"\xef\xbb\xbf")                      # BOM: Excel reads UTF-8 correctly
    rows = read_csv(r)
    total = (await client.get("/api/transactions", headers=auth, params={"page_size": 1})).json()["total"]
    assert rows[0] == HEADERS and len(rows) - 1 == total             # every matching row, not one page
    row = rows[1]
    assert datetime.strptime(row[0], "%Y-%m-%d") and float(row[4] or row[5])
    dates = [r[0] for r in rows[1:]]
    assert dates == sorted(dates)                                     # oldest first
    assert {r[3] for r in rows[1:]} == {"Debit", "Credit"} and {r[9] for r in rows[1:]} == {"Bank account"}


async def test_filters_apply_to_the_export(client, auth, sample):
    await import_file(client, auth, sample("hdfc_statement.csv"))
    rows = read_csv(await get_export(client, auth, type="credit"))[1:]
    assert rows and {r[3] for r in rows} == {"Credit"}
    rows = read_csv(await get_export(client, auth, month=10, year=2025))[1:]
    assert rows and all(r[0].startswith("2025-10") for r in rows)
    rows = read_csv(await get_export(client, auth, search="netflix"))[1:]
    assert len(rows) == 3 and {r[1] for r in rows} == {"Netflix"}
    rows = read_csv(await get_export(client, auth, min_amount=40000))[1:]
    assert rows and all(float(r[4] or r[5]) >= 40000 for r in rows)


@pytest.mark.parametrize("params,name", [
    ({"month": 8, "year": 2025}, "tally-transactions-2025-08.csv"),
    ({"year": 2025}, "tally-transactions-2025.csv"),
    ({"start": "2025-08-05", "end": "2025-09-02"}, "tally-transactions-2025-08-05_to_2025-09-02.csv"),
    ({"start": "2025-08-05"}, "tally-transactions-2025-08-05_onwards.csv"),
    ({}, "tally-transactions-all-time.csv"),
])
async def test_file_names_describe_the_period(client, auth, params, name):
    r = await get_export(client, auth, **params)
    assert r.headers["content-disposition"] == f'attachment; filename="{name}"'


async def test_card_statement_rows_are_labelled(client, auth, sample):
    await import_file(client, auth, sample("hdfc_credit_card.csv"), "card.csv")
    rows = read_csv(await get_export(client, auth))[1:]
    assert len(rows) == 34 and {r[9] for r in rows} == {"Credit card"} and {r[8] for r in rows} == {"Credit Card"}


# ------------------------------------------------------------------ Excel
async def test_excel_workbook_structure(client, auth, sample):
    await import_file(client, auth, sample("hdfc_statement.csv"))
    r = await get_export(client, auth, "xlsx", month=10, year=2025, type="debit")
    assert r.headers["content-type"] == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    assert r.headers["content-disposition"] == 'attachment; filename="tally-transactions-2025-10.xlsx"'
    wb = read_xlsx(r)
    assert wb.sheetnames == ["Transactions", "About this export"]
    ws = wb["Transactions"]
    assert [c.value for c in ws[1]] == HEADERS and ws.freeze_panes == "A2"
    assert ws.auto_filter.ref == f"A1:{chr(64 + len(HEADERS))}{ws.max_row}"
    first = [c for c in ws[2]]
    assert isinstance(first[0].value, datetime) and first[0].number_format == "DD-MMM-YYYY"    # real dates
    assert isinstance(first[4].value, (int, float)) and first[4].number_format == "#,##0.00"    # real numbers
    assert first[5].value is None                                                                # a debit has no credit
    total = sum(ws.cell(i, 5).value for i in range(2, ws.max_row + 1))                           # sums work
    about = {a.value: b.value for a, b in wb["About this export"].iter_rows(values_only=False)}
    assert about["Transactions"] == f"{ws.max_row - 1:,}" and about["Type"] == "Debit"
    assert about["Total debits"] == f"{total:,.2f}" and about["Period"] == "01 Oct 2025 to 31 Oct 2025"
    assert about["Exported"].endswith("IST")


async def test_excel_about_sheet_names_category_and_statement_filters(client, auth, sample):
    up = await import_file(client, auth, sample("hdfc_statement.csv"))
    cat = next(c for c in (await client.get("/api/categories", headers=auth)).json() if c["name"] == "Food & Dining")
    wb = read_xlsx(await get_export(client, auth, "xlsx", category_id=cat["id"], upload_id=up["id"]))
    about = {a.value: b.value for a, b in wb["About this export"].iter_rows()}
    assert about["Category"] == "Food & Dining" and about["Statement"] == "hdfc_statement.csv"
    none = read_xlsx(await get_export(client, auth, "xlsx"))
    assert {a.value: b.value for a, b in none["About this export"].iter_rows()}["Filters"] == "None - every transaction"


# ------------------------------------------------------------------ limits, validation, privacy
async def test_validation_and_auth(client, auth):
    assert (await get_export(client, auth, "pdf")).status_code == 422
    assert (await get_export(client, auth, month=13, year=2025)).status_code == 422
    assert (await client.get("/api/transactions/export")).status_code == 401


async def test_too_many_rows_is_refused_with_advice(client, auth, sample, monkeypatch):
    await import_file(client, auth, sample("hdfc_statement.csv"))
    monkeypatch.setattr("app.api.transactions.MAX_EXPORT_ROWS", 10)
    r = await get_export(client, auth)
    assert r.status_code == 400 and r.json()["error"]["code"] == "too_many_rows"
    assert "Narrow the date range" in r.json()["error"]["message"] and "10" in r.json()["error"]["message"]
    assert (await get_export(client, auth, search="netflix")).status_code == 200  # a narrower export works


async def test_exports_are_rate_limited(client, auth):
    for _ in range(30):
        assert (await get_export(client, auth)).status_code == 200
    r = await get_export(client, auth)
    assert r.status_code == 429 and "Retry-After" in r.headers


async def test_an_export_only_contains_your_own_transactions(client, auth, sample):
    other = await register(client, "other@example.com")
    await import_file(client, auth, sample("hdfc_statement.csv"))
    await import_file(client, other, BANK_CSV, "payloads.csv")
    assert len(read_csv(await get_export(client, other))) == 7
    assert not any("SWIGGY" in r[2].upper() for r in read_csv(await get_export(client, other)))


def test_export_row_handles_missing_values():
    row = export_row({"transaction_date": datetime(2025, 8, 1), "transaction_type": "debit", "debit_amount": 0.0,
                      "credit_amount": 0.0}, {})
    assert row[4] is None and row[5] is None and row[6] is None and row[1] == "" and row[9] == "Bank account"
    assert build_csv([row]).decode("utf-8-sig").splitlines()[1].startswith("2025-08-01,,,Debit,,,")


# ------------------------------------------------------------------ PDF report
def pdf_text(resp) -> str:
    return " ".join(" ".join(p.extract_text() for p in PdfReader(io.BytesIO(resp.content)).pages).split())


@pytest.mark.parametrize("value,expected", [
    (0, "Rs. 0"), (999, "Rs. 999"), (1000, "Rs. 1,000"), (102509, "Rs. 1,02,509"), (1234567.5, "Rs. 12,34,568"),
    (-54728.2, "-Rs. 54,728"), (None, "-"),
])
def test_inr_uses_indian_grouping_without_the_rupee_glyph(value, expected):
    assert inr(value) == expected


def test_inr_with_decimals():
    assert inr(1234.5, 2) == "Rs. 1,234.50" and inr(12345678.9, 2) == "Rs. 1,23,45,678.90"


async def test_pdf_report_matches_the_dashboard(client, auth, sample):
    await import_file(client, auth, sample("hdfc_statement.csv"))
    q = {"month": 10, "year": 2025}
    dash = (await client.get("/api/analytics/dashboard", headers=auth, params=q)).json()
    r = await client.get("/api/reports/summary.pdf", headers=auth, params=q)
    assert r.status_code == 200 and r.headers["content-type"] == "application/pdf" and r.content.startswith(b"%PDF")
    assert r.headers["content-disposition"] == 'attachment; filename="tally-report-2025-10.pdf"'
    text = pdf_text(r)
    assert "Spending report" in text and "October 2025" in text and "Where the money went" in text
    t = dash["totals"]
    assert inr(t["total_income"]) in text and inr(t["total_expenses"]) in text and f"{t['transaction_count']:,}" in text
    assert dash["category_breakdown"][0]["name"] in text and dash["top_merchants"][0]["merchant"] in text
    assert "Top merchants" in text and "Month by month" not in text  # a single month has no month-by-month table


async def test_pdf_report_for_all_time_has_a_monthly_table(client, auth, sample):
    await import_file(client, auth, sample("hdfc_statement.csv"))
    r = await client.get("/api/reports/summary.pdf", headers=auth)
    text = pdf_text(r)
    assert "All time (01 Aug 2025 to 31 Oct 2025)" in text and "Month by month" in text
    assert all(m in text for m in ("Aug 2025", "Sep 2025", "Oct 2025"))
    assert r.headers["content-disposition"] == 'attachment; filename="tally-report-all-time.pdf"'


async def test_pdf_report_includes_budgets_for_a_single_month(client, auth, sample):
    await import_file(client, auth, sample("hdfc_statement.csv"))
    await client.put("/api/budgets", headers=auth, json={"category_id": None, "monthly_limit": 50000})
    assert "Budgets" not in pdf_text(await client.get("/api/reports/summary.pdf", headers=auth))      # not for a long period
    text = pdf_text(await client.get("/api/reports/summary.pdf", headers=auth, params={"month": 10, "year": 2025}))
    assert "Budgets - October 2025" in text and "Overall spending" in text and "Over budget" in text and "Rs. 50,000" in text


async def test_pdf_report_for_a_range_and_a_statement(client, auth, sample):
    up = await import_file(client, auth, sample("hdfc_statement.csv"))
    r = await client.get("/api/reports/summary.pdf", headers=auth,
                         params={"start": "2025-09-01", "end": "2025-09-15", "upload_id": up["id"]})
    text = pdf_text(r)
    assert "01 Sep 2025 to 15 Sep 2025" in text and "Statement: hdfc_statement.csv" in text
    assert r.headers["content-disposition"] == 'attachment; filename="tally-report-2025-09-01_to_2025-09-15.pdf"'


async def test_pdf_report_notes_left_out_card_payments(client, auth, sample):
    bank = ("Posting Date,Transaction Details,Amount,Running Balance\n2025-08-01,SALARY ACME,85000.00,185000.00\n"
            "2025-08-10,CREDIT CARD PAYMENT HDFC CARD,-40000.00,145000.00\n2025-08-12,BESCOM ELECTRICITY,-1500.00,143500.00\n").encode()
    await import_file(client, auth, bank, "bank.csv")
    await import_file(client, auth, sample("hdfc_credit_card.csv"), "card.csv")
    text = pdf_text(await client.get("/api/reports/summary.pdf", headers=auth, params={"month": 8, "year": 2025}))
    assert "2 credit card bill payments are left out" in text
    assert inr(35228.22 + 1500) in text


async def test_pdf_report_for_an_empty_period(client, auth, sample):
    r = await client.get("/api/reports/summary.pdf", headers=auth, params={"month": 1, "year": 2020})
    assert r.status_code == 200 and "There are no transactions in this period." in pdf_text(r)


async def test_pdf_report_validation_auth_and_limits(client, auth):
    assert (await client.get("/api/reports/summary.pdf")).status_code == 401
    assert (await client.get("/api/reports/summary.pdf", headers=auth, params={"month": 13, "year": 2025})).status_code == 422
    for _ in range(30):
        assert (await client.get("/api/reports/summary.pdf", headers=auth, params={"month": 1, "year": 2020})).status_code == 200
    assert (await client.get("/api/reports/summary.pdf", headers=auth)).status_code == 429


async def test_pdf_report_is_private(client, auth, sample):
    await import_file(client, auth, sample("hdfc_statement.csv"))
    other = await register(client, "other@example.com")
    text = pdf_text(await client.get("/api/reports/summary.pdf", headers=other, params={"month": 10, "year": 2025}))
    assert "There are no transactions in this period." in text and "Swiggy" not in text


def test_report_builder_survives_markup_in_merchant_names():
    """Merchant names are untrusted text; '<' and '&' must not break PDF layout (or inject markup)."""
    data = {"period_label": "August 2025", "generated": "now", "statement": 'x <b>"y"</b>', "excluded_payments": 0,
            "totals": {"total_income": 0, "total_expenses": 1500.0, "net_balance": -1500.0, "transaction_count": 2, "debit_count": 2,
                       "credit_count": 0, "upi_spending": 0, "upi_transaction_count": 0, "avg_daily_spending": 48.0, "days": 31,
                       "savings_rate": None},
            "changes": None, "monthly": [], "budgets": None,
            "categories": [{"name": "R&D <i>Lab</i>", "color": "#EB6834", "amount": 1500.0, "percentage": 100.0, "count": 2}],
            "merchants": [{"merchant": "A & B <script>alert(1)</script>", "category": "R&D <i>Lab</i>", "count": 2, "total": 1500.0}]}
    pdf = build_summary_pdf(data)
    text = " ".join(" ".join(p.extract_text() for p in PdfReader(io.BytesIO(pdf)).pages).split())
    assert "A & B <script>alert(1)</script>" in text and "R&D <i>Lab</i>" in text and 'Statement: x <b>"y"</b>' in text


def _page_texts(pdf: bytes) -> list[str]:
    return [" ".join(p.extract_text().split()) for p in PdfReader(io.BytesIO(pdf)).pages]


def _busy_report(n_budgets: int = 3) -> dict:
    """A month with 11 categories and 10 merchants: the budgets heading lands at the foot of page 1."""
    names = ["Shopping", "Rent", "Food & Dining", "Groceries", "Investments", "Transfers", "Transportation", "Fuel",
             "Bills & Utilities", "Subscriptions", "Healthcare"]
    row = lambda name, spent, limit, status: {"name": name, "spent": spent, "monthly_limit": limit, "percent": spent / limit * 100, "status": status}  # noqa: E731
    return {
        "period_label": "October 2025", "generated": "now", "excluded_payments": 0, "statement": None, "changes": None, "monthly": [],
        "totals": {"total_income": 86275.0, "total_expenses": 102509.0, "net_balance": -16234.0, "transaction_count": 51, "debit_count": 48,
                   "credit_count": 3, "upi_spending": 94047.0, "upi_transaction_count": 43, "avg_daily_spending": 3307.0, "days": 31,
                   "savings_rate": -18.8},
        "categories": [{"name": n, "color": "#EB6834", "amount": 1000.0 * (11 - i), "percentage": 9.0, "count": 3} for i, n in enumerate(names)],
        "merchants": [{"merchant": f"Merchant {i}", "category": "Shopping", "count": 2, "total": 900.0 * (10 - i)} for i in range(10)],
        "budgets": {"month": {"label": "October 2025"}, "overall": row("Overall spending", 102509, 80000, "over"),
                    "budgets": [row(f"Budget {i}", 5000, 9000, "ok") for i in range(n_budgets - 1)]},
    }


def test_a_section_heading_is_never_stranded_at_the_foot_of_a_page():
    pages = _page_texts(build_summary_pdf(_busy_report()))
    assert len(pages) == 2
    page_with_heading = next(t for t in pages if "Budgets - October 2025" in t)
    assert "Overall spending" in page_with_heading  # the heading travels with its table
