"""Transaction exports (CSV and Excel).

Descriptions and merchant names come from outside - a payee can name themselves `=HYPERLINK("http://evil","pay")` -
so every text value is treated as untrusted. Opened in Excel or Sheets, a cell that starts with `=`, `+`, `-` or `@`
can run as a formula (CSV/formula injection). CSV text is prefixed with an apostrophe, and Excel text cells are
written with an explicit string type, so nothing in an export can ever execute.
"""
from __future__ import annotations

import csv
import io
from datetime import datetime

MAX_EXPORT_ROWS = 50_000
FORMULA_TRIGGERS = ("=", "+", "-", "@", "\t", "\r")

HEADERS = ["Date", "Merchant", "Description", "Type", "Debit", "Credit", "Balance", "Category", "Payment method",
           "Account type", "Bank", "UPI ID", "Reference", "Notes"]
WIDTHS = [12, 24, 52, 8, 13, 13, 14, 20, 16, 14, 22, 26, 22, 30]
ACCOUNT_LABELS = {"credit_card": "Credit card", "bank": "Bank account"}


def is_formula_like(value) -> bool:
    return isinstance(value, str) and value.startswith(FORMULA_TRIGGERS)


def neutralize(value):
    """CSV-safe text: a leading apostrophe stops spreadsheets from evaluating the cell."""
    return "'" + value if is_formula_like(value) else value


def export_row(t: dict, cats: dict[str, dict]) -> list:
    """One transaction as plain values (date, text, numbers); formatting is the writer's job."""
    cat = cats.get(str(t.get("category_id")), {})
    return [
        t["transaction_date"], t.get("normalized_merchant") or "", t.get("raw_description") or "",
        "Credit" if t.get("transaction_type") == "credit" else "Debit",
        t.get("debit_amount") or None, t.get("credit_amount") or None, t.get("balance"),
        cat.get("name") or "", t.get("payment_method") or "", ACCOUNT_LABELS.get(t.get("account_type") or "bank", "Bank account"),
        t.get("bank_name") or "", t.get("upi_id") or "", t.get("transaction_reference") or "", t.get("notes") or "",
    ]


def build_csv(rows: list[list]) -> bytes:
    """UTF-8 with a byte-order mark so Excel reads names and symbols correctly; ISO dates, plain numbers."""
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(HEADERS)
    for r in rows:
        out = []
        for v in r:
            if isinstance(v, datetime):
                out.append(v.strftime("%Y-%m-%d"))
            elif isinstance(v, (int, float)):
                out.append(f"{v:.2f}")
            else:
                out.append(neutralize("" if v is None else str(v)))
        w.writerow(out)
    return buf.getvalue().encode("utf-8-sig")


def build_xlsx(rows: list[list], about: list[tuple[str, str]]) -> bytes:
    """Excel workbook: real dates and numbers (so sorting and sums work), a frozen styled header with filters, and
    an 'About this export' sheet recording which filters produced it."""
    from openpyxl import Workbook
    from openpyxl.cell import WriteOnlyCell
    from openpyxl.styles import Alignment, Font, PatternFill

    wb = Workbook(write_only=True)
    ws = wb.create_sheet("Transactions")
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = f"A1:{chr(64 + len(HEADERS))}{len(rows) + 1}"
    for i, width in enumerate(WIDTHS):
        ws.column_dimensions[chr(65 + i)].width = width

    head = []
    for h in HEADERS:
        c = WriteOnlyCell(ws, value=h)
        c.font = Font(bold=True, color="FFFFFF")
        c.fill = PatternFill("solid", fgColor="2F7D55")
        c.alignment = Alignment(vertical="center")
        head.append(c)
    ws.append(head)

    for r in rows:
        line = []
        for i, v in enumerate(r):
            if v is None or v == "":
                line.append(None)
                continue
            c = WriteOnlyCell(ws, value=v)
            if isinstance(v, datetime):
                c.number_format = "DD-MMM-YYYY"
            elif isinstance(v, (int, float)):
                c.number_format = "#,##0.00"
            else:
                c.data_type = "s"  # always text: Excel never evaluates a string cell, whatever it starts with
            line.append(c)
        ws.append(line)

    about_ws = wb.create_sheet("About this export")
    about_ws.column_dimensions["A"].width = 22
    about_ws.column_dimensions["B"].width = 70
    for key, value in about:
        k, v = WriteOnlyCell(about_ws, value=key), WriteOnlyCell(about_ws, value=value)
        k.font = Font(bold=True)
        v.data_type = "s"
        about_ws.append([k, v])

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()
