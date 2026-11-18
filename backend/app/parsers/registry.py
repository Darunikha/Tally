"""Bank identification and parser dispatch."""
from __future__ import annotations

import logging
import re

from app.parsers.adapters.banks import BANK_PARSERS, GENERIC_PARSER
from app.parsers.adapters.cards import CARD_PARSERS, CARD_STATEMENT_WORDS, GENERIC_CARD_PARSER
from app.parsers.base import BaseBankParser, ParseError, ParseResult, StatementTable
from app.parsers.excel import read_excel
from app.parsers.readers import read_csv, read_pdf

log = logging.getLogger("tally.parsers")

DETECTION_THRESHOLD = 0.6


def all_parsers() -> list[BaseBankParser]:
    return [*BANK_PARSERS, *CARD_PARSERS, GENERIC_PARSER, GENERIC_CARD_PARSER]


def get_parser(key: str) -> BaseBankParser | None:
    return next((p for p in all_parsers() if p.key == key), None)


def identify_bank(table: StatementTable) -> tuple[BaseBankParser, float]:
    scored = sorted(((p.detect(table), p) for p in [*BANK_PARSERS, *CARD_PARSERS]), key=lambda x: x[0], reverse=True)
    best_score, best = scored[0]
    if best_score >= DETECTION_THRESHOLD:
        return best, best_score
    if CARD_STATEMENT_WORDS.search(table.text or ""):
        return GENERIC_CARD_PARSER, 0.0  # reads like a card statement from an issuer we have no adapter for
    return GENERIC_PARSER, 0.0


def read_table(content: bytes, file_type: str, password: str | None = None) -> StatementTable:
    if file_type == "csv":
        return read_csv(content)
    if file_type == "pdf":
        return read_pdf(content, password)
    if file_type in ("xls", "xlsx"):
        return read_excel(content)
    raise ParseError(f"Unsupported file type: {file_type}")


def parse_statement(content: bytes, file_type: str, bank_hint: str | None = None,
                    password: str | None = None) -> tuple[ParseResult, BaseBankParser]:
    """Read the file, pick an adapter (or use `bank_hint`), and parse. Falls back to the generic
    adapter if the bank-specific adapter fails on a slightly different layout.
    `password` unlocks encrypted PDFs; it is used in memory only."""
    table = read_table(content, file_type, password)
    parser = get_parser(bank_hint) if bank_hint else None
    if parser is None:
        parser, score = identify_bank(table)
        log.info("Bank identified as %s (score %.2f, source %s)", parser.key, score, table.source)
    generic = GENERIC_CARD_PARSER if parser.account_type == "credit_card" else GENERIC_PARSER
    try:
        result = parser.parse(table)
    except ParseError:
        if parser is generic:
            raise
        log.info("Adapter %s failed; retrying with generic parser", parser.key)
        result = generic.parse(table)
        result.bank_name = parser.bank_name  # bank still identified, layout differed
        result.warnings.append("Bank layout differed from the known format; parsed with the generic adapter.")
        result.parser_used = f"{result.parser_used}:{table.source}"
        return result, generic
    if parser is GENERIC_PARSER and table.source.startswith("pdf"):
        # PDF text often names the bank even when we parsed generically
        # title lines only (stop at the first dated transaction line) so counterparty banks / VPAs
        # in narrations (e.g. "zomato@hdfcbank") are not mistaken for the statement's bank
        title_lines = []
        for line in table.text.splitlines()[:8]:
            if re.match(r"\s*\d{1,4}[/\-. ]", line):
                break
            title_lines.append(line)
        header_text = "\n".join(title_lines)
        for p in BANK_PARSERS:
            if p.detect(StatementTable(headers=[], rows=[], text=header_text)) > 0:
                result.bank_name = p.bank_name
                break
    result.parser_used = f"{result.parser_used}:{table.source}"
    return result, parser
