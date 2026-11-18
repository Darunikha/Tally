"""Statement import pipeline.

  preview:  validate -> parse (adapter) -> normalize -> categorize -> dedupe -> stage (no import yet)
  confirm:  staged -> raw_transactions (duplicates skipped) -> upload completed -> summaries refreshed
  cancel:   staged + upload removed
  delete:   upload marked 'deleting' -> its transactions removed -> upload removed -> summaries refreshed
            (idempotent: safe to retry if interrupted)

Uploaded files are never kept: bytes are processed in memory (the framework may spool uploads over 1 MB to a
temp file, which is closed and deleted immediately) and never saved to the database.
"""
from __future__ import annotations

import logging
from datetime import timedelta

from bson import ObjectId
from pymongo.errors import BulkWriteError
from starlette.concurrency import run_in_threadpool

from app.core.errors import AppError
from app.database.mongo import RAW_TRANSACTIONS, STAGED_TRANSACTIONS, STATEMENT_UPLOADS
from app.models.documents import upload_doc
from app.parsers.base import ParseError, PasswordRequired
from app.parsers.registry import parse_statement
from app.services.accounts import check_for_statement
from app.services.categories import apply_engine, ensure_defaults, load_engine
from app.services.file_validation import validate_upload
from app.services.normalization import normalize
from app.services.summaries import refresh_summaries
from app.utils.dates import utcnow
from app.utils.money import r2

log = logging.getLogger("tally.statements")

PREVIEW_ROWS = 100
STALE_PREVIEW = timedelta(hours=24)


async def _cleanup_stale_previews(db, user_id: ObjectId) -> None:
    cutoff = utcnow() - STALE_PREVIEW
    stale = await db[STATEMENT_UPLOADS].find(
        {"user_id": user_id, "processing_status": {"$in": ["pending_review", "processing", "failed"]},
         "upload_date": {"$lt": cutoff}}, {"_id": 1}
    ).to_list(None)
    ids = [s["_id"] for s in stale]
    if ids:
        await db[STAGED_TRANSACTIONS].delete_many({"user_id": user_id, "upload_id": {"$in": ids}})
        await db[STATEMENT_UPLOADS].delete_many({"user_id": user_id, "_id": {"$in": ids}})


async def create_preview(db, user_id: ObjectId, filename: str, content_type: str | None, content: bytes,
                         bank_hint: str | None = None, is_demo: bool = False, password: str | None = None) -> dict:
    """`password` unlocks an encrypted PDF. It is passed straight to the parser, kept in memory only,
    and never stored, logged or echoed back."""
    safe_name, ftype, fhash = validate_upload(filename, content_type, content)
    await _cleanup_stale_previews(db, user_id)

    existing = await db[STATEMENT_UPLOADS].find_one(
        {"user_id": user_id, "file_hash": fhash, "processing_status": {"$in": ["completed", "pending_review"]}}
    )
    if existing and existing["processing_status"] == "completed":
        raise AppError("This statement file has already been imported.", 409, "duplicate_statement",
                       {"upload_id": str(existing["_id"]), "file_name": existing["file_name"]})
    if existing:  # an earlier unconfirmed preview of the same file - replace it
        await cancel_preview(db, user_id, existing["_id"])

    up = upload_doc(user_id, safe_name, ftype, fhash, len(content))
    up["is_demo"] = is_demo
    await db[STATEMENT_UPLOADS].insert_one(up)

    try:
        result, parser = await run_in_threadpool(parse_statement, content, ftype, bank_hint, password)
    except PasswordRequired as exc:
        # not a failed import - just waiting for the password, so leave no trace in history
        await db[STATEMENT_UPLOADS].delete_one({"_id": up["_id"]})
        code = "pdf_password_incorrect" if exc.incorrect else "pdf_password_required"
        raise AppError(str(exc), 422, code) from None
    except ParseError as exc:
        await db[STATEMENT_UPLOADS].update_one({"_id": up["_id"]}, {"$set": {"processing_status": "failed", "error": str(exc)}})
        raise AppError(str(exc), 422, "parse_error", {"upload_id": str(up["_id"])}) from None
    except Exception:
        log.exception("Unexpected parser failure for upload %s", up["_id"])
        await db[STATEMENT_UPLOADS].update_one({"_id": up["_id"]}, {"$set": {"processing_status": "failed", "error": "Parser error"}})
        raise AppError("The statement could not be processed.", 422, "parse_error", {"upload_id": str(up["_id"])}) from None
    finally:
        del content  # drop our reference to the uploaded bytes as early as possible

    docs = normalize(result.transactions, parser, result.bank_name, user_id, up["_id"], result.account_type)
    await ensure_defaults(db, user_id)
    apply_engine(await load_engine(db, user_id), docs)

    fps = [d["fingerprint"] for d in docs]
    existing_fps = set()
    for i in range(0, len(fps), 1000):
        async for e in db[RAW_TRANSACTIONS].find({"user_id": user_id, "fingerprint": {"$in": fps[i:i + 1000]}}, {"fingerprint": 1}):
            existing_fps.add(e["fingerprint"])
    for d in docs:
        d["is_duplicate"] = d["fingerprint"] in existing_fps

    new_docs = [d for d in docs if not d["is_duplicate"]]
    dates = [d["transaction_date"] for d in docs]
    stats = {
        "bank_name": result.bank_name,
        "account_type": result.account_type,
        "parser_used": result.parser_used,
        "processing_status": "pending_review",
        "parsed_count": len(docs),
        "duplicate_count": len(docs) - len(new_docs),
        "transaction_count": 0,
        "total_debits": r2(sum(d["debit_amount"] for d in new_docs)),
        "total_credits": r2(sum(d["credit_amount"] for d in new_docs)),
        "date_range": {"start": min(dates), "end": max(dates)},
        "warnings": result.warnings,
    }
    await db[STATEMENT_UPLOADS].update_one({"_id": up["_id"]}, {"$set": stats})
    if docs:
        await db[STAGED_TRANSACTIONS].insert_many(docs)
    up.update(stats)
    return {"upload": up, "transactions": docs[:PREVIEW_ROWS], "new_count": len(new_docs),
            "uncategorized_count": sum(1 for d in new_docs if d.get("needs_review"))}


async def _get_upload(db, user_id: ObjectId, upload_id: ObjectId) -> dict:
    up = await db[STATEMENT_UPLOADS].find_one({"_id": upload_id, "user_id": user_id})
    if not up:
        raise AppError("Statement not found", 404, "not_found")
    return up


async def confirm_import(db, user_id: ObjectId, upload_id: ObjectId, include_duplicates: bool = False,
                         account_id: str | None = None) -> dict:
    up = await _get_upload(db, user_id, upload_id)
    if up["processing_status"] != "pending_review":
        raise AppError(f"Statement is not awaiting confirmation (status: {up['processing_status']}).", 409, "invalid_state")
    account = await check_for_statement(db, user_id, account_id, up.get("account_type", "bank")) if account_id else None

    staged = await db[STAGED_TRANSACTIONS].find({"user_id": user_id, "upload_id": upload_id}).to_list(None)
    to_insert = []
    for d in staged:
        dup = d.pop("is_duplicate", False)
        if dup and not include_duplicates:
            continue
        if dup:
            d["fingerprint"] = f"{d['fingerprint']}:{upload_id}"  # user explicitly kept a duplicate
        d["created_at"] = d["updated_at"] = utcnow()
        d["account_id"] = account
        to_insert.append(d)

    inserted, skipped = 0, len(staged) - len(to_insert)
    if to_insert:
        try:
            res = await db[RAW_TRANSACTIONS].insert_many(to_insert, ordered=False)
            inserted = len(res.inserted_ids)
        except BulkWriteError as bwe:  # rows imported concurrently by another upload
            inserted = bwe.details.get("nInserted", 0)
            skipped += len(to_insert) - inserted

    imported = await db[RAW_TRANSACTIONS].find(
        {"user_id": user_id, "upload_id": upload_id}, {"debit_amount": 1, "credit_amount": 1, "transaction_date": 1}
    ).to_list(None)
    dates = [t["transaction_date"] for t in imported]
    update = {
        "processing_status": "completed",
        "transaction_count": len(imported),
        "duplicate_count": skipped,
        "total_debits": r2(sum(t["debit_amount"] for t in imported)),
        "total_credits": r2(sum(t["credit_amount"] for t in imported)),
        "date_range": {"start": min(dates) if dates else None, "end": max(dates) if dates else None},
        "completed_at": utcnow(),
        "account_id": account,
    }
    await db[STATEMENT_UPLOADS].update_one({"_id": upload_id}, {"$set": update})
    await db[STAGED_TRANSACTIONS].delete_many({"user_id": user_id, "upload_id": upload_id})
    await refresh_summaries(db, user_id)
    up.update(update)
    log.info("Upload %s imported: %d transactions, %d skipped", upload_id, inserted, skipped)
    return up


async def cancel_preview(db, user_id: ObjectId, upload_id: ObjectId) -> None:
    up = await _get_upload(db, user_id, upload_id)
    if up["processing_status"] == "completed":
        raise AppError("Imported statements must be deleted, not cancelled.", 409, "invalid_state")
    await db[STAGED_TRANSACTIONS].delete_many({"user_id": user_id, "upload_id": upload_id})
    await db[STATEMENT_UPLOADS].delete_one({"_id": upload_id, "user_id": user_id})


async def delete_statement(db, user_id: ObjectId, upload_id: ObjectId) -> dict:
    up = await _get_upload(db, user_id, upload_id)
    await db[STATEMENT_UPLOADS].update_one({"_id": upload_id}, {"$set": {"processing_status": "deleting"}})
    res = await db[RAW_TRANSACTIONS].delete_many({"user_id": user_id, "upload_id": upload_id})
    await db[STAGED_TRANSACTIONS].delete_many({"user_id": user_id, "upload_id": upload_id})
    await db[STATEMENT_UPLOADS].delete_one({"_id": upload_id, "user_id": user_id})
    await refresh_summaries(db, user_id)
    log.info("Upload %s deleted with %d transactions", upload_id, res.deleted_count)
    return {"deleted_transactions": res.deleted_count, "file_name": up["file_name"]}


async def resume_interrupted_deletions(db) -> None:
    """On startup, finish any deletion that was interrupted (status stuck at 'deleting')."""
    async for up in db[STATEMENT_UPLOADS].find({"processing_status": "deleting"}):
        await delete_statement(db, up["user_id"], up["_id"])
