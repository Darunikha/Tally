"""Accounts: the bank accounts and credit cards that statements are filed under."""
from fastapi import APIRouter, Depends
from pymongo.errors import DuplicateKeyError

from app.api.deps import current_user, db_dep
from app.core.errors import AppError
from app.database.mongo import ACCOUNTS
from app.schemas.requests import AccountCreate, AccountUpdate
from app.services import accounts as svc
from app.utils.dates import utcnow
from app.utils.serialize import to_json

router = APIRouter(prefix="/accounts", tags=["accounts"])


@router.get("")
async def list_accounts(user=Depends(current_user), db=Depends(db_dep)):
    """Every account with its latest balance and activity, plus statements not filed anywhere yet."""
    return await svc.account_summaries(db, user["_id"])


@router.post("", status_code=201)
async def create_account(body: AccountCreate, user=Depends(current_user), db=Depends(db_dep)):
    doc = await svc.create_account(db, user["_id"], body.name, body.account_type,
                                   (body.bank_name or "").strip() or None, body.last4, body.color)
    return to_json(doc)


@router.post("/auto-setup")
async def auto_setup(user=Depends(current_user), db=Depends(db_dep)):
    """Create an account per bank from statements that aren't filed under one, and file them."""
    return await svc.auto_setup(db, user["_id"])


@router.patch("/{account_id}")
async def update_account(account_id: str, body: AccountUpdate, user=Depends(current_user), db=Depends(db_dep)):
    acc = await svc.get_account(db, user["_id"], account_id)
    update: dict = {}
    if body.name is not None:
        name = body.name.strip()
        if not name:
            raise AppError("Name cannot be empty", 400, "invalid_name")
        update.update(name=name, name_key=name.casefold())
    if body.last4 is not None:
        update["last4"] = body.last4 or None
    if body.color is not None:
        update["color"] = body.color
    if update:
        update["updated_at"] = utcnow()
        try:
            await db[ACCOUNTS].update_one({"_id": acc["_id"]}, {"$set": update})
        except DuplicateKeyError:
            raise AppError(f"You already have an account called '{body.name}'.", 409, "duplicate") from None
    return to_json(await db[ACCOUNTS].find_one({"_id": acc["_id"]}))


@router.delete("/{account_id}")
async def delete_account(account_id: str, user=Depends(current_user), db=Depends(db_dep)):
    """Statements and transactions are kept and become unassigned."""
    return await svc.delete_account(db, user["_id"], account_id)
