"""Convert Mongo documents to JSON-safe dicts (ObjectId -> str, datetimes -> ISO)."""
from datetime import datetime

from bson import ObjectId

DATE_ONLY_FIELDS = {"transaction_date", "value_date", "start", "end", "period_start", "period_end"}
PRIVATE_FIELDS = {"password_hash", "user_id", "file_hash", "fingerprint"}


def to_json(value, key: str | None = None):
    if isinstance(value, ObjectId):
        return str(value)
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d") if key in DATE_ONLY_FIELDS else value.isoformat() + ("Z" if value.tzinfo is None else "")
    if isinstance(value, dict):
        out = {}
        for k, v in value.items():
            if k in PRIVATE_FIELDS:
                continue
            out["id" if k == "_id" else k] = to_json(v, k)
        return out
    if isinstance(value, (list, tuple, set)):
        return [to_json(v, key) for v in value]
    return value
