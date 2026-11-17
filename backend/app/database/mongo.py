"""Motor client lifecycle, collection names and index creation."""
import logging

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from pymongo import ASCENDING, DESCENDING

from app.core.config import get_settings

log = logging.getLogger("tally.db")

USERS = "users"
STATEMENT_UPLOADS = "statement_uploads"
RAW_TRANSACTIONS = "raw_transactions"
STAGED_TRANSACTIONS = "staged_transactions"
CATEGORIES = "categories"
CATEGORIZATION_RULES = "categorization_rules"
SPENDING_SUMMARIES = "spending_summaries"
ANOMALY_REVIEWS = "anomaly_reviews"
RATE_LIMITS = "rate_limits"
AUTH_TOKENS = "auth_tokens"  # password reset / email verification (hashed)

_client = None
_db: AsyncIOMotorDatabase | None = None


def _make_client(url: str):
    if url.startswith("mongomock://"):
        # In-memory database for tests / demo without a MongoDB server. Data is lost on restart.
        from mongomock_motor import AsyncMongoMockClient

        log.warning("Using in-memory mongomock database - data will NOT persist")
        return AsyncMongoMockClient(tz_aware=False)
    return AsyncIOMotorClient(url, uuidRepresentation="standard", serverSelectionTimeoutMS=5000)


async def connect() -> AsyncIOMotorDatabase:
    global _client, _db
    s = get_settings()
    _client = _make_client(s.mongodb_url)
    _db = _client[s.mongodb_db]
    await ensure_indexes(_db)
    log.info("Connected to MongoDB database '%s'", s.mongodb_db)
    return _db


async def disconnect() -> None:
    global _client, _db
    if _client is not None and hasattr(_client, "close"):
        _client.close()
    _client = None
    _db = None


def get_db() -> AsyncIOMotorDatabase:
    if _db is None:
        raise RuntimeError("Database not connected")
    return _db


def set_db(db) -> None:
    """Used by tests to inject a database."""
    global _db
    _db = db


async def ensure_indexes(db) -> None:
    await db[USERS].create_index("email", unique=True)

    up = db[STATEMENT_UPLOADS]
    await up.create_index([("user_id", ASCENDING), ("upload_date", DESCENDING)])
    await up.create_index([("user_id", ASCENDING), ("file_hash", ASCENDING)])

    tx = db[RAW_TRANSACTIONS]
    await tx.create_index([("user_id", ASCENDING), ("transaction_date", DESCENDING)])
    await tx.create_index([("user_id", ASCENDING), ("upload_id", ASCENDING)])
    await tx.create_index([("user_id", ASCENDING), ("normalized_merchant", ASCENDING)])
    await tx.create_index([("user_id", ASCENDING), ("category_id", ASCENDING)])
    await tx.create_index([("user_id", ASCENDING), ("transaction_reference", ASCENDING)])
    await tx.create_index([("user_id", ASCENDING), ("fingerprint", ASCENDING)], unique=True)

    await db[STAGED_TRANSACTIONS].create_index([("user_id", ASCENDING), ("upload_id", ASCENDING)])
    await db[CATEGORIES].create_index([("user_id", ASCENDING), ("name", ASCENDING)], unique=True)
    await db[CATEGORIZATION_RULES].create_index([("user_id", ASCENDING), ("priority", DESCENDING)])
    await db[SPENDING_SUMMARIES].create_index(
        [("user_id", ASCENDING), ("period", ASCENDING), ("period_start", ASCENDING)], unique=True
    )
    await db[ANOMALY_REVIEWS].create_index([("user_id", ASCENDING), ("anomaly_key", ASCENDING)], unique=True)
    # TTL indexes: MongoDB deletes these documents automatically once expires_at passes
    await db[RATE_LIMITS].create_index("expires_at", expireAfterSeconds=0)
    await db[AUTH_TOKENS].create_index("expires_at", expireAfterSeconds=0)
    await db[AUTH_TOKENS].create_index("token_hash", unique=True)
    await db[AUTH_TOKENS].create_index([("user_id", ASCENDING), ("purpose", ASCENDING)])
