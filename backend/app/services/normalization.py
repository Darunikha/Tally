"""Turn adapter output (ParsedTransaction) into normalized RawTransactions documents."""
from __future__ import annotations

import hashlib
import re
from collections import Counter

from bson import ObjectId

from app.models.documents import transaction_doc
from app.parsers.base import BaseBankParser, ParsedTransaction
from app.utils.payment import detect_payment_method, extract_merchant


def _norm_desc(desc: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", desc.upper())


def base_fingerprint_key(user_id: ObjectId, t: ParsedTransaction) -> str:
    bal = "" if t.balance is None else f"{t.balance:.2f}"
    return "|".join([
        str(user_id), t.transaction_date.strftime("%Y-%m-%d"), f"{t.debit_amount:.2f}", f"{t.credit_amount:.2f}",
        _norm_desc(t.description)[:120], bal,
    ])


def fingerprints(user_id: ObjectId, txns: list[ParsedTransaction]) -> list[str]:
    """Stable per-transaction fingerprints used for duplicate detection across uploads.

    Identical rows inside one statement (e.g. two equal coffees on the same day without a
    running balance) are legitimate, so an occurrence counter keeps them distinct; the same
    statement uploaded twice reproduces the same fingerprints and is detected as duplicate."""
    seen: Counter[str] = Counter()
    out = []
    for t in txns:
        key = base_fingerprint_key(user_id, t)
        seen[key] += 1
        out.append(hashlib.sha256(f"{key}|{seen[key]}".encode()).hexdigest())
    return out


def normalize(
    parsed: list[ParsedTransaction], parser: BaseBankParser, bank_name: str, user_id: ObjectId, upload_id: ObjectId
) -> list[dict]:
    fps = fingerprints(user_id, parsed)
    docs = []
    for t, fp in zip(parsed, fps):
        method = detect_payment_method(t.description)
        upi = parser.extract_upi(t.description) if method == "UPI" else None
        if upi and upi.is_upi:
            merchant = upi.merchant
            reference = t.reference or upi.reference
        else:
            merchant = extract_merchant(t.description, method)
            reference = t.reference
        docs.append(
            transaction_doc(
                user_id=user_id,
                upload_id=upload_id,
                transaction_date=t.transaction_date,
                value_date=t.value_date,
                raw_description=t.description,
                normalized_merchant=merchant or "Unknown",
                upi_id=upi.upi_id if upi else None,
                upi_flow=upi.flow if upi else None,
                transaction_reference=reference,
                debit_amount=t.debit_amount,
                credit_amount=t.credit_amount,
                balance=t.balance,
                payment_method=method,
                bank_name=bank_name,
                raw_bank_fields=t.raw_fields,
                fingerprint=fp,
            )
        )
    return docs
