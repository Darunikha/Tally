"""Common parser interface.

Every bank adapter receives a `StatementTable` (header row + data rows + surrounding text) produced
by the CSV/PDF readers, and returns `ParsedTransaction`s. Adding a bank means adding one adapter
class with its column aliases and detection markers; the import pipeline does not change.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime

from app.utils.dates import parse_date
from app.utils.money import parse_amount
from app.utils.upi import UpiDetails, extract_upi


class ParseError(Exception):
    """Raised when a statement cannot be read/parsed. Message is safe to show to the user."""


def norm_header(h: str) -> str:
    return re.sub(r"[^a-z0-9]", "", str(h or "").lower())


@dataclass
class StatementTable:
    headers: list[str]
    rows: list[list[str]]
    text: str = ""            # preamble / full text used for bank identification
    source: str = "csv"       # "csv" | "pdf" | "pdf-text" | "pdf-ocr"

    @property
    def norm_headers(self) -> list[str]:
        return [norm_header(h) for h in self.headers]


@dataclass
class ParsedTransaction:
    transaction_date: datetime
    description: str
    debit_amount: float = 0.0
    credit_amount: float = 0.0
    balance: float | None = None
    reference: str | None = None
    value_date: datetime | None = None
    raw_fields: dict = field(default_factory=dict)
    row_number: int = 0

    @property
    def transaction_type(self) -> str:
        return "credit" if self.credit_amount > 0 else "debit"


@dataclass
class ParseResult:
    bank_name: str
    parser_used: str
    transactions: list[ParsedTransaction]
    warnings: list[str] = field(default_factory=list)
    skipped_rows: int = 0


CANONICAL = ("date", "value_date", "description", "debit", "credit", "amount", "dr_cr", "balance", "reference")

_SKIP_DESC = re.compile(
    r"^\s*(OPENING\s+BALANCE|CLOSING\s+BALANCE|BALANCE\s+B/?F|BALANCE\s+C/?F|B/F|C/F|TOTAL|GRAND\s+TOTAL|"
    r"STATEMENT\s+SUMMARY|\*+\s*END)", re.IGNORECASE
)


class BaseBankParser:
    key: str = "base"
    bank_name: str = "Unknown"
    # canonical column -> accepted header spellings (compared after norm_header)
    column_aliases: dict[str, list[str]] = {}
    # normalized headers that, together, identify this bank's layout
    signature_headers: list[str] = []
    # regexes searched in statement text (bank name, IFSC prefix...)
    text_markers: list[str] = []
    fuzzy_columns: bool = False   # allow "contains" header matching (generic fallback only)
    upi_prefer_vpa: bool = False  # narration slot before VPA is a remark, not the payee

    # ---------- detection ----------
    def detect(self, table: StatementTable) -> float:
        """Confidence 0..1 that this adapter matches the statement."""
        headers = set(table.norm_headers)
        sig = [norm_header(h) for h in self.signature_headers]
        header_score = (sum(1 for h in sig if h in headers) / len(sig)) if sig else 0.0
        text_score = 0.0
        if self.text_markers and table.text:
            if any(re.search(m, table.text, re.IGNORECASE) for m in self.text_markers):
                text_score = 1.0
        return round(0.75 * header_score + 0.25 * text_score, 3)

    # ---------- column mapping ----------
    def map_columns(self, headers: list[str]) -> dict[str, int]:
        normed = [norm_header(h) for h in headers]
        mapping: dict[str, int] = {}
        used: set[int] = set()
        for canon in CANONICAL:
            aliases = [norm_header(a) for a in self.column_aliases.get(canon, [])]
            idx = next((i for a in aliases for i, h in enumerate(normed) if h == a and i not in used), None)
            if idx is None and self.fuzzy_columns:
                idx = next(
                    (i for a in aliases for i, h in enumerate(normed) if len(a) >= 4 and a in h and i not in used),
                    None,
                )
            if idx is not None:
                mapping[canon] = idx
                used.add(idx)
        return mapping

    def validate_mapping(self, mapping: dict[str, int]) -> None:
        missing = [c for c in ("date", "description") if c not in mapping]
        has_amounts = ("debit" in mapping or "credit" in mapping) or "amount" in mapping
        if missing or not has_amounts:
            need = missing + ([] if has_amounts else ["debit/credit or amount"])
            raise ParseError(f"Could not find required columns: {', '.join(need)}")

    # ---------- UPI (bank specific narration layouts can override) ----------
    def extract_upi(self, description: str) -> UpiDetails:
        return extract_upi(description, prefer_vpa=self.upi_prefer_vpa)

    # ---------- row parsing ----------
    def amounts_from_row(self, cell, mapping: dict[str, int]) -> tuple[float, float]:
        """Return (debit, credit) as positive numbers."""
        debit = credit = 0.0
        if "debit" in mapping or "credit" in mapping:
            d = parse_amount(cell("debit")) if "debit" in mapping else None
            c = parse_amount(cell("credit")) if "credit" in mapping else None
            debit, credit = abs(d or 0.0), abs(c or 0.0)
            if (d or 0) < 0 and not credit:  # some banks put negative numbers in a single column
                debit, credit = abs(d), 0.0
            if debit or credit or "amount" not in mapping:
                return debit, credit
        amt = parse_amount(cell("amount"))
        if amt is None:
            return 0.0, 0.0
        if "dr_cr" in mapping:
            flag = str(cell("dr_cr") or "").strip().upper()
            if flag.startswith("D"):
                return abs(amt), 0.0
            if flag.startswith("C"):
                return 0.0, abs(amt)
        return (abs(amt), 0.0) if amt < 0 else (0.0, amt)

    def parse(self, table: StatementTable) -> ParseResult:
        mapping = self.map_columns(table.headers)
        self.validate_mapping(mapping)
        txns: list[ParsedTransaction] = []
        skipped = 0
        warnings: list[str] = []

        for row_no, row in enumerate(table.rows, start=1):
            def cell(name: str, _row=row):
                i = mapping.get(name)
                if i is None or i >= len(_row):
                    return None
                v = _row[i]
                return None if v is None else str(v).strip()

            if not any(str(c or "").strip() for c in row):
                continue
            # repeated header rows (multi-page PDFs)
            if [norm_header(c) for c in row[: len(table.headers)]] == table.norm_headers:
                continue

            desc = re.sub(r"\s+", " ", cell("description") or "").strip()
            tdate = parse_date(cell("date"))
            debit, credit = self.amounts_from_row(cell, mapping)

            if tdate is None:
                # wrapped narration line belonging to the previous transaction
                if desc and txns and not debit and not credit:
                    txns[-1].description = f"{txns[-1].description} {desc}".strip()
                    continue
                skipped += 1
                continue
            if _SKIP_DESC.match(desc) or (not debit and not credit):
                skipped += 1
                continue

            raw = {h: (row[i] if i < len(row) else None) for i, h in enumerate(table.headers) if h}
            txns.append(
                ParsedTransaction(
                    transaction_date=tdate,
                    description=desc or "(no description)",
                    debit_amount=round(debit, 2),
                    credit_amount=round(credit, 2),
                    balance=parse_amount(cell("balance")),
                    reference=(cell("reference") or None) if cell("reference") not in ("", "0", "-") else None,
                    value_date=parse_date(cell("value_date")),
                    raw_fields={str(k): (None if v is None else str(v)) for k, v in raw.items()},
                    row_number=row_no,
                )
            )

        if not txns:
            raise ParseError("No transactions could be read from this statement.")
        if skipped:
            warnings.append(f"{skipped} row(s) were skipped (headers, totals, or rows without a valid date/amount).")
        return ParseResult(self.bank_name, self.key, txns, warnings, skipped)
