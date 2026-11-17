"""Single-use, expiring tokens for password reset and email verification.

Only a SHA-256 hash of each token is stored, so a database leak cannot be used to reset passwords.
Issuing a new token for the same purpose invalidates earlier ones; consuming is atomic (one use).
"""
from __future__ import annotations

import hashlib
import secrets
from datetime import timedelta

from bson import ObjectId
from pymongo import ReturnDocument

from app.core.errors import AppError
from app.database.mongo import AUTH_TOKENS
from app.utils.dates import utcnow

PURPOSES = ("password_reset", "email_verify")


def _hash(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


async def issue_token(db, user_id: ObjectId, purpose: str, ttl: timedelta) -> str:
    assert purpose in PURPOSES
    await db[AUTH_TOKENS].delete_many({"user_id": user_id, "purpose": purpose})
    raw = secrets.token_urlsafe(32)
    now = utcnow()
    await db[AUTH_TOKENS].insert_one({
        "_id": ObjectId(), "user_id": user_id, "purpose": purpose, "token_hash": _hash(raw),
        "created_at": now, "expires_at": now + ttl, "used_at": None,
    })
    return raw


async def consume_token(db, raw: str, purpose: str) -> ObjectId:
    """Mark the token used and return its user id; raise a uniform error if invalid/expired/used."""
    invalid = AppError(
        "This link is invalid or has expired. Please request a new one.", 400, "invalid_token"
    )
    if not raw or len(raw) > 200:
        raise invalid
    doc = await db[AUTH_TOKENS].find_one_and_update(
        {"token_hash": _hash(raw), "purpose": purpose, "used_at": None, "expires_at": {"$gt": utcnow()}},
        {"$set": {"used_at": utcnow()}},
        return_document=ReturnDocument.AFTER,
    )
    if not doc:
        raise invalid
    return doc["user_id"]


async def revoke_tokens(db, user_id: ObjectId, purpose: str | None = None) -> None:
    q = {"user_id": user_id}
    if purpose:
        q["purpose"] = purpose
    await db[AUTH_TOKENS].delete_many(q)
