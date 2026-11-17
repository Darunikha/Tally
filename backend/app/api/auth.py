"""Authentication: register/login, email verification, password reset, session revocation.

Rate limits (per window):
  login            20 / 15 min per IP, 8 / 15 min per email  (slows password guessing)
  register         5 / hour per IP
  forgot-password  10 / hour per IP, 3 / hour per email
  reset / verify   20 / hour per IP
  resend verify    3 / hour per user
"""
from datetime import timedelta
from urllib.parse import quote

from fastapi import APIRouter, BackgroundTasks, Depends, Request
from pymongo.errors import DuplicateKeyError

from app.api.deps import current_user, db_dep
from app.core.config import get_settings
from app.core.errors import AppError
from app.core.ratelimit import client_ip, limit
from app.core.security import hash_password, session_token, verify_password
from app.database.mongo import USERS
from app.models.documents import user_doc
from app.schemas.requests import (ForgotPasswordRequest, LoginRequest, RegisterRequest, ResetPasswordRequest,
                                  VerifyEmailRequest)
from app.services.categories import seed_user_defaults
from app.services.email import password_changed_email, password_reset_email, send_email, verification_email
from app.services.tokens import consume_token, issue_token, revoke_tokens
from app.utils.dates import utcnow
from app.utils.serialize import to_json

router = APIRouter(prefix="/auth", tags=["auth"])

# Constant dummy hash so login timing does not reveal whether an email exists.
_DUMMY_HASH = hash_password("timing-equaliser-0")
FORGOT_MESSAGE = "If an account exists for that email, we've sent a link to reset the password. It expires soon, so use it shortly."


def _session(user: dict) -> dict:
    return {"access_token": session_token(user), "token_type": "bearer", "user": to_json(user)}


def _link(path: str, token: str) -> str:
    return f"{get_settings().frontend_url.rstrip('/')}{path}?token={quote(token)}"


async def _send_verification(db, user: dict, background: BackgroundTasks) -> None:
    s = get_settings()
    token = await issue_token(db, user["_id"], "email_verify", timedelta(hours=s.email_verify_hours))
    background.add_task(send_email, verification_email(user["email"], user["full_name"],
                                                       _link("/verify-email", token), s.email_verify_hours))


@router.post("/register", status_code=201)
async def register(body: RegisterRequest, request: Request, background: BackgroundTasks, db=Depends(db_dep)):
    await limit(db, "register:ip", client_ip(request), 5, 3600)
    doc = user_doc(body.email, body.full_name.strip(), hash_password(body.password), get_settings().legal_version)
    try:
        await db[USERS].insert_one(doc)
    except DuplicateKeyError:
        raise AppError("An account with this email already exists", 409, "email_taken") from None
    await seed_user_defaults(db, doc["_id"])
    await _send_verification(db, doc, background)
    return _session(doc)


@router.post("/login")
async def login(body: LoginRequest, request: Request, db=Depends(db_dep)):
    await limit(db, "login:ip", client_ip(request), 20, 900)
    await limit(db, "login:email", body.email, 8, 900)
    user = await db[USERS].find_one({"email": body.email.lower()})
    ok = verify_password(body.password, user["password_hash"] if user else _DUMMY_HASH)
    if not user or not ok:
        raise AppError("Incorrect email or password", 401, "invalid_credentials")
    await db[USERS].update_one({"_id": user["_id"]}, {"$set": {"last_login_at": utcnow()}})
    return _session(user)


@router.get("/me")
async def me(user=Depends(current_user)):
    return to_json(user)


# ---------------------------------------------------------------- password reset
@router.post("/forgot-password")
async def forgot_password(body: ForgotPasswordRequest, request: Request, background: BackgroundTasks,
                          db=Depends(db_dep)):
    """Always returns the same response, whether or not the email is registered."""
    await limit(db, "forgot:ip", client_ip(request), 10, 3600)
    await limit(db, "forgot:email", body.email, 3, 3600)
    user = await db[USERS].find_one({"email": body.email.lower()})
    if user:
        s = get_settings()
        token = await issue_token(db, user["_id"], "password_reset", timedelta(minutes=s.password_reset_minutes))
        background.add_task(send_email, password_reset_email(user["email"], user["full_name"],
                                                             _link("/reset-password", token), s.password_reset_minutes))
    return {"ok": True, "message": FORGOT_MESSAGE}


@router.post("/reset-password")
async def reset_password(body: ResetPasswordRequest, request: Request, background: BackgroundTasks,
                         db=Depends(db_dep)):
    await limit(db, "reset:ip", client_ip(request), 20, 3600)
    user_id = await consume_token(db, body.token, "password_reset")
    user = await db[USERS].find_one({"_id": user_id})
    if not user:
        raise AppError("This link is invalid or has expired. Please request a new one.", 400, "invalid_token")
    await db[USERS].update_one({"_id": user_id}, {
        "$set": {"password_hash": hash_password(body.new_password), "password_changed_at": utcnow(),
                 # the reset link was delivered to this inbox, which proves ownership of the address
                 "email_verified": True, "email_verified_at": user.get("email_verified_at") or utcnow()},
        "$inc": {"token_version": 1},  # signs out every existing session
    })
    await revoke_tokens(db, user_id, "password_reset")
    background.add_task(send_email, password_changed_email(
        user["email"], user["full_name"], f"{get_settings().frontend_url.rstrip('/')}/forgot-password"))
    return {"ok": True, "message": "Your password has been reset. Please sign in with your new password."}


# ---------------------------------------------------------------- email verification
@router.post("/verify-email")
async def verify_email(body: VerifyEmailRequest, request: Request, db=Depends(db_dep)):
    await limit(db, "verify:ip", client_ip(request), 20, 3600)
    user_id = await consume_token(db, body.token, "email_verify")
    await db[USERS].update_one({"_id": user_id}, {"$set": {"email_verified": True, "email_verified_at": utcnow()}})
    return {"ok": True, "message": "Your email address is verified."}


@router.post("/resend-verification")
async def resend_verification(background: BackgroundTasks, user=Depends(current_user), db=Depends(db_dep)):
    if user.get("email_verified"):
        return {"ok": True, "message": "Your email is already verified."}
    await limit(db, "resend-verify:user", str(user["_id"]), 3, 3600)
    await _send_verification(db, user, background)
    return {"ok": True, "message": f"We've sent a new verification link to {user['email']}."}


# ---------------------------------------------------------------- sessions
@router.post("/logout-all")
async def logout_all(user=Depends(current_user), db=Depends(db_dep)):
    """Revoke every session, including this one."""
    await db[USERS].update_one({"_id": user["_id"]}, {"$inc": {"token_version": 1}})
    return {"ok": True}
