"""Generate SYNTHETIC bank statements (no real customer data) in several bank layouts.

    python sample_data/generate_samples.py

Produces CSVs for HDFC, ICICI, SBI, Axis, Kotak and an unknown layout, plus text-based PDFs
(one with a ruled table, one plain-text) for PDF parser tests. Output is deterministic.
"""
from __future__ import annotations

import csv
import random
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

OUT = Path(__file__).parent


@dataclass
class Txn:
    d: date
    name: str          # payee / merchant display text as banks print it
    vpa: str | None
    amount: float
    credit: bool
    kind: str          # upi_p2m | upi_p2a | neft | card | ach | atm | interest
    remark: str = "Payment"


MERCHANTS = [  # (name, vpa, min, max, weight)
    ("SWIGGY", "swiggy@icici", 180, 650, 9),
    ("ZOMATO", "zomato@hdfcbank", 200, 700, 7),
    ("BIGBASKET", "bigbasket@axisbank", 600, 2400, 3),
    ("BLINKIT", "blinkit.payu@hdfcbank", 150, 900, 4),
    ("AMAZON PAY INDIA", "amazonpay@apl", 299, 3500, 3),
    ("FLIPKART INTERNET", "flipkart@axisbank", 399, 2999, 2),
    ("UBER INDIA", "uber@paytm", 120, 480, 5),
    ("OLA CABS", "olacabs@ybl", 110, 420, 3),
    ("RAPIDO", "rapido@ybl", 45, 160, 3),
    ("INDIAN OIL PETROL PUMP", "iocl.fuel@ybl", 500, 2000, 2),
    ("APOLLO PHARMACY", "apollopharmacy@icici", 150, 1200, 1),
    ("BOOKMYSHOW", "bookmyshow@icici", 300, 900, 1),
    ("RAMESH TEA STALL", "ramesh.tea99@paytm", 20, 60, 4),
    ("DMART", "dmart@ybl", 400, 2500, 2),
]


def build_transactions(seed: int, start: date, months: int, salary: float, opening: float):
    rng = random.Random(seed)
    txns: list[Txn] = []
    first = start
    for m in range(months):
        y, mo = first.year + (first.month - 1 + m) // 12, (first.month - 1 + m) % 12 + 1
        ms = date(y, mo, 1)
        txns.append(Txn(ms, "ACME TECHNOLOGIES PVT LTD", None, salary, True, "neft", f"SALARY {ms:%b}".upper()))
        txns.append(Txn(ms + timedelta(days=4), "SURESH NAIR", "sureshnair@okhdfcbank", 18000, False, "upi_p2a", "RENT"))
        txns.append(Txn(ms + timedelta(days=6), "NETFLIX", None, 649, False, "ach"))
        txns.append(Txn(ms + timedelta(days=9), "SPOTIFY", "spotify@icici", 119, False, "upi_p2m"))
        txns.append(Txn(ms + timedelta(days=11), "BESCOM", "bescom@ybl", rng.randint(900, 1800), False, "upi_p2m"))
        txns.append(Txn(ms + timedelta(days=13), "AIRTEL", "airtel@paytm", 599, False, "upi_p2m"))
        txns.append(Txn(ms + timedelta(days=15), "GROWW", "groww.sip@icici", 5000, False, "upi_p2m", "SIP"))
        txns.append(Txn(ms + timedelta(days=20), "ATM", None, 3000, False, "atm"))
        if m == months - 1:
            txns.append(Txn(ms + timedelta(days=27), "SB INTEREST", None, 412.0, True, "interest"))
        days_in_month = ((date(y + (mo // 12), mo % 12 + 1, 1)) - ms).days
        for _ in range(rng.randint(26, 34)):
            name, vpa, lo, hi, _w = rng.choices(MERCHANTS, weights=[x[4] for x in MERCHANTS])[0]
            d = ms + timedelta(days=rng.randrange(days_in_month))
            kind = "card" if name.startswith(("AMAZON", "FLIPKART")) and rng.random() < 0.5 else "upi_p2m"
            txns.append(Txn(d, name, vpa, float(rng.randint(lo, hi)), False, kind))
        # a friend paying back
        txns.append(Txn(ms + timedelta(days=rng.randrange(8, 25)), "PRIYA S", "priya.s@oksbi", float(rng.randint(300, 1500)), True, "upi_p2a"))
    # deliberate anomalies in the last month
    last = date(first.year + (first.month - 1 + months - 1) // 12, (first.month - 1 + months - 1) % 12 + 1, 1)
    txns.append(Txn(last + timedelta(days=16), "FLIPKART INTERNET", "flipkart@axisbank", 48999, False, "upi_p2m"))
    for _ in range(4):  # burst of food orders in one day
        txns.append(Txn(last + timedelta(days=17), "SWIGGY", "swiggy@icici", float(rng.randint(250, 520)), False, "upi_p2m"))
    txns.append(Txn(last + timedelta(days=21), "ZOMATO", "zomato@hdfcbank", 455, False, "upi_p2m"))
    txns.append(Txn(last + timedelta(days=21), "ZOMATO", "zomato@hdfcbank", 455, False, "upi_p2m"))  # duplicate-looking

    txns.sort(key=lambda t: (t.d, not t.credit))
    bal = opening
    out = []
    for i, t in enumerate(txns):
        bal = round(bal + (t.amount if t.credit else -t.amount), 2)
        ref = f"5{seed % 10}{t.d:%m%d}{i:06d}"[:12].ljust(12, "0")
        out.append((t, bal, ref))
    return out


def ifsc(bank: str, n: int) -> str:
    return f"{bank}0{n:06d}"


def narration(bank: str, t: Txn, ref: str) -> str:
    up = t.name.upper()
    if t.kind in ("upi_p2m", "upi_p2a"):
        flow = "P2M" if t.kind == "upi_p2m" else "P2A"
        if bank == "hdfc":
            return f"UPI-{up}-{t.vpa}-{ifsc('ICIC', 103)}-{ref}-{t.remark}"
        if bank == "icici":
            return f"UPI/{ref}/{t.remark}/{t.vpa}/ICICI Bank"
        if bank == "sbi":
            return f"{'BY' if t.credit else 'TO'} TRANSFER-UPI/{'CR' if t.credit else 'DR'}/{ref}/{up}/YESB/{t.vpa}/{t.remark}--"
        if bank == "axis":
            return f"UPI/{flow}/{ref}/{t.name.title()}/{t.remark}/HDFC BANK"
        if bank == "kotak":
            return f"UPI/{up}/{ref}/{t.remark}"
        return f"UPI {up} {t.vpa} Ref {ref}"
    if t.kind == "neft":
        return {
            "sbi": f"BY TRANSFER-NEFT*{ifsc('HDFC', 1)}*N{ref[:9]}*{up}--",
            "axis": f"NEFT/N{ref[:9]}/{up}/{t.remark}",
        }.get(bank, f"NEFT CR-{ifsc('HDFC', 1)}-{up}-{t.remark}-N{ref[:9]}")
    if t.kind == "card":
        return f"POS 4111XXXXXXXX1234 {up}"
    if t.kind == "ach":
        return f"ACH D- {up} ENTERTAINMENT-{ref[:7]}"
    if t.kind == "atm":
        return f"ATW-512345XXXXXX1234-S1ANBG12-BANGALORE"
    if t.kind == "interest":
        return "SB INTEREST CREDIT" if bank != "hdfc" else "CREDIT INTEREST CAPITALISED"
    return up


def money(v: float) -> str:
    return f"{v:,.2f}"


def write_csv(path: Path, preamble: list[list[str]], header: list[str], rows: list[list[str]]):
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        for r in preamble:
            w.writerow(r)
        w.writerow(header)
        w.writerows(rows)


def gen_hdfc():
    data = build_transactions(11, date(2025, 8, 1), 3, 85000, 42000)
    rows = []
    for t, bal, ref in data:
        rows.append([
            f"{t.d:%d/%m/%y}", narration("hdfc", t, ref), ref[:16], f"{t.d:%d/%m/%y}",
            "" if t.credit else money(t.amount), money(t.amount) if t.credit else "", money(bal),
        ])
    write_csv(OUT / "hdfc_statement.csv",
              [["HDFC BANK Ltd."], ["Account Holder: DEMO USER"], ["Account No: XXXXXXXX4321"], ["IFSC: HDFC0000123"], []],
              ["Date", "Narration", "Chq./Ref.No.", "Value Dt", "Withdrawal Amt.", "Deposit Amt.", "Closing Balance"], rows)


def gen_icici():
    data = build_transactions(22, date(2025, 8, 1), 3, 72000, 15000)
    rows = []
    for i, (t, bal, ref) in enumerate(data, 1):
        rows.append([str(i), f"{t.d:%d/%m/%Y}", f"{t.d:%d/%m/%Y}", "-", narration("icici", t, ref),
                     "0.00" if t.credit else f"{t.amount:.2f}", f"{t.amount:.2f}" if t.credit else "0.00", f"{bal:.2f}"])
    write_csv(OUT / "icici_statement.csv",
              [["DETAILED STATEMENT"], ["ICICI Bank Limited"], ["Transactions List - DEMO USER - INR - XXXXXXXX9876"]],
              ["S No.", "Value Date", "Transaction Date", "Cheque Number", "Transaction Remarks",
               "Withdrawal Amount (INR )", "Deposit Amount (INR )", "Balance (INR )"], rows)


def gen_sbi():
    data = build_transactions(33, date(2025, 8, 1), 3, 64000, 23000)
    rows = []
    for t, bal, ref in data:
        rows.append([f"{t.d.day} {t.d:%b %Y}", f"{t.d.day} {t.d:%b %Y}", narration("sbi", t, ref), ref,
                     "" if t.credit else money(t.amount), money(t.amount) if t.credit else "", money(bal)])
    write_csv(OUT / "sbi_statement.csv",
              [["Account Name", ":DEMO USER"], ["Account Number", ":XXXXXXX5555"], ["Branch", ":STATE BANK OF INDIA - DEMO"],
               ["IFS Code", ":SBIN0001234"], []],
              ["Txn Date", "Value Date", "Description", "Ref No./Cheque No.", "Debit", "Credit", "Balance"], rows)
    return data


def gen_axis():
    data = build_transactions(44, date(2025, 8, 1), 3, 91000, 50000)
    rows = []
    for t, bal, ref in data:
        rows.append([f"{t.d:%d-%m-%Y}", "", narration("axis", t, ref), "" if t.credit else f"{t.amount:.2f}",
                     f"{t.amount:.2f}" if t.credit else "", f"{bal:.2f}", "1234"])
    write_csv(OUT / "axis_statement.csv",
              [["Statement of Axis Account No :XXXXXXXX7777 for the period"], ["DEMO USER"]],
              ["Tran Date", "CHQNO", "PARTICULARS", "DR", "CR", "BAL", "SOL"], rows)


def gen_kotak():
    data = build_transactions(55, date(2025, 8, 1), 3, 58000, 12000)
    rows = []
    for i, (t, bal, ref) in enumerate(data, 1):
        rows.append([str(i), f"{t.d:%d-%m-%Y}", f"{t.d:%d-%m-%Y}", narration("kotak", t, ref), ref,
                     f"{t.amount:,.2f}", "CR" if t.credit else "DR", f"{abs(bal):,.2f}", "CR" if bal >= 0 else "DR"])
    write_csv(OUT / "kotak_statement.csv",
              [["Kotak Mahindra Bank"], ["Account Statement - DEMO USER"], []],
              ["Sl. No.", "Transaction Date", "Value Date", "Description", "Chq / Ref No.", "Amount", "Dr / Cr", "Balance", "Dr / Cr"],
              rows)


def gen_unknown():
    """A layout no adapter knows - exercises the generic fallback (signed single amount column)."""
    data = build_transactions(66, date(2025, 9, 1), 2, 40000, 8000)
    rows = []
    for t, bal, ref in data:
        rows.append([t.d.isoformat(), narration("other", t, ref), f"{t.amount if t.credit else -t.amount:.2f}", f"{bal:.2f}"])
    write_csv(OUT / "unknown_bank_statement.csv", [["Neo Digital Bank - account export"]],
              ["Posting Date", "Transaction Details", "Amount", "Running Balance"], rows)


def gen_pdfs(sbi_data):
    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4, landscape
        from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.pdfgen import canvas
    except ImportError:
        print("reportlab not installed - skipping PDF samples")
        return
    styles = getSampleStyleSheet()
    small = styles["BodyText"].clone("small", fontSize=7, leading=8)

    # 1) ruled-table PDF (SBI layout)
    doc = SimpleDocTemplate(str(OUT / "sbi_statement.pdf"), pagesize=landscape(A4), leftMargin=20, rightMargin=20)
    header = ["Txn Date", "Value Date", "Description", "Ref No./Cheque No.", "Debit", "Credit", "Balance"]
    body = [header]
    for t, bal, ref in sbi_data[:60]:
        body.append([f"{t.d.day} {t.d:%b %Y}", f"{t.d.day} {t.d:%b %Y}", Paragraph(narration("sbi", t, ref), small), ref,
                     "" if t.credit else money(t.amount), money(t.amount) if t.credit else "", money(bal)])
    tbl = Table(body, colWidths=[60, 60, 330, 90, 70, 70, 80], repeatRows=1)
    tbl.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.4, colors.grey), ("FONTSIZE", (0, 0), (-1, -1), 7),
                             ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey)]))
    doc.build([Paragraph("STATE BANK OF INDIA - Account Statement (SYNTHETIC)", styles["Heading2"]),
               Paragraph("IFS Code: SBIN0001234 &nbsp; Account: XXXXXXX5555", styles["BodyText"]), Spacer(1, 8), tbl])

    # 2) plain-text PDF without ruling (exercises text-line fallback)
    data = build_transactions(77, date(2025, 10, 1), 1, 50000, 20000)
    c = canvas.Canvas(str(OUT / "plain_text_statement.pdf"), pagesize=A4)
    y = 800
    c.setFont("Helvetica", 9)
    c.drawString(40, y, "Sample Co-operative Bank - Statement of Account (SYNTHETIC)"); y -= 14
    c.drawString(40, y, f"Opening Balance: {money(20000)}"); y -= 20
    for t, bal, ref in data:
        if y < 50:
            c.showPage(); c.setFont("Helvetica", 9); y = 800
        desc = narration("other", t, ref)[:60]
        c.drawString(40, y, f"{t.d:%d/%m/%Y}  {desc}")
        c.drawRightString(470, y, money(t.amount))
        c.drawRightString(550, y, money(bal))
        y -= 13
    c.save()


LOCKED_PDF_PASSWORD = "DEMO1234"  # synthetic sample only


def gen_excel():
    """Excel variants banks actually send: real .xlsx, real binary .xls, and HTML saved as .xls."""
    # 1) .xlsx in HDFC layout with true date & numeric cells (not text)
    try:
        import openpyxl
        data = build_transactions(11, date(2025, 8, 1), 3, 85000, 42000)
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Statement"
        for r in [["HDFC BANK Ltd."], ["Account Holder: DEMO USER"], ["Account No: XXXXXXXX4321"], ["IFSC: HDFC0000123"], []]:
            ws.append(r)
        ws.append(["Date", "Narration", "Chq./Ref.No.", "Value Dt", "Withdrawal Amt.", "Deposit Amt.", "Closing Balance"])
        ws.append(["********", "********", "********", "********", "********", "********", "********"])
        from datetime import datetime as dt
        for t, bal, ref in data:
            d = dt(t.d.year, t.d.month, t.d.day)
            ws.append([d, narration("hdfc", t, ref), int(ref), d, None if t.credit else t.amount,
                       t.amount if t.credit else None, bal])
        wb.save(OUT / "hdfc_statement.xlsx")
    except ImportError:
        print("openpyxl not installed - skipping .xlsx sample")

    # 2) binary .xls (BIFF8) in ICICI layout, dates stored as Excel serial dates
    try:
        import xlwt
        data = build_transactions(22, date(2025, 8, 1), 3, 72000, 15000)
        book = xlwt.Workbook()
        sh = book.add_sheet("OpTransactionHistory")
        date_style = xlwt.easyxf(num_format_str="DD/MM/YYYY")
        row = 0
        for line in ["DETAILED STATEMENT", "ICICI Bank Limited", "Transactions List - DEMO USER - INR - XXXXXXXX9876", ""]:
            sh.write(row, 0, line); row += 1
        headers = ["S No.", "Value Date", "Transaction Date", "Cheque Number", "Transaction Remarks",
                   "Withdrawal Amount (INR )", "Deposit Amount (INR )", "Balance (INR )"]
        for c, h in enumerate(headers):
            sh.write(row, c, h)
        row += 1
        for i, (t, bal, ref) in enumerate(data, 1):
            vals = [i, t.d, t.d, "-", narration("icici", t, ref), 0.0 if t.credit else t.amount,
                    t.amount if t.credit else 0.0, bal]
            for c, v in enumerate(vals):
                sh.write(row, c, v, date_style) if isinstance(v, date) else sh.write(row, c, v)
            row += 1
        book.save(str(OUT / "icici_statement.xls"))
    except ImportError:
        print("xlwt not installed - skipping .xls sample")

    # 3) HTML table saved with a .xls extension (a very common "Excel" export)
    data = build_transactions(44, date(2025, 8, 1), 3, 91000, 50000)
    cells = lambda tag, vals: "<tr>" + "".join(f"<{tag}>{v}</{tag}>" for v in vals) + "</tr>"
    rows = [cells("td", ["Statement of Axis Account No :XXXXXXXX7777 for the period"]), cells("td", ["DEMO USER"]),
            cells("th", ["Tran Date", "CHQNO", "PARTICULARS", "DR", "CR", "BAL", "SOL"])]
    for t, bal, ref in data:
        rows.append(cells("td", [f"{t.d:%d-%m-%Y}", "", narration("axis", t, ref), "" if t.credit else f"{t.amount:.2f}",
                                 f"{t.amount:.2f}" if t.credit else "", f"{bal:.2f}", "1234"]))
    (OUT / "axis_statement_html.xls").write_text(
        "<html><head><meta charset='utf-8'></head><body><table border='1'>\n" + "\n".join(rows) + "\n</table></body></html>",
        encoding="utf-8")


def gen_locked_pdf():
    """Password-protected copy of the SBI PDF (password: DEMO1234), like real bank e-statements."""
    try:
        from reportlab.lib import pdfencrypt
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4, landscape
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.platypus import Paragraph, SimpleDocTemplate, Table, TableStyle
    except ImportError:
        return
    data = build_transactions(33, date(2025, 8, 1), 1, 64000, 23000)
    enc = pdfencrypt.StandardEncryption(LOCKED_PDF_PASSWORD, ownerPassword="owner-" + LOCKED_PDF_PASSWORD, strength=128)
    doc = SimpleDocTemplate(str(OUT / "sbi_statement_locked.pdf"), pagesize=landscape(A4), encrypt=enc)
    small = getSampleStyleSheet()["BodyText"].clone("s", fontSize=7, leading=8)
    body = [["Txn Date", "Value Date", "Description", "Ref No./Cheque No.", "Debit", "Credit", "Balance"]]
    for t, bal, ref in data:
        body.append([f"{t.d.day} {t.d:%b %Y}", f"{t.d.day} {t.d:%b %Y}", Paragraph(narration("sbi", t, ref), small), ref,
                     "" if t.credit else money(t.amount), money(t.amount) if t.credit else "", money(bal)])
    tbl = Table(body, colWidths=[60, 60, 330, 90, 70, 70, 80], repeatRows=1)
    tbl.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.4, colors.grey), ("FONTSIZE", (0, 0), (-1, -1), 7)]))
    doc.build([Paragraph("STATE BANK OF INDIA - Account Statement (SYNTHETIC, password DEMO1234)",
                         getSampleStyleSheet()["Heading2"]), tbl])


# ---------------------------------------------------------------- credit cards (SYNTHETIC)
CARD_MERCHANTS = [  # (statement text as issuers print it, min, max, weight)
    ("SWIGGY BANGALORE IN", 180, 650, 9),
    ("ZOMATO GURGAON IN", 200, 700, 6),
    ("AMAZON PAY INDIA PRIVATE LIMITED MUMBAI IN", 299, 6500, 5),
    ("FLIPKART INTERNET PRIVATE BANGALORE IN", 499, 8999, 3),
    ("UBER INDIA SYSTEMS PVT LTD BANGALORE IN", 120, 480, 5),
    ("BIGBASKET INNOVATIVE RETAIL BANGALORE IN", 600, 2400, 3),
    ("INDIAN OIL PETROL PUMP PUNE IN", 500, 3000, 2),
    ("IRCTC NEW DELHI IN", 450, 2800, 1),
    ("NETFLIX.COM SINGAPORE SG", 649, 649, 1),
    ("APOLLO PHARMACY CHENNAI IN", 150, 1400, 2),
    ("BOOKMYSHOW MUMBAI IN", 300, 1200, 1),
]


def build_card_transactions(seed: int = 21, start: date = date(2025, 8, 1)):
    """One month of card activity: purchases, fees with GST, a refund and the bill payment received."""
    rng = random.Random(seed)
    names = [m[0] for m in CARD_MERCHANTS]
    weights = [m[3] for m in CARD_MERCHANTS]
    rows = []  # (date, description, amount, is_credit)
    for day in range(1, 29):
        for _ in range(rng.choice([0, 1, 1, 2])):
            name = rng.choices(names, weights)[0]
            lo, hi = next((m[1], m[2]) for m in CARD_MERCHANTS if m[0] == name)
            rows.append((start.replace(day=day), name, float(rng.randint(lo, hi)), False))
    rows.append((start.replace(day=3), "ANNUAL FEE", 499.00, False))
    rows.append((start.replace(day=3), "IGST-CGST @18%", 89.82, False))
    rows.append((start.replace(day=20), "FINANCE CHARGES", 312.40, False))
    rows.append((start.replace(day=14), "REFUND AMAZON PAY INDIA PRIVATE LIMITED MUMBAI IN", 1299.00, True))
    rows.append((start.replace(day=9), "PAYMENT RECEIVED - THANK YOU", 40000.00, True))
    return sorted(rows, key=lambda r: (r[0], r[1]))


def gen_cards():
    data = build_card_transactions()
    hdr = ["HDFC Bank Credit Cards", "Credit Card Statement for card ending 4321 (SYNTHETIC)", ""]
    rows = [[f"{d:%d/%m/%Y} {9 + i % 12:02d}:{(i * 7) % 60:02d}:00", desc, money(a) + (" Cr" if cr else "")]
            for i, (d, desc, a, cr) in enumerate(data)]
    write_csv(OUT / "hdfc_credit_card.csv", [[h] for h in hdr], ["Date", "Transaction Description", "Amount (in Rs.)"], rows)

    rows = [[f"{d:%d/%m/%Y}", str(1100000 + i), desc, str(int(a // 100)) if not cr else "0", "0", money(a), "CR" if cr else ""]
            for i, (d, desc, a, cr) in enumerate(data)]
    for r in rows:
        if "PAYMENT RECEIVED" in r[2]:
            r[2] = "BBPS Payment received"
    write_csv(OUT / "icici_credit_card.csv", [], ["Date", "SerNo.", "Transaction Details", "Reward Points", "Intl.#", "Amount (in Rs)", "BillingAmountSign"], rows)

    rows = [[f"{d:%d %b %y}", desc, money(a) + (" C" if cr else " D")] for d, desc, a, cr in data]
    write_csv(OUT / "sbi_credit_card.csv", [["SBI Card - Statement of Account (SYNTHETIC)"], ["Card Number XXXX XXXX XXXX 7788"], []],
              ["Date", "Transaction Details", "Amount ( ₹ )"], rows)

    cats = ["FOOD", "SHOPPING", "TRAVEL", "FUEL", "ENTERTAINMENT", "HEALTH", "UTILITIES"]
    rows = [[f"{d:%d/%m/%Y}", desc, cats[i % len(cats)], money(a) + (" Cr" if cr else " Dr")] for i, (d, desc, a, cr) in enumerate(data)]
    write_csv(OUT / "axis_credit_card.csv", [["Axis Bank Credit Card Statement (SYNTHETIC)"], []],
              ["Date", "Transaction Details", "Merchant Category", "Amount (Rs.)"], rows)

    # no issuer name anywhere: only the format list (generic_card) can tell this is a card
    rows = [[f"{d:%Y-%m-%d}", desc, money(a) + (" Cr" if cr else "")] for d, desc, a, cr in data]
    write_csv(OUT / "card_unknown_issuer.csv", [], ["Posting Date", "Description", "Amount"], rows)


def gen_card_pdf():
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.pdfgen import canvas
    except ImportError:
        return
    data = build_card_transactions()
    c = canvas.Canvas(str(OUT / "credit_card_statement.pdf"), pagesize=A4)
    y = 800
    c.setFont("Helvetica", 9)
    for line in ("Sample Issuer Credit Card Statement (SYNTHETIC)", "Statement Period: 01/08/2025 to 31/08/2025",
                 "Credit Limit: 2,00,000.00    Total Amount Due: 45,230.00    Payment Due Date: 18/09/2025"):
        c.drawString(40, y, line); y -= 14
    y -= 8
    for d, desc, a, cr in data:
        if y < 50:
            c.showPage(); c.setFont("Helvetica", 9); y = 800
        c.drawString(40, y, f"{d:%d/%m/%Y}  {desc[:62]}")
        c.drawRightString(550, y, money(a) + (" Cr" if cr else ""))
        y -= 13
    c.save()


if __name__ == "__main__":
    gen_hdfc(); gen_icici(); sbi = gen_sbi(); gen_axis(); gen_kotak(); gen_unknown(); gen_pdfs(sbi)
    gen_excel(); gen_locked_pdf(); gen_cards(); gen_card_pdf()
    print("Synthetic samples written to", OUT)
