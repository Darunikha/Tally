"""Per-user category/rule seeding, engine loading and re-categorization."""
from __future__ import annotations

from bson import ObjectId
from pymongo import UpdateOne

from pymongo.errors import DuplicateKeyError

from app.categorization.defaults import (ADDED_IN_V2, CARD_PAYMENTS_CATEGORY, DEFAULT_CATEGORIES, DEFAULT_RULES,
                                         DEFAULTS_VERSION, OTHER_CATEGORY)
from app.categorization.engine import CategorizationEngine
from app.database.mongo import CATEGORIES, CATEGORIZATION_RULES, RAW_TRANSACTIONS, USERS
from app.models.documents import category_doc, rule_doc
from app.utils.dates import utcnow


async def seed_user_defaults(db, user_id: ObjectId) -> None:
    if await db[CATEGORIES].count_documents({"user_id": user_id}) == 0:
        cats = [category_doc(user_id, n, c, d, is_default=True, excluded_from_totals=n == CARD_PAYMENTS_CATEGORY)
                for n, c, d in DEFAULT_CATEGORIES]
        await db[CATEGORIES].insert_many(cats)
    if await db[CATEGORIZATION_RULES].count_documents({"user_id": user_id}) == 0:
        by_name = {c["name"]: c["_id"] async for c in db[CATEGORIES].find({"user_id": user_id})}
        rules = [
            rule_doc(user_id, name, rx, by_name[cat], prio, applies, is_default=True)
            for name, rx, cat, prio, applies in DEFAULT_RULES
            if cat in by_name
        ]
        await db[CATEGORIZATION_RULES].insert_many(rules)
    await db[USERS].update_one({"_id": user_id}, {"$set": {"defaults_version": DEFAULTS_VERSION}})


async def ensure_defaults(db, user_id: ObjectId) -> None:
    """Top up an older account with the defaults added since it was created (credit card payments category and
    rules). Runs once per account: later edits or deletions by the user are never undone."""
    user = await db[USERS].find_one({"_id": user_id}, {"defaults_version": 1})
    if user is None or user.get("defaults_version", 1) >= DEFAULTS_VERSION:
        return
    cats = {c["name"]: c async for c in db[CATEGORIES].find({"user_id": user_id})}
    if not any(c.get("excluded_from_totals") for c in cats.values()):
        existing = cats.get(CARD_PAYMENTS_CATEGORY)
        if existing:
            await db[CATEGORIES].update_one({"_id": existing["_id"]}, {"$set": {"excluded_from_totals": True}})
        else:
            name, color, desc = next(c for c in DEFAULT_CATEGORIES if c[0] == CARD_PAYMENTS_CATEGORY)
            doc = category_doc(user_id, name, color, desc, is_default=True, excluded_from_totals=True)
            try:
                await db[CATEGORIES].insert_one(doc)
                cats[name] = doc
            except DuplicateKeyError:  # a concurrent import added it first
                cats[name] = await db[CATEGORIES].find_one({"user_id": user_id, "name": name})
    have = {r["rule_name"] async for r in db[CATEGORIZATION_RULES].find({"user_id": user_id}, {"rule_name": 1})}
    new_rules = [rule_doc(user_id, name, rx, cats[cat]["_id"], prio, applies, is_default=True)
                 for name, rx, cat, prio, applies in DEFAULT_RULES
                 if name in ADDED_IN_V2 and name not in have and cat in cats]
    if new_rules:
        await db[CATEGORIZATION_RULES].insert_many(new_rules)
    await db[USERS].update_one({"_id": user_id}, {"$set": {"defaults_version": DEFAULTS_VERSION}})


async def other_category_id(db, user_id: ObjectId) -> ObjectId | None:
    doc = await db[CATEGORIES].find_one({"user_id": user_id, "name": OTHER_CATEGORY})
    if doc is None:
        doc = category_doc(user_id, OTHER_CATEGORY, "#B8B2A7", "Uncategorized - needs review", is_default=True)
        await db[CATEGORIES].insert_one(doc)
    return doc["_id"]


async def load_engine(db, user_id: ObjectId) -> CategorizationEngine:
    rules = await db[CATEGORIZATION_RULES].find({"user_id": user_id, "enabled": True}).to_list(None)
    return CategorizationEngine(rules, str(await other_category_id(db, user_id)))


def apply_engine(engine: CategorizationEngine, docs: list[dict]) -> None:
    """Categorize documents in place (manual overrides untouched)."""
    for d in docs:
        fields = engine.apply(d)
        if fields:
            fields["category_id"] = ObjectId(fields["category_id"]) if fields["category_id"] else None
            fields["matched_rule_id"] = ObjectId(fields["matched_rule_id"]) if fields["matched_rule_id"] else None
            d.update(fields)


async def recategorize_all(db, user_id: ObjectId) -> int:
    """Re-run rules over all non-manual transactions. Returns number of changed transactions."""
    engine = await load_engine(db, user_id)
    ops = []
    cursor = db[RAW_TRANSACTIONS].find(
        {"user_id": user_id, "manual_override": {"$ne": True}},
        {"normalized_merchant": 1, "raw_description": 1, "transaction_type": 1, "category_id": 1, "manual_override": 1},
    )
    changed = 0
    async for t in cursor:
        before = t.get("category_id")
        apply_engine(engine, [t])
        changed += t.get("category_id") != before
        # always write: the matched rule / source may change even when the category does not
        ops.append(UpdateOne({"_id": t["_id"]}, {"$set": {
            "category_id": t["category_id"], "matched_rule_id": t["matched_rule_id"],
            "categorization_source": t["categorization_source"], "needs_review": t["needs_review"],
            "updated_at": utcnow(),
        }}))
    for i in range(0, len(ops), 1000):
        await db[RAW_TRANSACTIONS].bulk_write(ops[i:i + 1000], ordered=False)
    return changed
