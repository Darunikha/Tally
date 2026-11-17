"""Shared API dependencies: database handle and authenticated user."""
from bson import ObjectId
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.config import get_settings
from app.core.errors import AppError
from app.core.security import decode_access_token
from app.database.mongo import USERS, get_db

bearer = HTTPBearer(auto_error=False)


def db_dep():
    return get_db()


async def current_user(creds: HTTPAuthorizationCredentials | None = Depends(bearer), db=Depends(db_dep)) -> dict:
    if creds is None or creds.scheme.lower() != "bearer":
        raise AppError("Not authenticated", 401, "unauthorized")
    payload = decode_access_token(creds.credentials)
    sub = payload.get("sub") if payload else None
    if not sub or not ObjectId.is_valid(sub):
        raise AppError("Session expired - please sign in again", 401, "unauthorized")
    user = await db[USERS].find_one({"_id": ObjectId(sub)})
    if not user:
        raise AppError("Account not found", 401, "unauthorized")
    # sessions issued before a password change / "sign out everywhere" are no longer valid
    if int(payload.get("tv", 0)) != int(user.get("token_version", 0)):
        raise AppError("Session expired - please sign in again", 401, "unauthorized")
    return user


async def verified_user(user=Depends(current_user)) -> dict:
    """Use on actions that require a confirmed email when REQUIRE_EMAIL_VERIFICATION is on."""
    if get_settings().require_email_verification and not user.get("email_verified"):
        raise AppError("Please verify your email address first - check your inbox for the link.", 403,
                       "email_not_verified")
    return user
