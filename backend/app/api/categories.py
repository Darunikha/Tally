from fastapi import APIRouter, Depends
from pymongo.errors import DuplicateKeyError

from app.api.deps import current_user, db_dep
from app.categorization.defaults import OTHER_CATEGORY
from app.categorization.engine import InvalidRuleError, validate_pattern
from app.core.errors import AppError
from app.database.mongo import BUDGETS, CATEGORIES, CATEGORIZATION_RULES, RAW_TRANSACTIONS
from app.models.documents import category_doc, rule_doc
from app.schemas.requests import CategoryCreate, CategoryUpdate, RuleCreate, RuleTest, RuleUpdate
from app.services.categories import other_category_id, recategorize_all
from app.services.query import oid
from app.services.summaries import refresh_summaries
from app.utils.serialize import to_json

router = APIRouter(tags=["categories"])


# ------------------------------------------------------------------ categories
@router.get("/categories")
async def list_categories(user=Depends(current_user), db=Depends(db_dep)):
    cats = await db[CATEGORIES].find({"user_id": user["_id"]}).sort("name", 1).to_list(None)
    counts = {}
    async for t in db[RAW_TRANSACTIONS].find({"user_id": user["_id"]}, {"category_id": 1}):
        counts[t.get("category_id")] = counts.get(t.get("category_id"), 0) + 1
    rules = {}
    async for r in db[CATEGORIZATION_RULES].find({"user_id": user["_id"]}, {"category_id": 1}):
        rules[r["category_id"]] = rules.get(r["category_id"], 0) + 1
    out = []
    for c in cats:
        j = to_json(c)
        j["transaction_count"] = counts.get(c["_id"], 0)
        j["rule_count"] = rules.get(c["_id"], 0)
        out.append(j)
    return out


@router.post("/categories", status_code=201)
async def create_category(body: CategoryCreate, user=Depends(current_user), db=Depends(db_dep)):
    doc = category_doc(user["_id"], body.name.strip(), body.color, body.description.strip())
    try:
        await db[CATEGORIES].insert_one(doc)
    except DuplicateKeyError:
        raise AppError("A category with this name already exists", 409, "duplicate") from None
    return to_json(doc)


@router.patch("/categories/{category_id}")
async def update_category(category_id: str, body: CategoryUpdate, user=Depends(current_user), db=Depends(db_dep)):
    cid = oid(category_id, "category id")
    cat = await db[CATEGORIES].find_one({"_id": cid, "user_id": user["_id"]})
    if not cat:
        raise AppError("Category not found", 404, "not_found")
    update = body.model_dump(exclude_none=True)
    if "name" in update:
        update["name"] = update["name"].strip()
        if cat["name"] == OTHER_CATEGORY and update["name"] != OTHER_CATEGORY:
            raise AppError("The 'Other' fallback category cannot be renamed", 400, "protected")
    if update:
        try:
            await db[CATEGORIES].update_one({"_id": cid}, {"$set": update})
        except DuplicateKeyError:
            raise AppError("A category with this name already exists", 409, "duplicate") from None
        if "name" in update:
            await refresh_summaries(db, user["_id"])
    return to_json(await db[CATEGORIES].find_one({"_id": cid}))


@router.delete("/categories/{category_id}")
async def delete_category(category_id: str, user=Depends(current_user), db=Depends(db_dep)):
    """Deleting moves its transactions to 'Other' (flagged for review) and removes its rules."""
    cid = oid(category_id, "category id")
    cat = await db[CATEGORIES].find_one({"_id": cid, "user_id": user["_id"]})
    if not cat:
        raise AppError("Category not found", 404, "not_found")
    if cat["name"] == OTHER_CATEGORY:
        raise AppError("The 'Other' fallback category cannot be deleted", 400, "protected")
    other = await other_category_id(db, user["_id"])
    moved = await db[RAW_TRANSACTIONS].update_many(
        {"user_id": user["_id"], "category_id": cid},
        {"$set": {"category_id": other, "manual_override": False, "categorization_source": "default",
                  "needs_review": True, "matched_rule_id": None}},
    )
    rules = await db[CATEGORIZATION_RULES].delete_many({"user_id": user["_id"], "category_id": cid})
    await db[BUDGETS].delete_many({"user_id": user["_id"], "category_id": cid})
    await db[CATEGORIES].delete_one({"_id": cid})
    await refresh_summaries(db, user["_id"])
    return {"moved_transactions": moved.modified_count, "deleted_rules": rules.deleted_count}


# ------------------------------------------------------------------ rules
async def _check_category(db, user_id, category_id: str):
    cid = oid(category_id, "category id")
    if not await db[CATEGORIES].find_one({"_id": cid, "user_id": user_id}):
        raise AppError("Category not found", 404, "not_found")
    return cid


def _check_pattern(p: str):
    try:
        validate_pattern(p)
    except InvalidRuleError as e:
        raise AppError(str(e), 400, "invalid_pattern") from None


@router.get("/rules")
async def list_rules(user=Depends(current_user), db=Depends(db_dep)):
    rules = await db[CATEGORIZATION_RULES].find({"user_id": user["_id"]}).sort([("priority", -1), ("rule_name", 1)]).to_list(None)
    cats = {c["_id"]: c async for c in db[CATEGORIES].find({"user_id": user["_id"]})}
    hits = {}
    async for t in db[RAW_TRANSACTIONS].find({"user_id": user["_id"], "matched_rule_id": {"$ne": None}}, {"matched_rule_id": 1}):
        hits[t["matched_rule_id"]] = hits.get(t["matched_rule_id"], 0) + 1
    out = []
    for r in rules:
        j = to_json(r)
        c = cats.get(r["category_id"], {})
        j["category_name"], j["category_color"] = c.get("name"), c.get("color")
        j["match_count"] = hits.get(r["_id"], 0)
        out.append(j)
    return out


@router.post("/rules", status_code=201)
async def create_rule(body: RuleCreate, user=Depends(current_user), db=Depends(db_dep)):
    _check_pattern(body.regex_pattern)
    cid = await _check_category(db, user["_id"], body.category_id)
    doc = rule_doc(user["_id"], body.rule_name.strip(), body.regex_pattern, cid, body.priority, body.applies_to, body.enabled)
    await db[CATEGORIZATION_RULES].insert_one(doc)
    return to_json(doc)


@router.patch("/rules/{rule_id}")
async def update_rule(rule_id: str, body: RuleUpdate, user=Depends(current_user), db=Depends(db_dep)):
    rid = oid(rule_id, "rule id")
    if not await db[CATEGORIZATION_RULES].find_one({"_id": rid, "user_id": user["_id"]}):
        raise AppError("Rule not found", 404, "not_found")
    update = body.model_dump(exclude_none=True)
    if "regex_pattern" in update:
        _check_pattern(update["regex_pattern"])
    if "category_id" in update:
        update["category_id"] = await _check_category(db, user["_id"], update["category_id"])
    if update:
        await db[CATEGORIZATION_RULES].update_one({"_id": rid}, {"$set": update})
    return to_json(await db[CATEGORIZATION_RULES].find_one({"_id": rid}))


@router.delete("/rules/{rule_id}", status_code=204)
async def delete_rule(rule_id: str, user=Depends(current_user), db=Depends(db_dep)):
    res = await db[CATEGORIZATION_RULES].delete_one({"_id": oid(rule_id, "rule id"), "user_id": user["_id"]})
    if not res.deleted_count:
        raise AppError("Rule not found", 404, "not_found")


@router.post("/rules/test")
async def test_rule(body: RuleTest, user=Depends(current_user), db=Depends(db_dep)):
    """Preview which existing transactions a pattern would match (max 20 shown)."""
    _check_pattern(body.regex_pattern)
    rx = validate_pattern(body.regex_pattern)
    if body.sample is not None:
        return {"sample_match": bool(rx.search(body.sample.upper()))}
    matches, total = [], 0
    async for t in db[RAW_TRANSACTIONS].find({"user_id": user["_id"]},
                                             {"normalized_merchant": 1, "raw_description": 1, "amount": 1,
                                              "transaction_date": 1, "transaction_type": 1}):
        if rx.search(f"{t.get('normalized_merchant') or ''} | {t.get('raw_description') or ''}".upper()):
            total += 1
            if len(matches) < 20:
                matches.append(to_json(t))
    return {"match_count": total, "examples": matches}


@router.post("/rules/apply")
async def apply_rules(user=Depends(current_user), db=Depends(db_dep)):
    """Re-run all enabled rules over existing transactions (manual overrides are kept)."""
    changed = await recategorize_all(db, user["_id"])
    await refresh_summaries(db, user["_id"])
    return {"recategorized": changed}
