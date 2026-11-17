"""Password hashing (bcrypt) and JWT access tokens."""
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt

from app.core.config import get_settings


def hash_password(password: str) -> str:
    # bcrypt only uses the first 72 bytes; we validate length at the schema level.
    return bcrypt.hashpw(password.encode("utf-8")[:72], bcrypt.gensalt(rounds=12)).decode("utf-8")


def verify_password(password: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8")[:72], hashed.encode("utf-8"))
    except ValueError:
        return False


def create_access_token(user_id: str, token_version: int = 0) -> str:
    """`tv` (token version) lets the server revoke every session for a user by bumping the
    user's token_version - used on password reset/change and "sign out everywhere"."""
    s = get_settings()
    now = datetime.now(timezone.utc)
    payload = {"sub": user_id, "tv": token_version, "iat": now, "exp": now + timedelta(minutes=s.jwt_expire_minutes)}
    return jwt.encode(payload, s.jwt_secret, algorithm=s.jwt_algorithm)


def decode_access_token(token: str) -> dict | None:
    s = get_settings()
    try:
        return jwt.decode(token, s.jwt_secret, algorithms=[s.jwt_algorithm], options={"require": ["sub", "exp"]})
    except jwt.PyJWTError:
        return None


def session_token(user: dict) -> str:
    return create_access_token(str(user["_id"]), int(user.get("token_version", 0)))
