"""MongoDB document builders - the single place that defines each collection's shape.

Collections: users, statement_uploads, raw_transactions, staged_transactions (preview area),
categories, categorization_rules, spending_summaries, anomaly_reviews.
Every document except `users` carries `user_id` for per-user isolation.
"""
from __future__ import annotations

from datetime import datetime

from bson import ObjectId

from app.utils.dates import utcnow

UPLOAD_STATUSES = ("processing", "pending_review", "completed", "failed", "deleting")


def user_doc(email: str, full_name: str, password_hash: str, legal_version: str | None = None) -> dict:
    now = utcnow()
    return {
        "_id": ObjectId(),
        "email": email.lower(),
        "full_name": full_name,
        "password_hash": password_hash,
        "email_verified": False,
        "email_verified_at": None,
        "token_version": 0,  # bumped to revoke all sessions (password change/reset, sign out everywhere)
        "password_changed_at": now,
        # DPDP Act: record of the consent given at signup (which policy version, when)
        "consent": {"terms_version": legal_version, "privacy_version": legal_version, "accepted_at": now},
        "settings": {"anomaly_sensitivity": "medium", "large_transaction_threshold": None},
        "created_at": now,
    }


def upload_doc(user_id: ObjectId, file_name: str, file_type: str, file_hash: str, file_size: int) -> dict:
    return {
        "_id": ObjectId(),
        "user_id": user_id,
        "file_name": file_name,
        "bank_name": None,
        "file_type": file_type,
        "file_size": file_size,
        "file_hash": file_hash,
        "upload_date": utcnow(),
        "processing_status": "processing",
        "transaction_count": 0,
        "parsed_count": 0,
        "duplicate_count": 0,
        "total_debits": 0.0,
        "total_credits": 0.0,
        "date_range": {"start": None, "end": None},
        "parser_used": None,
        "account_type": "bank",  # "bank" | "credit_card"
        "account_id": None,      # the Account this statement is filed under (None = unassigned)
        "warnings": [],
        "error": None,
        "is_demo": False,
        "file_retained": False,  # uploaded files are processed in memory and never stored
    }


def transaction_doc(
    *,
    user_id: ObjectId,
    upload_id: ObjectId,
    transaction_date: datetime,
    value_date: datetime | None,
    raw_description: str,
    normalized_merchant: str | None,
    upi_id: str | None,
    upi_flow: str | None,
    transaction_reference: str | None,
    debit_amount: float,
    credit_amount: float,
    balance: float | None,
    payment_method: str,
    bank_name: str,
    raw_bank_fields: dict,
    fingerprint: str,
    account_type: str = "bank",
    account_id: ObjectId | None = None,
) -> dict:
    now = utcnow()
    ttype = "credit" if credit_amount > 0 else "debit"
    return {
        "_id": ObjectId(),
        "user_id": user_id,
        "upload_id": upload_id,
        "transaction_date": transaction_date,
        "value_date": value_date,
        "raw_description": raw_description,
        "normalized_merchant": normalized_merchant,
        "upi_id": upi_id,
        "upi_flow": upi_flow,
        "transaction_reference": transaction_reference,
        "debit_amount": round(debit_amount, 2),
        "credit_amount": round(credit_amount, 2),
        "amount": round(credit_amount if ttype == "credit" else debit_amount, 2),
        "balance": balance,
        "transaction_type": ttype,
        "payment_method": payment_method,
        "category_id": None,
        "categorization_source": "default",
        "matched_rule_id": None,
        "manual_override": False,
        "needs_review": True,
        "notes": "",
        "bank_name": bank_name,
        "account_type": account_type,
        "account_id": account_id,
        "raw_bank_fields": raw_bank_fields,
        "fingerprint": fingerprint,
        "created_at": now,
        "updated_at": now,
    }


def category_doc(user_id: ObjectId, name: str, color: str, description: str = "", is_default: bool = False,
                excluded_from_totals: bool = False) -> dict:
    return {
        "_id": ObjectId(),
        "user_id": user_id,
        "name": name,
        "description": description,
        "color": color,
        "is_default": is_default,
        "excluded_from_totals": excluded_from_totals,  # e.g. credit card bill payments: not income or spending
        "created_at": utcnow(),
    }


def rule_doc(
    user_id: ObjectId, rule_name: str, regex_pattern: str, category_id: ObjectId, priority: int,
    applies_to: str = "any", enabled: bool = True, is_default: bool = False,
) -> dict:
    return {
        "_id": ObjectId(),
        "user_id": user_id,
        "rule_name": rule_name,
        "regex_pattern": regex_pattern,
        "category_id": category_id,
        "priority": priority,
        "applies_to": applies_to,
        "enabled": enabled,
        "is_default": is_default,
        "created_at": utcnow(),
    }


def budget_doc(user_id: ObjectId, category_id: ObjectId | None, monthly_limit: float, alert_threshold: int) -> dict:
    now = utcnow()
    return {
        "_id": ObjectId(),
        "user_id": user_id,
        "category_id": category_id,  # None = overall monthly budget
        "monthly_limit": monthly_limit,
        "alert_threshold": alert_threshold,
        "created_at": now,
        "updated_at": now,
    }


ACCOUNT_COLORS = ["#2F7D55", "#2A78D6", "#EB6834", "#6250D6", "#EDA100", "#E87BA4", "#4B7F87", "#8A6D3B"]


def account_doc(user_id: ObjectId, name: str, account_type: str, bank_name: str | None, last4: str | None,
                color: str) -> dict:
    now = utcnow()
    return {
        "_id": ObjectId(),
        "user_id": user_id,
        "name": name,
        "name_key": name.casefold(),  # unique per user, case-insensitively
        "account_type": account_type,  # "bank" | "credit_card"
        "bank_name": bank_name,
        "last4": last4,  # the last 4 digits only, for recognising the account - never a full number
        "color": color,
        "created_at": now,
        "updated_at": now,
    }
