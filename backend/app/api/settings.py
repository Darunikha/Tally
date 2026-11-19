import json
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends
from fastapi.responses import Response

from app.api.deps import current_user, db_dep, verified_user
from app.core.config import get_settings
from app.core.errors import AppError
from app.core.ratelimit import limit
from app.core.security import hash_password, session_token, verify_password
from app.database.mongo import (ACCOUNTS, ANOMALY_REVIEWS, AUTH_TOKENS, BUDGETS, CATEGORIES, LEARNING_DISMISSED, CATEGORIZATION_RULES, RAW_TRANSACTIONS,
                                RECURRING_IGNORED, SPENDING_SUMMARIES, STAGED_TRANSACTIONS, STATEMENT_UPLOADS, USERS)
from app.schemas.requests import PasswordChange, ProfileUpdate
from app.services.email import password_changed_email, send_email
from app.services.statements import confirm_import, create_preview, delete_statement
from app.utils.dates import utcnow
from app.utils.serialize import to_json

router = APIRouter(prefix="/settings", tags=["settings"])

SAMPLE_DIR = Path(__file__).resolve().parents[2] / "sample_data"
DEMO_FILES = ["hdfc_statement.csv"]  # one synthetic account, Aug-Oct 2025


@router.patch("/profile")
async def update_profile(body: ProfileUpdate, user=Depends(current_user), db=Depends(db_dep)):
    update = {}
    if body.full_name is not None:
        update["full_name"] = body.full_name.strip()
    if body.anomaly_sensitivity is not None:
        update["settings.anomaly_sensitivity"] = body.anomaly_sensitivity
    if body.clear_large_threshold:
        update["settings.large_transaction_threshold"] = None
    elif body.large_transaction_threshold is not None:
        update["settings.large_transaction_threshold"] = body.large_transaction_threshold
    if update:
        await db[USERS].update_one({"_id": user["_id"]}, {"$set": update})
    return to_json(await db[USERS].find_one({"_id": user["_id"]}))


@router.post("/password")
async def change_password(body: PasswordChange, background: BackgroundTasks, user=Depends(current_user),
                          db=Depends(db_dep)):
    """Changes the password and signs out every OTHER session; returns a fresh token for this one."""
    await limit(db, "change-password:user", str(user["_id"]), 10, 3600)
    if not verify_password(body.current_password, user["password_hash"]):
        raise AppError("Current password is incorrect", 400, "invalid_password")
    await db[USERS].update_one({"_id": user["_id"]}, {
        "$set": {"password_hash": hash_password(body.new_password), "password_changed_at": utcnow()},
        "$inc": {"token_version": 1},
    })
    await db[AUTH_TOKENS].delete_many({"user_id": user["_id"], "purpose": "password_reset"})
    fresh = await db[USERS].find_one({"_id": user["_id"]})
    background.add_task(send_email, password_changed_email(
        user["email"], user["full_name"], f"{get_settings().frontend_url.rstrip('/')}/forgot-password"))
    return {"ok": True, "access_token": session_token(fresh)}


@router.get("/data-summary")
async def data_summary(user=Depends(current_user), db=Depends(db_dep)):
    uid = user["_id"]
    return {
        "statements": await db[STATEMENT_UPLOADS].count_documents({"user_id": uid, "processing_status": "completed"}),
        "demo_statements": await db[STATEMENT_UPLOADS].count_documents({"user_id": uid, "is_demo": True}),
        "transactions": await db[RAW_TRANSACTIONS].count_documents({"user_id": uid}),
        "custom_rules": await db[CATEGORIZATION_RULES].count_documents({"user_id": uid, "is_default": False}),
        "custom_categories": await db[CATEGORIES].count_documents({"user_id": uid, "is_default": False}),
        "demo_available": all((SAMPLE_DIR / f).exists() for f in DEMO_FILES),
    }


@router.post("/demo-data")
async def load_demo_data(user=Depends(verified_user), db=Depends(db_dep)):
    """Optional demo mode: imports bundled SYNTHETIC statements through the real pipeline."""
    await limit(db, "demo:user", str(user["_id"]), 10, 3600)
    imported = []
    for name in DEMO_FILES:
        path = SAMPLE_DIR / name
        if not path.exists():
            raise AppError("Demo statements are not available on this server", 404, "not_found")
        try:
            res = await create_preview(db, user["_id"], f"demo_{name}", "text/csv", path.read_bytes(), is_demo=True)
        except AppError as e:
            if e.code == "duplicate_statement":
                continue
            raise
        up = await confirm_import(db, user["_id"], res["upload"]["_id"])
        imported.append({"file_name": up["file_name"], "transactions": up["transaction_count"]})
    return {"imported": imported}


@router.delete("/demo-data")
async def remove_demo_data(user=Depends(current_user), db=Depends(db_dep)):
    removed = 0
    for up in await db[STATEMENT_UPLOADS].find({"user_id": user["_id"], "is_demo": True}).to_list(None):
        removed += (await delete_statement(db, user["_id"], up["_id"]))["deleted_transactions"]
    return {"deleted_transactions": removed}


async def _wipe(db, uid, keep_setup: bool):
    for coll in (RAW_TRANSACTIONS, STAGED_TRANSACTIONS, STATEMENT_UPLOADS, SPENDING_SUMMARIES, ANOMALY_REVIEWS):
        await db[coll].delete_many({"user_id": uid})
    if not keep_setup:
        await db[CATEGORIZATION_RULES].delete_many({"user_id": uid})
        await db[CATEGORIES].delete_many({"user_id": uid})
        await db[BUDGETS].delete_many({"user_id": uid})
        await db[ACCOUNTS].delete_many({"user_id": uid})
        await db[LEARNING_DISMISSED].delete_many({"user_id": uid})
        await db[RECURRING_IGNORED].delete_many({"user_id": uid})
        await db[AUTH_TOKENS].delete_many({"user_id": uid})


@router.get("/export")
async def export_my_data(user=Depends(current_user), db=Depends(db_dep)):
    """Right of access (DPDP Act): a complete machine-readable copy of everything stored about the user."""
    await limit(db, "export:user", str(user["_id"]), 10, 3600)
    uid = user["_id"]

    async def all_of(coll, projection=None):
        return to_json(await db[coll].find({"user_id": uid}, projection).to_list(None))

    profile = to_json(user)
    profile.pop("token_version", None)
    data = {
        "exported_at": utcnow().isoformat() + "Z",
        "about": "Export of all personal data Tally stores for your account. Uploaded files themselves are never stored.",
        "profile": profile,
        "statements": await all_of(STATEMENT_UPLOADS),
        "transactions": await all_of(RAW_TRANSACTIONS),
        "categories": await all_of(CATEGORIES),
        "categorization_rules": await all_of(CATEGORIZATION_RULES),
        "budgets": await all_of(BUDGETS),
        "accounts": await all_of(ACCOUNTS),
        "dismissed_rule_suggestions": await all_of(LEARNING_DISMISSED),
        "recurring_ignored": await all_of(RECURRING_IGNORED),
        "anomaly_reviews": await all_of(ANOMALY_REVIEWS),
        "monthly_summaries": await all_of(SPENDING_SUMMARIES),
    }
    return Response(json.dumps(data, ensure_ascii=False, indent=2, default=str), media_type="application/json",
                    headers={"Content-Disposition": "attachment; filename=tally-my-data.json"})


@router.delete("/data")
async def delete_all_data(user=Depends(current_user), db=Depends(db_dep)):
    """Delete all statements and transactions; keeps the account, categories and rules."""
    await _wipe(db, user["_id"], keep_setup=True)
    return {"ok": True}


@router.delete("/account")
async def delete_account(body: dict, user=Depends(current_user), db=Depends(db_dep)):
    if not verify_password(str(body.get("password", ""))[:72], user["password_hash"]):
        raise AppError("Password is incorrect", 400, "invalid_password")
    await _wipe(db, user["_id"], keep_setup=False)
    await db[USERS].delete_one({"_id": user["_id"]})
    return {"ok": True}
