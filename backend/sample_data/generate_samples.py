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


if __name__ == "__main__":
    gen_hdfc(); gen_icici(); sbi = gen_sbi(); gen_axis(); gen_kotak(); gen_unknown(); gen_pdfs(sbi)
    print("Synthetic samples written to", OUT)
