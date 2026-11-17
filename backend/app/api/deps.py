"""Shared API dependencies: database handle and authenticated user."""
from bson import ObjectId
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.errors import AppError
from app.core.security import decode_access_token
from app.database.mongo import USERS, get_db

bearer = HTTPBearer(auto_error=False)


def db_dep():
    return get_db()


async def current_user(creds: HTTPAuthorizationCredentials | None = Depends(bearer), db=Depends(db_dep)) -> dict:
    if creds is None or creds.scheme.lower() != "bearer":
        raise AppError("Not authenticated", 401, "unauthorized")
    sub = decode_access_token(creds.credentials)
    if not sub or not ObjectId.is_valid(sub):
        raise AppError("Session expired - please sign in again", 401, "unauthorized")
    user = await db[USERS].find_one({"_id": ObjectId(sub)})
    if not user:
        raise AppError("Account not found", 401, "unauthorized")
    return user
