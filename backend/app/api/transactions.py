from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response

from app.api.deps import current_user, db_dep
from app.core.errors import AppError
from app.core.ratelimit import limit as rate_limit
from app.database.mongo import ACCOUNTS, CATEGORIES, RAW_TRANSACTIONS, STATEMENT_UPLOADS
from app.schemas.requests import BulkCategoryUpdate, TransactionUpdate
from app.services.categories import load_engine
from app.services.exports import MAX_EXPORT_ROWS, build_csv, build_xlsx, export_row
from app.services.query import build_filter, category_map, oid, resolve_period
from app.services.summaries import refresh_summaries
from app.utils.dates import now_ist, utcnow
from app.utils.payment import PAYMENT_METHODS
from app.utils.serialize import to_json

router = APIRouter(prefix="/transactions", tags=["transactions"])

SORTS = {"date": "transaction_date", "amount": "amount", "merchant": "normalized_merchant"}


def _decorate(doc: dict, cats: dict) -> dict:
    j = to_json(doc)
    c = cats.get(str(doc.get("category_id")), {})
    j["category_name"], j["category_color"] = c.get("name"), c.get("color")
    return j


class TxnFilters:
    """Query parameters shared by list and export."""

    def __init__(
        self,
        start: str | None = None, end: str | None = None, month: int | None = Query(None, ge=1, le=12),
        year: int | None = Query(None, ge=1990, le=2100), upload_id: str | None = None, account_id: str | None = None,
        category_id: str | None = None, type: str | None = Query(None, pattern="^(debit|credit)$"),
        payment_method: str | None = None, search: str | None = Query(None, max_length=100),
        needs_review: bool | None = None, min_amount: float | None = None, max_amount: float | None = None,
        merchant: str | None = Query(None, max_length=100),
    ):
        self.args = (start, end, month, year)
        self.rest = dict(upload_id=upload_id, account_id=account_id, category_id=category_id, transaction_type=type,
                         payment_method=payment_method, search=search, needs_review=needs_review,
                         min_amount=min_amount, max_amount=max_amount, merchant=merchant)

    def query(self, user_id) -> dict:
        return build_filter(user_id, resolve_period(*self.args), **self.rest)


@router.get("/payment-methods")
async def payment_methods(_=Depends(current_user)):
    return PAYMENT_METHODS


@router.get("")
async def list_transactions(
    f: TxnFilters = Depends(),
    sort: str = Query("date", pattern="^(date|amount|merchant)$"), order: str = Query("desc", pattern="^(asc|desc)$"),
    page: int = Query(1, ge=1), page_size: int = Query(25, ge=1, le=200),
    user=Depends(current_user), db=Depends(db_dep),
):
    q = f.query(user["_id"])
    direction = -1 if order == "desc" else 1
    total = await db[RAW_TRANSACTIONS].count_documents(q)
    docs = await (db[RAW_TRANSACTIONS].find(q, {"raw_bank_fields": 0})
                  .sort([(SORTS[sort], direction), ("_id", direction)])
                  .skip((page - 1) * page_size).limit(page_size).to_list(None))
    cats = await category_map(db, user["_id"])
    return {"items": [_decorate(d, cats) for d in docs], "total": total, "page": page, "page_size": page_size,
            "pages": max(1, -(-total // page_size))}


def _export_name(f: TxnFilters, ext: str) -> str:
    """tally-transactions-2025-08.csv - built from parsed dates only, never from raw query text."""
    p = resolve_period(*f.args)
    if f.args[2] and f.args[3]:
        token = f"{f.args[3]}-{f.args[2]:02d}"
    elif f.args[3] and not f.args[2]:
        token = str(f.args[3])
    elif p.start or p.end:
        token = f"{p.start:%Y-%m-%d}" if p.start else "start"
        token += f"_to_{p.end:%Y-%m-%d}" if p.end else "_onwards"
    else:
        token = "all-time"
    return f"tally-transactions-{token}.{ext}"


async def _describe_filters(f: TxnFilters, cats: dict, db, user_id) -> list[tuple[str, str]]:
    p = resolve_period(*f.args)
    out = []
    if p.start or p.end:
        first = f"{p.start:%d %b %Y}" if p.start else "the beginning"
        out.append(("Period", first + (f" to {p.end:%d %b %Y}" if p.end else " onwards")))
    r = f.rest
    if r["category_id"]:
        out.append(("Category", cats.get(r["category_id"], {}).get("name", "(unknown)")))
    if r["account_id"]:
        acc = None if r["account_id"] == "none" else await db[ACCOUNTS].find_one({"_id": oid(r["account_id"], "account id"), "user_id": user_id})
        out.append(("Account", "Not filed under an account" if r["account_id"] == "none" else (acc or {}).get("name", "(unknown)")))
    if r["upload_id"]:
        up = await db[STATEMENT_UPLOADS].find_one({"_id": oid(r["upload_id"], "statement id"), "user_id": user_id})
        out.append(("Statement", (up or {}).get("file_name", "(unknown)")))
    labels = {"transaction_type": "Type", "payment_method": "Payment method", "search": "Search text", "merchant": "Merchant",
              "min_amount": "Minimum amount", "max_amount": "Maximum amount"}
    out += [(labels[k], str(r[k]).capitalize() if k == "transaction_type" else str(r[k])) for k in labels if r[k] not in (None, "")]
    if r["needs_review"]:
        out.append(("Needs review", "Yes"))
    return out or [("Filters", "None - every transaction")]


@router.get("/export")
async def export_transactions(f: TxnFilters = Depends(), format: str = Query("csv", pattern="^(csv|xlsx)$"),
                              user=Depends(current_user), db=Depends(db_dep)):
    """Every transaction matching the filters (not just one page), as CSV or Excel."""
    uid = user["_id"]
    await rate_limit(db, "export:transactions", str(uid), 30, 3600)
    q = f.query(uid)
    total = await db[RAW_TRANSACTIONS].count_documents(q)
    if total > MAX_EXPORT_ROWS:
        raise AppError(f"That is {total:,} transactions; an export can hold {MAX_EXPORT_ROWS:,}. "
                       "Narrow the date range or filters and try again.", 400, "too_many_rows")
    cats = await category_map(db, uid)
    docs = await (db[RAW_TRANSACTIONS].find(q, {"raw_bank_fields": 0}).sort([("transaction_date", 1), ("_id", 1)])
                  .to_list(None))
    accounts = {str(a["_id"]): a["name"] async for a in db[ACCOUNTS].find({"user_id": uid}, {"name": 1})}
    rows = [export_row(t, cats, accounts) for t in docs]
    if format == "xlsx":
        debits = sum(t.get("debit_amount") or 0 for t in docs)
        credits = sum(t.get("credit_amount") or 0 for t in docs)
        about = [("Exported", f"{now_ist():%d %b %Y, %H:%M} IST"), ("Transactions", f"{len(rows):,}"),
                 ("Total debits", f"{debits:,.2f}"), ("Total credits", f"{credits:,.2f}")]
        about += await _describe_filters(f, cats, db, uid)
        content, media = build_xlsx(rows, about), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    else:
        content, media = build_csv(rows), "text/csv; charset=utf-8"
    return Response(content=content, media_type=media,
                    headers={"Content-Disposition": f'attachment; filename="{_export_name(f, format)}"'})


@router.get("/{txn_id}")
async def get_transaction(txn_id: str, user=Depends(current_user), db=Depends(db_dep)):
    t = await db[RAW_TRANSACTIONS].find_one({"_id": oid(txn_id), "user_id": user["_id"]})
    if not t:
        raise AppError("Transaction not found", 404, "not_found")
    return _decorate(t, await category_map(db, user["_id"]))


@router.patch("/{txn_id}")
async def update_transaction(txn_id: str, body: TransactionUpdate, user=Depends(current_user), db=Depends(db_dep)):
    t = await db[RAW_TRANSACTIONS].find_one({"_id": oid(txn_id), "user_id": user["_id"]})
    if not t:
        raise AppError("Transaction not found", 404, "not_found")
    update: dict = {"updated_at": utcnow()}
    category_changed = False
    if body.notes is not None:
        update["notes"] = body.notes.strip()
    if body.reset_category:
        t["manual_override"] = False
        fields = (await load_engine(db, user["_id"])).apply(t)
        update.update({"category_id": oid(fields["category_id"]) if fields["category_id"] else None,
                       "matched_rule_id": oid(fields["matched_rule_id"]) if fields["matched_rule_id"] else None,
                       "categorization_source": fields["categorization_source"],
                       "needs_review": fields["needs_review"], "manual_override": False})
        category_changed = True
    elif body.category_id is not None:
        cid = oid(body.category_id, "category id")
        if not await db[CATEGORIES].find_one({"_id": cid, "user_id": user["_id"]}):
            raise AppError("Category not found", 404, "not_found")
        update.update({"category_id": cid, "manual_override": True, "categorization_source": "manual",
                       "matched_rule_id": None, "needs_review": False})
        category_changed = True
    await db[RAW_TRANSACTIONS].update_one({"_id": t["_id"]}, {"$set": update})
    if category_changed:
        await refresh_summaries(db, user["_id"])
    t = await db[RAW_TRANSACTIONS].find_one({"_id": t["_id"]})
    return _decorate(t, await category_map(db, user["_id"]))


@router.post("/bulk-category")
async def bulk_category(body: BulkCategoryUpdate, user=Depends(current_user), db=Depends(db_dep)):
    cid = oid(body.category_id, "category id")
    if not await db[CATEGORIES].find_one({"_id": cid, "user_id": user["_id"]}):
        raise AppError("Category not found", 404, "not_found")
    ids = [oid(i, "transaction id") for i in body.transaction_ids]
    res = await db[RAW_TRANSACTIONS].update_many(
        {"_id": {"$in": ids}, "user_id": user["_id"]},
        {"$set": {"category_id": cid, "manual_override": True, "categorization_source": "manual",
                  "matched_rule_id": None, "needs_review": False, "updated_at": utcnow()}},
    )
    await refresh_summaries(db, user["_id"])
    return {"updated": res.modified_count}
