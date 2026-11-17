"""Regex rule engine.

Resolution order for a transaction:
  1. manual override (set by the user on the transaction) - never touched by the engine
  2. enabled rules, highest priority first (user rules and default rules share one ordering;
     on equal priority, user-created rules win over default rules)
  3. fallback -> "Other", flagged `needs_review`
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass

log = logging.getLogger("spendly.categorization")

MAX_PATTERN_LEN = 300
# crude guard against catastrophic backtracking patterns such as (a+)+ or (\w*)*
_NESTED_QUANT = re.compile(r"\((?:[^()\\]|\\.)*[+*](?:[^()\\]|\\.)*\)\s*[+*{]")


class InvalidRuleError(ValueError):
    pass


def validate_pattern(pattern: str) -> re.Pattern:
    if not pattern or not pattern.strip():
        raise InvalidRuleError("Pattern cannot be empty")
    if len(pattern) > MAX_PATTERN_LEN:
        raise InvalidRuleError(f"Pattern is too long (max {MAX_PATTERN_LEN} characters)")
    if _NESTED_QUANT.search(pattern):
        raise InvalidRuleError("Nested quantifiers like (a+)+ are not allowed")
    try:
        return re.compile(pattern, re.IGNORECASE)
    except re.error as exc:
        raise InvalidRuleError(f"Invalid regular expression: {exc}") from None


@dataclass
class CompiledRule:
    id: str
    name: str
    regex: re.Pattern
    category_id: str
    priority: int
    applies_to: str  # debit | credit | any
    is_default: bool


@dataclass
class CategoryMatch:
    category_id: str | None
    rule_id: str | None
    source: str  # rule | custom_rule | default


class CategorizationEngine:
    def __init__(self, rules: list[dict], fallback_category_id: str | None):
        self.fallback_category_id = fallback_category_id
        compiled: list[CompiledRule] = []
        for r in rules:
            if not r.get("enabled", True):
                continue
            try:
                rx = validate_pattern(r["regex_pattern"])
            except InvalidRuleError:
                log.warning("Skipping invalid rule %s", r.get("_id"))
                continue
            compiled.append(
                CompiledRule(
                    id=str(r["_id"]), name=r.get("rule_name", ""), regex=rx, category_id=str(r["category_id"]),
                    priority=int(r.get("priority", 0)), applies_to=r.get("applies_to", "any"),
                    is_default=bool(r.get("is_default", False)),
                )
            )
        compiled.sort(key=lambda c: (-c.priority, c.is_default))
        self.rules = compiled

    @staticmethod
    def match_text(merchant: str | None, description: str | None) -> str:
        return f"{merchant or ''} | {description or ''}".upper()

    def categorize(self, merchant: str | None, description: str | None, txn_type: str) -> CategoryMatch:
        text = self.match_text(merchant, description)
        for rule in self.rules:
            if rule.applies_to != "any" and rule.applies_to != txn_type:
                continue
            if rule.regex.search(text):
                return CategoryMatch(rule.category_id, rule.id, "rule" if rule.is_default else "custom_rule")
        return CategoryMatch(self.fallback_category_id, None, "default")

    def apply(self, txn: dict) -> dict:
        """Return the categorization fields for a transaction document (respects manual overrides)."""
        if txn.get("manual_override"):
            return {}
        m = self.categorize(txn.get("normalized_merchant"), txn.get("raw_description"), txn.get("transaction_type", "debit"))
        return {
            "category_id": m.category_id,
            "matched_rule_id": m.rule_id,
            "categorization_source": m.source,
            "needs_review": m.source == "default",
        }
