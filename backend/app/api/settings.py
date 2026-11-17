from pathlib import Path

from fastapi import APIRouter, Depends

from app.api.deps import current_user, db_dep
from app.core.errors import AppError
from app.core.security import hash_password, verify_password
from app.database.mongo import (ANOMALY_REVIEWS, CATEGORIES, CATEGORIZATION_RULES, RAW_TRANSACTIONS,
                                SPENDING_SUMMARIES, STAGED_TRANSACTIONS, STATEMENT_UPLOADS, USERS)
from app.schemas.requests import PasswordChange, ProfileUpdate
from app.services.statements import confirm_import, create_preview, delete_statement
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
async def change_password(body: PasswordChange, user=Depends(current_user), db=Depends(db_dep)):
    if not verify_password(body.current_password, user["password_hash"]):
        raise AppError("Current password is incorrect", 400, "invalid_password")
    await db[USERS].update_one({"_id": user["_id"]}, {"$set": {"password_hash": hash_password(body.new_password)}})
    return {"ok": True}


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
async def load_demo_data(user=Depends(current_user), db=Depends(db_dep)):
    """Optional demo mode: imports bundled SYNTHETIC statements through the real pipeline."""
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
