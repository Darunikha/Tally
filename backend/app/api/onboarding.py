"""First-run guidance: a checklist whose steps tick themselves off from the user's real data."""
from fastapi import APIRouter, Depends

from app.api.deps import current_user, db_dep
from app.database.mongo import BUDGETS, RAW_TRANSACTIONS, STATEMENT_UPLOADS, USERS
from app.schemas.requests import OnboardingUpdate

router = APIRouter(prefix="/onboarding", tags=["onboarding"])


async def progress(db, user: dict) -> dict:
    uid = user["_id"]
    done_q = {"user_id": uid, "processing_status": "completed"}
    has_statement = await db[STATEMENT_UPLOADS].count_documents(done_q, limit=1) > 0
    has_filed = await db[STATEMENT_UPLOADS].count_documents({**done_q, "account_id": {"$ne": None}}, limit=1) > 0
    to_review = await db[RAW_TRANSACTIONS].count_documents({"user_id": uid, "needs_review": True}) if has_statement else 0
    has_budget = await db[BUDGETS].count_documents({"user_id": uid}, limit=1) > 0

    steps = [
        {"key": "statement", "title": "Add your first statement", "done": has_statement, "href": "/upload",
         "description": "Upload a CSV, Excel or PDF statement from your bank or card, or try the demo data first."},
        {"key": "account", "title": "File it under an account", "done": has_filed, "href": "/accounts",
         "description": "Say which account it belongs to, so each account gets its own balance and spending."},
        {"key": "review", "title": "Review uncategorised transactions", "done": has_statement and to_review == 0, "href": "/transactions?needs_review=true",
         "description": (f"{to_review:,} transaction{'s' if to_review != 1 else ''} need a category. Fix one and Tally can learn a rule from it."
                         if to_review else "Once you have a statement, check anything Tally could not categorise.")},
        {"key": "budget", "title": "Set a budget", "done": has_budget, "href": "/budgets",
         "description": "Pick a monthly limit for a category and see how you are tracking."},
    ]
    state = user.get("onboarding") or {}
    completed = sum(1 for s in steps if s["done"])
    return {
        "steps": steps, "completed": completed, "total": len(steps),
        # people who already have data have long since found their way around: no welcome tour for them
        "welcome_seen": bool(state.get("welcome_seen", has_statement)),
        "checklist_dismissed": bool(state.get("checklist_dismissed", False)),
        "show_checklist": not state.get("checklist_dismissed", False) and completed < len(steps),
    }


@router.get("")
async def get_onboarding(user=Depends(current_user), db=Depends(db_dep)):
    return await progress(db, user)


@router.patch("")
async def update_onboarding(body: OnboardingUpdate, user=Depends(current_user), db=Depends(db_dep)):
    changes = {f"onboarding.{k}": v for k, v in body.model_dump(exclude_none=True).items()}
    if changes:
        await db[USERS].update_one({"_id": user["_id"]}, {"$set": changes})
    return await progress(db, await db[USERS].find_one({"_id": user["_id"]}))
