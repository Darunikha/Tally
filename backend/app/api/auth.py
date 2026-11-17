from fastapi import APIRouter, Depends
from pymongo.errors import DuplicateKeyError

from app.api.deps import current_user, db_dep
from app.core.errors import AppError
from app.core.security import create_access_token, hash_password, verify_password
from app.database.mongo import USERS
from app.models.documents import user_doc
from app.schemas.requests import LoginRequest, RegisterRequest
from app.services.categories import seed_user_defaults
from app.utils.serialize import to_json

router = APIRouter(prefix="/auth", tags=["auth"])

# Constant dummy hash so login timing does not reveal whether an email exists.
_DUMMY_HASH = hash_password("timing-equaliser-0")


def _session(user: dict) -> dict:
    return {"access_token": create_access_token(str(user["_id"])), "token_type": "bearer", "user": to_json(user)}


@router.post("/register", status_code=201)
async def register(body: RegisterRequest, db=Depends(db_dep)):
    doc = user_doc(body.email, body.full_name.strip(), hash_password(body.password))
    try:
        await db[USERS].insert_one(doc)
    except DuplicateKeyError:
        raise AppError("An account with this email already exists", 409, "email_taken") from None
    await seed_user_defaults(db, doc["_id"])
    return _session(doc)


@router.post("/login")
async def login(body: LoginRequest, db=Depends(db_dep)):
    user = await db[USERS].find_one({"email": body.email.lower()})
    ok = verify_password(body.password, user["password_hash"] if user else _DUMMY_HASH)
    if not user or not ok:
        raise AppError("Incorrect email or password", 401, "invalid_credentials")
    return _session(user)


@router.get("/me")
async def me(user=Depends(current_user)):
    return to_json(user)
