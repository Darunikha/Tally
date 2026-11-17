"""Fixed-window rate limiting backed by MongoDB (shared by every server instance).

Each limit is a counter document {_id: "<hashed key>:<window>:<bucket>", count, expires_at}; a TTL
index removes old windows. Keys are SHA-256 hashed so emails / IPs are never stored in clear.
"""
from __future__ import annotations

import hashlib
import time
from datetime import datetime

from fastapi import Request
from pymongo import ReturnDocument

from app.core.config import get_settings
from app.core.errors import AppError
from app.database.mongo import RATE_LIMITS


def client_ip(request: Request) -> str:
    if get_settings().trust_proxy_headers:
        fwd = request.headers.get("x-forwarded-for", "")
        # the proxy appends the address it saw; the right-most entry is the one it vouches for
        parts = [p.strip() for p in fwd.split(",") if p.strip()]
        if parts:
            return parts[-1]
        real = request.headers.get("x-real-ip")
        if real:
            return real.strip()
    return request.client.host if request.client else "unknown"


def _human(seconds: int) -> str:
    if seconds < 90:
        return f"{seconds} seconds"
    minutes = round(seconds / 60)
    return f"{minutes} minute{'s' if minutes != 1 else ''}"


async def limit(db, scope: str, identity: str, max_hits: int, window_seconds: int) -> None:
    """Count one hit for (scope, identity); raise 429 once more than `max_hits` occur in the window."""
    if not get_settings().rate_limit_enabled:
        return
    now = time.time()
    bucket = int(now // window_seconds)
    key = hashlib.sha256(f"{scope}|{identity.lower()}".encode()).hexdigest()[:32]
    window_end = (bucket + 1) * window_seconds
    doc = await db[RATE_LIMITS].find_one_and_update(
        {"_id": f"{key}:{window_seconds}:{bucket}"},
        {"$inc": {"count": 1}, "$setOnInsert": {"expires_at": datetime.utcfromtimestamp(window_end)}},
        upsert=True,
        return_document=ReturnDocument.AFTER,
    )
    if doc["count"] > max_hits:
        retry = max(1, int(window_end - now))
        raise AppError(f"Too many attempts. Please try again in {_human(retry)}.", 429, "rate_limited",
                       headers={"Retry-After": str(retry)})
