"""One-page-ish spending report as a PDF. Pure: takes plain data, returns bytes.

Amounts are written "Rs. 1,02,509" (Indian grouping). The standard PDF fonts have no rupee sign, and a missing glyph
would print as a black box, so the symbol is spelled out.
"""
from __future__ import annotations

import io
import re
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

BRAND = colors.HexColor("#2F7D55")
INK = colors.HexColor("#14213D")
MUTED = colors.HexColor("#6B7280")
LINE = colors.HexColor("#E8E8E1")
TINT = colors.HexColor("#F6F6F1")
STATUS_LABEL = {"ok": "On track", "warning": "Nearly there", "over": "Over budget"}
STATUS_COLOR = {"ok": BRAND, "warning": colors.HexColor("#B7791F"), "over": colors.HexColor("#C2413B")}


def inr(value: float | None, decimals: int = 0) -> str:
    """Rs. 1,02,509 - Indian digit grouping."""
    if value is None:
        return "-"
    v = round(float(value), decimals)
    whole, _, frac = f"{abs(v):.{decimals}f}".partition(".")
    whole = re.sub(r"(\d)(?=(\d\d)+\d$)", r"\1,", whole)
    return f"{'-' if v < 0 else ''}Rs. {whole}{'.' + frac if frac else ''}"


def _signed(pct: float | None) -> str:
    return "no earlier data" if pct is None else f"{pct:+.1f}% vs previous period"


def _styles():
    base = getSampleStyleSheet()
    return {
        "h1": ParagraphStyle("h1", parent=base["Heading1"], fontSize=20, textColor=INK, spaceAfter=2),
        "sub": ParagraphStyle("sub", parent=base["BodyText"], fontSize=10, textColor=MUTED, spaceAfter=10),
        "h2": ParagraphStyle("h2", parent=base["Heading2"], fontSize=12.5, textColor=INK, spaceBefore=14, spaceAfter=6,
                             keepWithNext=1),  # a heading is never left alone at the foot of a page
        "cell": ParagraphStyle("cell", parent=base["BodyText"], fontSize=8.5, leading=10.5, textColor=INK),
        "right": ParagraphStyle("right", parent=base["BodyText"], fontSize=8.5, leading=10.5, textColor=INK, alignment=TA_RIGHT),
        "label": ParagraphStyle("label", parent=base["BodyText"], fontSize=8, textColor=MUTED),
        "value": ParagraphStyle("value", parent=base["BodyText"], fontSize=15, leading=18, textColor=INK, fontName="Helvetica-Bold"),
        "note": ParagraphStyle("note", parent=base["BodyText"], fontSize=8, leading=10, textColor=MUTED),
    }


def _p(text, style) -> Paragraph:
    """Paragraph from untrusted text (merchant names can contain < & >)."""
    return Paragraph(escape(str(text)), style)


def _table(header: list[str], rows: list[list], widths: list[float], st: dict, right_cols: set[int]) -> Table:
    head = [_p(h, ParagraphStyle("th", parent=st["label"], fontName="Helvetica-Bold", alignment=TA_RIGHT if i in right_cols else 0))
            for i, h in enumerate(header)]
    body = [[_p(c, st["right"] if i in right_cols else st["cell"]) if not isinstance(c, Paragraph) else c
             for i, c in enumerate(r)] for r in rows]
    t = Table([head] + body, colWidths=widths, repeatRows=1)
    t.setStyle(TableStyle([
        ("LINEBELOW", (0, 0), (-1, 0), 0.8, BRAND), ("LINEBELOW", (0, 1), (-1, -1), 0.3, LINE),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    return t


def _footer(canvas, doc):
    canvas.saveState()
    canvas.setFont("Helvetica", 7.5)
    canvas.setFillColor(MUTED)
    canvas.drawString(18 * mm, 10 * mm, "Tally - generated from the statements you uploaded. Figures are only as complete as those statements.")
    canvas.drawRightString(A4[0] - 18 * mm, 10 * mm, f"Page {doc.page}")
    canvas.restoreState()


def build_summary_pdf(r: dict) -> bytes:
    """`r`: period_label, generated, statement (optional), totals, changes (optional), categories, merchants,
    monthly, budgets (optional), excluded_payments."""
    st = _styles()
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm, topMargin=16 * mm, bottomMargin=18 * mm,
                            title=f"Spending report - {r['period_label']}", author="Tally")
    width = A4[0] - 36 * mm
    t = r["totals"]
    story = [_p("Spending report", st["h1"]),
             _p(f"{r['period_label']}" + (f"  |  Account: {r['account']}" if r.get("account") else "")
                + (f"  |  Statement: {r['statement']}" if r.get("statement") else "")
                + f"  |  Generated {r['generated']}", st["sub"])]

    if not t["transaction_count"]:
        story.append(_p("There are no transactions in this period.", st["cell"]))
        doc.build(story, onFirstPage=_footer, onLaterPages=_footer)
        return buf.getvalue()

    ch = r.get("changes") or {}
    tiles = [
        ("Income", inr(t["total_income"]), _signed(ch.get("total_income")) if ch else ""),
        ("Expenses", inr(t["total_expenses"]), _signed(ch.get("total_expenses")) if ch else ""),
        ("Net", inr(t["net_balance"]), f"Savings rate {t['savings_rate']}%" if t.get("savings_rate") is not None else ""),
        ("Transactions", f"{t['transaction_count']:,}", f"{t['debit_count']:,} debits, {t['credit_count']:,} credits"),
        ("UPI spending", inr(t["upi_spending"]), f"{t['upi_transaction_count']:,} UPI payments"),
        ("Average per day", inr(t["avg_daily_spending"]), f"over {t['days']} days"),
    ]
    cells = [[[_p(label, st["label"]), _p(value, st["value"]), _p(sub, st["note"])] for label, value, sub in tiles[:3]],
             [[_p(label, st["label"]), _p(value, st["value"]), _p(sub, st["note"])] for label, value, sub in tiles[3:]]]
    grid = Table(cells, colWidths=[width / 3] * 3)
    grid.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), TINT), ("BOX", (0, 0), (-1, -1), 0.5, LINE),
                              ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.white), ("VALIGN", (0, 0), (-1, -1), "TOP"),
                              ("TOPPADDING", (0, 0), (-1, -1), 7), ("BOTTOMPADDING", (0, 0), (-1, -1), 7)]))
    story += [grid]
    if r.get("excluded_payments"):
        n = r["excluded_payments"]
        story += [Spacer(1, 4), _p(f"{n} credit card bill payment{'s' if n != 1 else ''} are left out of income and expenses, "
                                   "because the card's own purchases are already counted.", st["note"])]

    cats = r["categories"]
    if cats:
        story.append(_p("Where the money went", st["h2"]))
        rows = [["", c["name"], inr(c["amount"]), f"{c['percentage']}%", f"{c['count']:,}"] for c in cats]
        tbl = _table(["", "Category", "Spent", "Share", "Transactions"], rows, [6 * mm, width - 76 * mm, 30 * mm, 18 * mm, 22 * mm], st, {2, 3, 4})
        tbl.setStyle(TableStyle([("BACKGROUND", (0, i + 1), (0, i + 1), colors.HexColor(c["color"])) for i, c in enumerate(cats)]
                                + [("LINEBELOW", (0, 1), (0, -1), 2, colors.white)]))
        story.append(tbl)

    if r["merchants"]:
        story.append(_p("Top merchants", st["h2"]))
        rows = [[m["merchant"], m.get("category") or "-", f"{m['count']:,}", inr(m["total"])] for m in r["merchants"]]
        story.append(_table(["Merchant", "Category", "Payments", "Total"], rows, [width - 94 * mm, 40 * mm, 22 * mm, 32 * mm], st, {2, 3}))

    if len(r["monthly"]) >= 2:
        story.append(_p("Month by month", st["h2"]))
        rows = [[m["label"], inr(m["income"]), inr(m["expense"]), inr(m["net"])] for m in r["monthly"]]
        story.append(_table(["Month", "Income", "Expenses", "Net"], rows, [width - 96 * mm, 32 * mm, 32 * mm, 32 * mm], st, {1, 2, 3}))

    b = r.get("budgets")
    if b and (b["overall"] or b["budgets"]):
        story.append(_p(f"Budgets - {b['month']['label']}", st["h2"]))
        rows = []
        for x in ([b["overall"]] if b["overall"] else []) + b["budgets"]:
            label = Paragraph(f'<font color="{STATUS_COLOR[x["status"]].hexval().replace("0x", "#")}">{STATUS_LABEL[x["status"]]}</font>', st["cell"])
            rows.append([x["name"], inr(x["spent"]), inr(x["monthly_limit"]), f"{round(x['percent'])}%", label])
        story.append(_table(["Budget", "Spent", "Limit", "Used", "Status"], rows, [width - 112 * mm, 30 * mm, 30 * mm, 18 * mm, 34 * mm], st, {1, 2, 3}))

    doc.build(story, onFirstPage=_footer, onLaterPages=_footer)
    return buf.getvalue()
