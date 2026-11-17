from fastapi import APIRouter, Depends, File, Form, Query, UploadFile

from app.api.deps import current_user, db_dep
from app.core.config import get_settings
from app.core.errors import AppError
from app.database.mongo import STAGED_TRANSACTIONS, STATEMENT_UPLOADS
from app.parsers.registry import all_parsers
from app.schemas.requests import ConfirmImport
from app.services import statements as svc
from app.services.query import category_map, oid
from app.utils.serialize import to_json

router = APIRouter(prefix="/statements", tags=["statements"])


def _with_category(docs: list[dict], cats: dict) -> list[dict]:
    out = []
    for d in docs:
        j = to_json(d)
        c = cats.get(str(d.get("category_id")), {})
        j["category_name"], j["category_color"] = c.get("name"), c.get("color")
        j.pop("raw_bank_fields", None)
        out.append(j)
    return out


@router.get("/banks")
async def supported_banks(_=Depends(current_user)):
    return [{"key": p.key, "bank_name": p.bank_name} for p in all_parsers()]


@router.post("/preview", status_code=201)
async def preview(file: UploadFile = File(...), bank: str | None = Form(default=None),
                  user=Depends(current_user), db=Depends(db_dep)):
    limit = get_settings().max_upload_bytes
    try:
        content = await file.read(limit + 1)  # bounded read
    finally:
        await file.close()  # releases any spooled temp file immediately
    if len(content) > limit:
        raise AppError(f"File is larger than {get_settings().max_upload_mb} MB.", 413, "file_too_large")
    if bank and bank not in {p.key for p in all_parsers()}:
        raise AppError("Unknown bank format", 400, "invalid_bank")
    res = await svc.create_preview(db, user["_id"], file.filename or "statement", file.content_type, content, bank or None)
    cats = await category_map(db, user["_id"])
    return {"upload": to_json(res["upload"]), "transactions": _with_category(res["transactions"], cats),
            "new_count": res["new_count"], "uncategorized_count": res["uncategorized_count"]}


@router.get("")
async def history(user=Depends(current_user), db=Depends(db_dep)):
    docs = await db[STATEMENT_UPLOADS].find(
        {"user_id": user["_id"], "processing_status": {"$in": ["completed", "failed", "deleting"]}}
    ).sort("upload_date", -1).to_list(None)
    return [to_json(d) for d in docs]


@router.get("/{upload_id}/staged")
async def staged(upload_id: str, page: int = Query(1, ge=1), page_size: int = Query(100, ge=1, le=500),
                 user=Depends(current_user), db=Depends(db_dep)):
    q = {"user_id": user["_id"], "upload_id": oid(upload_id)}
    total = await db[STAGED_TRANSACTIONS].count_documents(q)
    docs = await (db[STAGED_TRANSACTIONS].find(q).sort("transaction_date", 1)
                  .skip((page - 1) * page_size).limit(page_size).to_list(None))
    return {"items": _with_category(docs, await category_map(db, user["_id"])), "total": total, "page": page}


@router.post("/{upload_id}/confirm")
async def confirm(upload_id: str, body: ConfirmImport | None = None, user=Depends(current_user), db=Depends(db_dep)):
    up = await svc.confirm_import(db, user["_id"], oid(upload_id), (body or ConfirmImport()).include_duplicates)
    return to_json(up)


@router.delete("/{upload_id}/preview", status_code=204)
async def cancel(upload_id: str, user=Depends(current_user), db=Depends(db_dep)):
    await svc.cancel_preview(db, user["_id"], oid(upload_id))


@router.get("/{upload_id}")
async def get_statement(upload_id: str, user=Depends(current_user), db=Depends(db_dep)):
    up = await db[STATEMENT_UPLOADS].find_one({"_id": oid(upload_id), "user_id": user["_id"]})
    if not up:
        raise AppError("Statement not found", 404, "not_found")
    return to_json(up)


@router.delete("/{upload_id}")
async def delete(upload_id: str, user=Depends(current_user), db=Depends(db_dep)):
    return await svc.delete_statement(db, user["_id"], oid(upload_id))
