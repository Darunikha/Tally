"""Credit card statement adapters.

A card statement differs from a bank statement in three ways that matter for the numbers:
  * a purchase is a plain positive amount (a *debit*), while a payment or refund is marked "Cr",
    "C", a "CR" flag column or a minus sign (a *credit*) - the opposite of a signed bank amount;
  * there is no running balance;
  * the payment you make towards the card shows up as a credit, which is not income.
"""
from __future__ import annotations

import re

from app.parsers.base import BaseBankParser, StatementTable, norm_header
from app.utils.money import parse_amount

_SUFFIX = re.compile(r"(?<=[\d)])\s*(cr|dr|c|d)\.?\s*$", re.IGNORECASE)  # "5,000.00 Cr" and "5,000.00CR"
# phrases that only appear on a card statement's summary, never in a bank statement's narrations
CARD_STATEMENT_WORDS = re.compile(
    r"total\s*amount\s*due|minimum\s*(?:amount\s*)?due|payment\s*due\s*date|credit\s*limit|available\s*credit|"
    r"credit\s*card\s*statement|card\s*statement", re.IGNORECASE)


def split_card_amount(raw) -> tuple[float, bool] | None:
    """('1,299.00') -> (1299.0, False purchase); ('5,000.00 Cr') / ('-5,000.00') -> (5000.0, True credit)."""
    if raw is None:
        return None
    s = str(raw).strip()
    credit = False
    m = _SUFFIX.search(s)
    if m:
        credit = m.group(1).lower() in ("cr", "c")
        s = s[: m.start()]
    value = parse_amount(s)
    if value is None:
        return None
    if value < 0:
        credit = True  # a minus sign marks a payment or refund
    return abs(value), credit


class CreditCardParser(BaseBankParser):
    """Base for card issuers: one Amount column, purchases are debits, 'Cr' marks credits."""

    account_type = "credit_card"
    column_aliases = {
        "date": ["Date", "Transaction Date", "Txn Date", "Posting Date"],
        "description": ["Transaction Details", "Transaction Description", "Description", "Details", "Merchant Name"],
        "amount": ["Amount (in Rs.)", "Amount (in Rs)", "Amount (Rs.)", "Amount (INR)", "Amount ( ₹ )", "Amount", "Amt"],
        "dr_cr": ["BillingAmountSign", "Billing Amount Sign", "Dr / Cr", "Dr/Cr", "Debit / Credit", "Transaction Type"],
    }
    # distinctive headers that identify the issuer even when the file carries no issuer name
    distinctive_headers: list[str] = []
    fuzzy_columns = True

    @staticmethod
    def card_shaped(headers: list[str]) -> bool:
        """Date + description + an amount column and no running balance (cards have none)."""
        def starts(*prefixes: str) -> bool:
            return any(h.startswith(p) for h in headers for p in prefixes)

        return (starts("date", "txndate") and starts("transactiondetails", "transactiondescription", "description", "details", "merchant")
                and starts("amount", "amt") and not starts("balance", "withdrawal", "deposit") and "bal" not in headers)

    def detect(self, table: StatementTable) -> float:
        headers = table.norm_headers
        if not self.card_shaped(headers):
            return 0.0  # generic "Date / Details / Amount" headers alone must not claim a bank statement
        issuer_text = any(re.search(m, table.text or "", re.IGNORECASE) for m in self.text_markers)
        distinctive = bool(self.distinctive_headers) and all(norm_header(h) in headers for h in self.distinctive_headers)
        return 0.95 if issuer_text else 0.8 if distinctive else 0.0

    def amounts_from_row(self, cell, mapping: dict[str, int]) -> tuple[float, float]:
        if "debit" in mapping or "credit" in mapping:
            return super().amounts_from_row(cell, mapping)  # some issuers do split the columns
        parsed = split_card_amount(cell("amount"))
        if parsed is None:
            return 0.0, 0.0
        amount, credit = parsed
        flag = str(cell("dr_cr") or "").strip().upper() if "dr_cr" in mapping else ""
        if flag.startswith("C"):
            credit = True
        elif flag.startswith("D"):
            credit = False
        return (0.0, amount) if credit else (amount, 0.0)


class HDFCCardParser(CreditCardParser):
    key = "hdfc_card"
    bank_name = "HDFC Bank Credit Card"
    text_markers = [r"HDFC\s*BANK[\w\s]{0,20}CREDIT\s*CARD", r"HDFC\s*BANK\s*CARDS?"]


class ICICICardParser(CreditCardParser):
    key = "icici_card"
    bank_name = "ICICI Bank Credit Card"
    distinctive_headers = ["SerNo.", "BillingAmountSign"]
    text_markers = [r"ICICI\s*BANK[\w\s]{0,20}CREDIT\s*CARD"]


class SBICardParser(CreditCardParser):
    key = "sbi_card"
    bank_name = "SBI Card"
    text_markers = [r"SBI\s*CARD", r"SBI\s*CARDS?\s*AND\s*PAYMENT"]


class AxisCardParser(CreditCardParser):
    key = "axis_card"
    bank_name = "Axis Bank Credit Card"
    distinctive_headers = ["Merchant Category"]
    text_markers = [r"AXIS\s*BANK[\w\s]{0,20}CREDIT\s*CARD"]


class GenericCardParser(CreditCardParser):
    """Any other card issuer. Chosen from the format list, or automatically when the statement text
    reads like a card statement (credit limit, total amount due, ...)."""

    key = "generic_card"
    bank_name = "Credit Card"

    def detect(self, table: StatementTable) -> float:
        return 0.0  # never auto-selected by header; the registry falls back to it for card-like text


CARD_PARSERS: list[BaseBankParser] = [HDFCCardParser(), ICICICardParser(), SBICardParser(), AxisCardParser()]
GENERIC_CARD_PARSER = GenericCardParser()
