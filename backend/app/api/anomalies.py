from fastapi import APIRouter, Depends, Query

from app.anomaly_detection.detector import DISCLAIMER, TYPE_LABELS, detect_anomalies
from app.api.deps import current_user, db_dep
from app.database.mongo import ANOMALY_REVIEWS
from app.schemas.requests import AnomalyReview
from app.services.query import build_filter, category_map, excluded_category_ids, load_transactions, resolve_period
from app.utils.dates import utcnow

router = APIRouter(prefix="/anomalies", tags=["anomalies"])


async def _anomalies(db, user, start=None, end=None, month=None, year=None, upload_id=None):
    period = resolve_period(start, end, month, year)
    # baselines use the user's full history; results are limited to the requested period
    excluded = await excluded_category_ids(db, user["_id"])  # a big card bill payment is not an unusual purchase
    history = await load_transactions(db, build_filter(user["_id"], None, upload_id=upload_id, exclude_category_ids=excluded))
    s = user.get("settings", {})
    found = detect_anomalies(history, await category_map(db, user["_id"]), period.start, period.end,
                             s.get("anomaly_sensitivity", "medium"), s.get("large_transaction_threshold"))
    reviews = {r["anomaly_key"]: r["status"] async for r in db[ANOMALY_REVIEWS].find({"user_id": user["_id"]})}
    for a in found:
        a["status"] = reviews.get(a["key"], "open")
    return found


@router.get("")
async def list_anomalies(start: str | None = None, end: str | None = None,
                         month: int | None = Query(None, ge=1, le=12), year: int | None = Query(None, ge=1990, le=2100),
                         upload_id: str | None = None, status: str | None = Query(None, pattern="^(open|reviewed|dismissed)$"),
                         severity: str | None = Query(None, pattern="^(low|medium|high)$"),
                         user=Depends(current_user), db=Depends(db_dep)):
    found = await _anomalies(db, user, start, end, month, year, upload_id)
    counts = {
        "total": len(found),
        "open": sum(a["status"] == "open" for a in found),
        "high": sum(a["severity"] == "high" and a["status"] == "open" for a in found),
        "medium": sum(a["severity"] == "medium" and a["status"] == "open" for a in found),
        "low": sum(a["severity"] == "low" and a["status"] == "open" for a in found),
        "by_type": {t: sum(a["type"] == t for a in found) for t in TYPE_LABELS},
    }
    if status:
        found = [a for a in found if a["status"] == status]
    if severity:
        found = [a for a in found if a["severity"] == severity]
    return {"items": found, "counts": counts, "disclaimer": DISCLAIMER, "types": TYPE_LABELS,
            "sensitivity": user.get("settings", {}).get("anomaly_sensitivity", "medium")}


@router.put("/{anomaly_key}/review")
async def review(anomaly_key: str, body: AnomalyReview, user=Depends(current_user), db=Depends(db_dep)):
    key = anomaly_key[:40]
    if body.status == "open":
        await db[ANOMALY_REVIEWS].delete_one({"user_id": user["_id"], "anomaly_key": key})
    else:
        await db[ANOMALY_REVIEWS].update_one(
            {"user_id": user["_id"], "anomaly_key": key},
            {"$set": {"status": body.status, "updated_at": utcnow()}}, upsert=True)
    return {"key": key, "status": body.status}
