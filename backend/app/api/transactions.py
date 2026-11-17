import csv
import io

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse

from app.api.deps import current_user, db_dep
from app.core.errors import AppError
from app.database.mongo import CATEGORIES, RAW_TRANSACTIONS
from app.schemas.requests import BulkCategoryUpdate, TransactionUpdate
from app.services.categories import load_engine
from app.services.query import build_filter, category_map, oid, resolve_period
from app.services.summaries import refresh_summaries
from app.utils.dates import utcnow
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
        year: int | None = Query(None, ge=1990, le=2100), upload_id: str | None = None,
        category_id: str | None = None, type: str | None = Query(None, pattern="^(debit|credit)$"),
        payment_method: str | None = None, search: str | None = Query(None, max_length=100),
        needs_review: bool | None = None, min_amount: float | None = None, max_amount: float | None = None,
        merchant: str | None = Query(None, max_length=100),
    ):
        self.args = (start, end, month, year)
        self.rest = dict(upload_id=upload_id, category_id=category_id, transaction_type=type,
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


@router.get("/export")
async def export_csv(f: TxnFilters = Depends(), user=Depends(current_user), db=Depends(db_dep)):
    q = f.query(user["_id"])
    cats = await category_map(db, user["_id"])
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["Date", "Merchant", "Description", "Type", "Debit", "Credit", "Category", "Payment Method",
                "UPI ID", "Reference", "Bank", "Notes"])
    async for t in db[RAW_TRANSACTIONS].find(q).sort("transaction_date", 1):
        w.writerow([t["transaction_date"].strftime("%Y-%m-%d"), t.get("normalized_merchant"), t.get("raw_description"),
                    t["transaction_type"], t["debit_amount"] or "", t["credit_amount"] or "",
                    cats.get(str(t.get("category_id")), {}).get("name", ""), t.get("payment_method"),
                    t.get("upi_id") or "", t.get("transaction_reference") or "", t.get("bank_name"), t.get("notes") or ""])
    return StreamingResponse(iter([buf.getvalue()]), media_type="text/csv",
                             headers={"Content-Disposition": "attachment; filename=tally-transactions.csv"})


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
