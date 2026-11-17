"""Turn raw CSV / PDF bytes into a StatementTable (header row + data rows + text). Excel: see excel.py.

Bank exports often have account-holder preambles before the real header row, so the header row
is located by scoring the first rows for date/description/amount keywords.
"""
from __future__ import annotations

import csv
import io
import logging
import re

from app.parsers.base import ParseError, PasswordRequired, StatementTable, norm_header
from app.utils.dates import parse_date
from app.utils.money import parse_amount

log = logging.getLogger("tally.parsers")

_DATE_HDR = re.compile(r"date|dt$")
_DESC_HDR = re.compile(r"narration|description|particulars|remarks|details|memo|payee")
_AMT_HDR = re.compile(r"withdrawal|deposit|debit|credit|amount|amt|^dr$|^cr$|paidout|paidin|balance|^bal$")


def _header_score(row: list[str]) -> int:
    cells = [norm_header(c) for c in row if str(c or "").strip()]
    if len(cells) < 3:
        return 0
    score = 0
    score += 2 if any(_DATE_HDR.search(c) for c in cells) else 0
    score += 2 if any(_DESC_HDR.search(c) for c in cells) else 0
    score += min(3, sum(1 for c in cells if _AMT_HDR.search(c)))
    return score


def _find_header(rows: list[list[str]], scan: int = 60) -> int:
    best_idx, best = -1, 0
    for i, row in enumerate(rows[:scan]):
        s = _header_score(row)
        if s > best:
            best_idx, best = i, s
        if s >= 6:
            break
    if best < 4:
        raise ParseError("Could not locate the transaction table header (date / description / amount columns).")
    return best_idx


def _dedupe_headers(headers: list[str]) -> list[str]:
    seen: dict[str, int] = {}
    out = []
    for h in headers:
        h = re.sub(r"\s+", " ", str(h or "")).strip()
        if h in seen:
            seen[h] += 1
            out.append(f"{h}_{seen[h]}")
        else:
            seen[h] = 1
            out.append(h)
    return out


def _build_table(rows: list[list[str]], source: str, extra_text: str = "", scan: int = 60) -> StatementTable:
    rows = [[("" if c is None else str(c)) for c in r] for r in rows]
    h = _find_header(rows, scan)
    headers = _dedupe_headers(rows[h])
    preamble = "\n".join(" ".join(c for c in r if c) for r in rows[:h])
    data = [r + [""] * (len(headers) - len(r)) if len(r) < len(headers) else r for r in rows[h + 1:]]
    return StatementTable(headers=headers, rows=data, text=(preamble + "\n" + extra_text).strip(), source=source)


# ---------------------------------------------------------------- CSV
def decode_text(content: bytes) -> str:
    for enc in ("utf-8-sig", "utf-16", "cp1252", "latin-1"):
        try:
            text = content.decode(enc)
            if enc == "utf-16" and "\x00" in text:
                continue
            return text
        except UnicodeDecodeError:
            continue
    raise ParseError("Unable to decode the file. Please upload a UTF-8 or Windows-1252 encoded CSV.")


def read_csv(content: bytes) -> StatementTable:
    text = decode_text(content)
    if not text.strip():
        raise ParseError("The file is empty.")
    sample = text[:20000]
    delimiter = ","
    try:
        delimiter = csv.Sniffer().sniff(sample, delimiters=",;\t|").delimiter
    except csv.Error:
        counts = {d: sample.count(d) for d in ",;\t|"}
        delimiter = max(counts, key=counts.get)
    rows = list(csv.reader(io.StringIO(text), delimiter=delimiter))
    if len(rows) < 2:
        raise ParseError("The CSV does not contain any transaction rows.")
    return _build_table(rows, "csv")


# ---------------------------------------------------------------- PDF
def _open_pdf(content: bytes, password: str | None = None):
    """Open a PDF, unlocking it with `password` if encrypted (RC4 / AES-128 / AES-256).
    The password is only used in memory for this call - never stored or logged."""
    import pdfplumber
    from pdfminer.pdfdocument import PDFEncryptionError, PDFPasswordIncorrect

    try:
        pdf = pdfplumber.open(io.BytesIO(content), password=password or "")
        _ = pdf.pages  # force document parsing so decryption problems surface here
        return pdf
    except PDFPasswordIncorrect:
        raise PasswordRequired(incorrect=bool(password)) from None
    except PDFEncryptionError:
        raise ParseError("This PDF uses an encryption method that isn't supported. "
                         "Please download an unlocked copy or a CSV/Excel statement.") from None
    except Exception as exc:  # pdfminer raises a variety of errors
        msg = str(exc).lower()
        if "password" in msg or "encrypt" in msg:
            raise PasswordRequired(incorrect=bool(password)) from None
        raise ParseError("The PDF could not be opened. It may be corrupted.") from None


def read_pdf(content: bytes, password: str | None = None) -> StatementTable:
    pdf = _open_pdf(content, password)
    try:
        if len(pdf.pages) > 200:
            raise ParseError("PDF has too many pages (max 200).")
        texts: list[str] = []
        table_rows: list[list[str]] = []
        for page in pdf.pages:
            try:
                texts.append(page.extract_text() or "")
            except Exception:
                texts.append("")
            try:
                for tbl in page.extract_tables() or []:
                    for r in tbl:
                        table_rows.append([re.sub(r"\s*\n\s*", " ", c or "").strip() for c in r])
            except Exception:
                continue
        full_text = "\n".join(texts)

        if len(full_text.strip()) < 30:
            ocr_text = _ocr_pdf(pdf)
            return read_text_lines(ocr_text, source="pdf-ocr")

        if table_rows:
            try:
                return _build_table(table_rows, "pdf", extra_text=texts[0][:1500] if texts else "")
            except ParseError:
                log.info("PDF tables found but no header; falling back to text-line parsing")
        return read_text_lines(full_text, source="pdf-text")
    finally:
        pdf.close()


def _ocr_pdf(pdf) -> str:
    """OCR for scanned PDFs. Optional: requires `pytesseract` + the Tesseract binary."""
    try:
        import pytesseract  # type: ignore
    except ImportError:
        raise ParseError(
            "This PDF looks scanned (no text layer). OCR support needs 'pytesseract' and Tesseract installed; "
            "alternatively download a CSV or text PDF from your bank."
        ) from None
    out = []
    try:
        for page in pdf.pages:
            img = page.to_image(resolution=300).original
            out.append(pytesseract.image_to_string(img))
    except Exception:
        raise ParseError("OCR failed for this scanned PDF. Please upload a CSV or text-based PDF.") from None
    text = "\n".join(out)
    if len(text.strip()) < 30:
        raise ParseError("No readable text found in this scanned PDF.")
    return text


# ---------------------------------------------------------------- text-line fallback
_LINE_DATE = re.compile(
    r"^\s*(\d{1,2}[/\-.](?:\d{1,2}|[A-Za-z]{3})[/\-.]\d{2,4}|\d{1,2}\s+[A-Za-z]{3,9},?\s+\d{2,4}|\d{4}-\d{2}-\d{2})\s+(.*)$"
)
_TRAIL_AMT = re.compile(r"(-?\(?[\d,]+\.\d{2}\)?(?:\s*(?:Dr|Cr)\.?)?)\s*$", re.IGNORECASE)
_OPENING = re.compile(r"opening\s+balance[^\d\-]*(-?[\d,]+\.\d{2})", re.IGNORECASE)


def read_text_lines(text: str, source: str = "pdf-text") -> StatementTable:
    """Parse statements without detectable tables: one transaction per line starting with a date,
    ending in [amount] [balance]. Debit vs credit is inferred from the running balance movement,
    falling back to Dr/Cr markers and keywords."""
    rows: list[list[str]] = []
    prev_balance = None
    m = _OPENING.search(text)
    if m:
        prev_balance = parse_amount(m.group(1))

    last_row = None
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        dm = _LINE_DATE.match(line)
        if not dm or parse_date(dm.group(1)) is None:
            if last_row is not None and not _TRAIL_AMT.search(line) and len(line) < 120:
                last_row[1] = f"{last_row[1]} {line}"  # wrapped narration
            continue
        rest = dm.group(2)
        amounts: list[str] = []
        while len(amounts) < 3:
            am = _TRAIL_AMT.search(rest)
            if not am:
                break
            amounts.insert(0, am.group(1))
            rest = rest[: am.start()].rstrip()
        if not amounts:
            continue
        # strip a leading value-date if present
        rest = re.sub(r"^(\d{1,2}[/\-.](?:\d{1,2}|[A-Za-z]{3})[/\-.]\d{2,4})\s+", "", rest)
        desc = rest.strip()
        balance = parse_amount(amounts[-1]) if len(amounts) >= 2 else None
        if len(amounts) >= 3:
            # [debit] [credit] [balance] where one of debit/credit is usually 0.00
            d, c = parse_amount(amounts[-3]) or 0.0, parse_amount(amounts[-2]) or 0.0
            debit, credit = abs(d), abs(c)
        else:
            amt_raw = amounts[0]
            amt = abs(parse_amount(amt_raw) or 0.0)
            if balance is not None and prev_balance is not None and abs(abs(balance - prev_balance) - amt) < 0.01:
                is_credit = balance > prev_balance
            elif re.search(r"cr\.?$", amt_raw, re.IGNORECASE):
                is_credit = True
            elif re.search(r"dr\.?$", amt_raw, re.IGNORECASE) or (parse_amount(amt_raw) or 0) < 0:
                is_credit = False
            else:
                is_credit = bool(re.search(r"\b(CR|CREDIT|SALARY|REFUND|INTEREST|BY TRANSFER|DEPOSIT)\b", desc.upper()))
            debit, credit = (0.0, amt) if is_credit else (amt, 0.0)
        if balance is not None:
            prev_balance = balance
        last_row = [dm.group(1), desc, f"{debit:.2f}", f"{credit:.2f}", "" if balance is None else f"{balance:.2f}"]
        rows.append(last_row)

    if not rows:
        raise ParseError("No transaction lines were recognised in this PDF.")
    return StatementTable(
        headers=["Date", "Description", "Debit", "Credit", "Balance"], rows=rows, text=text[:5000], source=source
    )
