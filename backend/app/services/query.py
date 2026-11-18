"""Shared filter construction + data loading for transactions (always scoped to one user)."""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timedelta

from bson import ObjectId
from bson.errors import InvalidId

from app.core.errors import AppError
from app.database.mongo import CATEGORIES, RAW_TRANSACTIONS, STATEMENT_UPLOADS
from app.utils.dates import add_months, month_end, to_day


def oid(value: str | ObjectId | None, what: str = "id") -> ObjectId:
    if isinstance(value, ObjectId):
        return value
    try:
        return ObjectId(str(value))
    except (InvalidId, TypeError):
        raise AppError(f"Invalid {what}", 400, "invalid_id") from None


@dataclass
class Period:
    start: datetime | None
    end: datetime | None  # inclusive day

    @property
    def days(self) -> int:
        return (self.end - self.start).days + 1 if self.start and self.end else 0

    def previous(self) -> "Period":
        """Equivalent preceding period (previous calendar month(s) when aligned to months)."""
        if not (self.start and self.end):
            return Period(None, None)
        if self.start.day == 1 and (self.end + timedelta(days=1)).day == 1:
            months = (self.end.year - self.start.year) * 12 + self.end.month - self.start.month + 1
            ps = add_months(self.start, -months)
            return Period(ps, self.start - timedelta(days=1))
        return Period(self.start - timedelta(days=self.days), self.start - timedelta(days=1))


def resolve_period(start: str | None = None, end: str | None = None, month: int | None = None,
                   year: int | None = None) -> Period:
    if start or end:
        try:
            s = to_day(start) if start else None
            e = to_day(end) if end else None
        except ValueError:
            raise AppError("Dates must be YYYY-MM-DD", 400, "invalid_date") from None
        if s and e and s > e:
            raise AppError("Start date must be before end date", 400, "invalid_date")
        return Period(s, e)
    if year and month:
        if not 1 <= month <= 12:
            raise AppError("Invalid month", 400, "invalid_date")
        s = datetime(year, month, 1)
        return Period(s, month_end(s))
    if year:
        return Period(datetime(year, 1, 1), datetime(year, 12, 31))
    return Period(None, None)


def build_filter(user_id: ObjectId, period: Period | None = None, upload_id: str | None = None,
                 category_id: str | None = None, transaction_type: str | None = None,
                 payment_method: str | None = None, search: str | None = None, needs_review: bool | None = None,
                 min_amount: float | None = None, max_amount: float | None = None,
                 merchant: str | None = None, exclude_category_ids: list[ObjectId] | None = None,
                 account_id: str | None = None) -> dict:
    q: dict = {"user_id": user_id}
    if period and (period.start or period.end):
        q["transaction_date"] = {}
        if period.start:
            q["transaction_date"]["$gte"] = period.start
        if period.end:
            q["transaction_date"]["$lte"] = period.end
    if upload_id:
        q["upload_id"] = oid(upload_id, "statement id")
    if account_id:  # "none" = statements not filed under any account (a missing field matches None)
        q["account_id"] = None if account_id == "none" else oid(account_id, "account id")
    if category_id:
        q["category_id"] = oid(category_id, "category id")
    if exclude_category_ids and "category_id" not in q:
        q["category_id"] = {"$nin": exclude_category_ids}
    if transaction_type in ("debit", "credit"):
        q["transaction_type"] = transaction_type
    if payment_method:
        q["payment_method"] = payment_method
    if needs_review is not None:
        q["needs_review"] = needs_review
    if merchant:
        q["normalized_merchant"] = merchant
    if min_amount is not None or max_amount is not None:
        q["amount"] = {}
        if min_amount is not None:
            q["amount"]["$gte"] = float(min_amount)
        if max_amount is not None:
            q["amount"]["$lte"] = float(max_amount)
    if search:
        s = search.strip()[:100]
        if s:
            rx = {"$regex": re.escape(s), "$options": "i"}  # escaped: user text is never a raw regex
            q["$or"] = [{"raw_description": rx}, {"normalized_merchant": rx}, {"upi_id": rx}, {"notes": rx},
                        {"transaction_reference": rx}]
    return q


async def excluded_category_ids(db, user_id: ObjectId) -> list[ObjectId]:
    """Categories left out of income and spending totals (credit card bill payments).

    Only once the user has imported a credit card statement: the card's own purchases are then counted, so
    the bill paid from the bank (and the payment received on the card) would be counted a second time. Until
    then a card bill paid from the bank is real spending and stays in the totals."""
    has_card = await db[STATEMENT_UPLOADS].find_one(
        {"user_id": user_id, "account_type": "credit_card", "processing_status": "completed"}, {"_id": 1})
    if not has_card:
        return []
    return [c["_id"] async for c in db[CATEGORIES].find({"user_id": user_id, "excluded_from_totals": True}, {"_id": 1})]


ANALYTIC_FIELDS = {
    "transaction_date": 1, "debit_amount": 1, "credit_amount": 1, "transaction_type": 1, "category_id": 1,
    "normalized_merchant": 1, "payment_method": 1, "upi_id": 1, "upi_flow": 1, "needs_review": 1,
    "raw_description": 1, "upload_id": 1, "bank_name": 1, "transaction_reference": 1,
}


async def load_transactions(db, query: dict, projection: dict | None = None) -> list[dict]:
    return await db[RAW_TRANSACTIONS].find(query, projection or ANALYTIC_FIELDS).sort("transaction_date", 1).to_list(None)


async def category_map(db, user_id: ObjectId) -> dict[str, dict]:
    return {str(c["_id"]): c async for c in db[CATEGORIES].find({"user_id": user_id})}
