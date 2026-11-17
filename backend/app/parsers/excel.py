"""Excel statement reading (.xlsx / .xls) -> StatementTable.

Indian banks' "Excel" downloads come in several shapes, identified by content, not extension:
  * real .xlsx (zip / Office Open XML)              -> openpyxl (read-only, values only)
  * real .xls (BIFF, OLE compound file)            -> xlrd
  * an HTML table saved with a .xls extension      -> stdlib HTML parser
  * tab/comma-delimited text saved as .xls         -> CSV reader
Each worksheet is tried in turn; the first one with a recognisable transaction header wins.
Files are treated as untrusted: zip-bomb limits, row caps, and defusedxml for XML parsing.
"""
from __future__ import annotations

import io
import re
import zipfile
from datetime import date, datetime
from html.parser import HTMLParser

from app.parsers.base import ParseError, StatementTable
from app.parsers.readers import _build_table, decode_text, read_csv

MAX_ROWS = 100_000
MAX_SHEETS = 20
MAX_UNCOMPRESSED = 200 * 1024 * 1024  # xlsx zip-bomb guard
HEADER_SCAN = 200  # Excel exports often carry long account-summary preambles

OLE_MAGIC = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"
ZIP_MAGIC = b"PK\x03\x04"
_ENCRYPTED_OLE = "EncryptedPackage".encode("utf-16-le")

ENCRYPTED_EXCEL_MSG = (
    "This Excel file is password protected. Open it in Excel and save a copy without a password, "
    "or download the statement as CSV or PDF instead."
)


def _cell(v) -> str:
    """Normalise a cell value to text the bank adapters understand."""
    if v is None:
        return ""
    if isinstance(v, datetime):
        return v.strftime("%Y-%m-%d")  # unambiguous; parse_date handles ISO
    if isinstance(v, date):
        return v.isoformat()
    if isinstance(v, bool):
        return str(v)
    if isinstance(v, float):
        # 529012345678.0 (a reference stored as a number) -> "529012345678"
        return str(int(v)) if v.is_integer() and abs(v) < 1e15 else repr(v)
    return str(v).strip()


def _table_from_sheets(sheets: list[list[list[str]]], source: str) -> StatementTable:
    last_error: ParseError | None = None
    for rows in sheets:
        if not rows:
            continue
        try:
            return _build_table(rows, source, scan=HEADER_SCAN)
        except ParseError as e:
            last_error = e
    raise last_error or ParseError("The spreadsheet is empty.")


# ---------------------------------------------------------------- .xlsx
def _read_xlsx(content: bytes) -> list[list[list[str]]]:
    try:
        zf = zipfile.ZipFile(io.BytesIO(content))
    except zipfile.BadZipFile:
        raise ParseError("The Excel file is corrupted or not a valid .xlsx file.") from None
    with zf:
        if len(zf.infolist()) > 2000 or sum(i.file_size for i in zf.infolist()) > MAX_UNCOMPRESSED:
            raise ParseError("The Excel file is too large to process.")
        if "xl/workbook.xml" not in zf.namelist():
            raise ParseError("The file is not a valid Excel workbook.")

    import openpyxl  # uses defusedxml automatically when installed

    try:
        wb = openpyxl.load_workbook(io.BytesIO(content), read_only=True, data_only=True)
    except Exception:
        raise ParseError("The Excel file could not be opened. It may be corrupted.") from None
    sheets = []
    try:
        for ws in wb.worksheets[:MAX_SHEETS]:
            rows = []
            for i, r in enumerate(ws.iter_rows(values_only=True)):
                if i >= MAX_ROWS:
                    break
                rows.append([_cell(v) for v in r])
            # trailing all-empty columns are common in exports
            sheets.append([r for r in rows])
    finally:
        wb.close()
    return sheets


# ---------------------------------------------------------------- .xls (BIFF)
def _read_xls(content: bytes) -> list[list[list[str]]]:
    if _ENCRYPTED_OLE in content[:200_000]:
        raise ParseError(ENCRYPTED_EXCEL_MSG)  # an encrypted .xlsx is stored as an OLE container
    import xlrd

    try:
        book = xlrd.open_workbook(file_contents=content, on_demand=True)
    except xlrd.XLRDError as e:
        if "encrypt" in str(e).lower():
            raise ParseError(ENCRYPTED_EXCEL_MSG) from None
        raise ParseError("The .xls file could not be opened. It may be corrupted.") from None
    except Exception:
        raise ParseError("The .xls file could not be opened. It may be corrupted.") from None
    sheets = []
    try:
        for idx in range(min(book.nsheets, MAX_SHEETS)):
            sh = book.sheet_by_index(idx)
            rows = []
            for r in range(min(sh.nrows, MAX_ROWS)):
                out = []
                for c in range(sh.ncols):
                    cell = sh.cell(r, c)
                    if cell.ctype == xlrd.XL_CELL_DATE:
                        try:
                            out.append(_cell(xlrd.xldate_as_datetime(cell.value, book.datemode)))
                        except Exception:
                            out.append(_cell(cell.value))
                    else:
                        out.append(_cell(cell.value))
                rows.append(out)
            sheets.append(rows)
            book.unload_sheet(idx)
    finally:
        book.release_resources()
    return sheets


# ---------------------------------------------------------------- HTML disguised as .xls
class _TableParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.rows: list[list[str]] = []
        self._row: list[str] | None = None
        self._cell: list[str] | None = None

    def handle_starttag(self, tag, attrs):
        if tag == "tr":
            self._row = []
        elif tag in ("td", "th") and self._row is not None:
            self._cell = []
        elif tag == "br" and self._cell is not None:
            self._cell.append(" ")

    def handle_endtag(self, tag):
        if tag in ("td", "th") and self._row is not None and self._cell is not None:
            self._row.append(re.sub(r"\s+", " ", "".join(self._cell)).strip())
            self._cell = None
        elif tag == "tr" and self._row is not None:
            if any(self._row) and len(self.rows) < MAX_ROWS:
                self.rows.append(self._row)
            self._row = None

    def handle_data(self, data):
        if self._cell is not None:
            self._cell.append(data)


def _read_html(text: str) -> list[list[list[str]]]:
    p = _TableParser()
    p.feed(text)
    p.close()
    return [p.rows]


# ---------------------------------------------------------------- entry point
def read_excel(content: bytes) -> StatementTable:
    head = content[:8]
    if head.startswith(ZIP_MAGIC):
        return _table_from_sheets(_read_xlsx(content), "xlsx")
    if head.startswith(OLE_MAGIC):
        return _table_from_sheets(_read_xls(content), "xls")
    text = decode_text(content)
    if re.search(r"<\s*(table|html|tr)\b", text[:5000], re.IGNORECASE):
        return _table_from_sheets(_read_html(text), "xls-html")
    table = read_csv(content)  # tab/comma-delimited text with an Excel extension
    table.source = "xls-text"
    return table
