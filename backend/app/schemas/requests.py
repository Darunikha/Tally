"""Pydantic request schemas (all API input is validated here)."""
from typing import Literal

from pydantic import BaseModel, EmailStr, Field, field_validator

HEX_COLOR = r"^#[0-9A-Fa-f]{6}$"


class RegisterRequest(BaseModel):
    email: EmailStr
    full_name: str = Field(min_length=1, max_length=80)
    password: str = Field(min_length=8, max_length=72)

    @field_validator("password")
    @classmethod
    def strong_enough(cls, v: str) -> str:
        if not any(c.isdigit() for c in v) or not any(c.isalpha() for c in v):
            raise ValueError("Password must contain letters and numbers")
        return v


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=72)


class ProfileUpdate(BaseModel):
    full_name: str | None = Field(default=None, min_length=1, max_length=80)
    anomaly_sensitivity: Literal["low", "medium", "high"] | None = None
    large_transaction_threshold: float | None = Field(default=None, ge=0, le=100_000_000)
    clear_large_threshold: bool = False


class PasswordChange(BaseModel):
    current_password: str = Field(min_length=1, max_length=72)
    new_password: str = Field(min_length=8, max_length=72)

    @field_validator("new_password")
    @classmethod
    def strong_enough(cls, v: str) -> str:
        return RegisterRequest.strong_enough(v)


class TransactionUpdate(BaseModel):
    category_id: str | None = None
    notes: str | None = Field(default=None, max_length=500)
    reset_category: bool = False  # drop manual override and let rules decide again


class BulkCategoryUpdate(BaseModel):
    transaction_ids: list[str] = Field(min_length=1, max_length=500)
    category_id: str


class CategoryCreate(BaseModel):
    name: str = Field(min_length=1, max_length=40)
    color: str = Field(default="#2F7D55", pattern=HEX_COLOR)
    description: str = Field(default="", max_length=200)


class CategoryUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=40)
    color: str | None = Field(default=None, pattern=HEX_COLOR)
    description: str | None = Field(default=None, max_length=200)


class RuleCreate(BaseModel):
    rule_name: str = Field(min_length=1, max_length=60)
    regex_pattern: str = Field(min_length=1, max_length=300)
    category_id: str
    priority: int = Field(default=50, ge=0, le=1000)
    applies_to: Literal["debit", "credit", "any"] = "any"
    enabled: bool = True


class RuleUpdate(BaseModel):
    rule_name: str | None = Field(default=None, min_length=1, max_length=60)
    regex_pattern: str | None = Field(default=None, min_length=1, max_length=300)
    category_id: str | None = None
    priority: int | None = Field(default=None, ge=0, le=1000)
    applies_to: Literal["debit", "credit", "any"] | None = None
    enabled: bool | None = None


class RuleTest(BaseModel):
    regex_pattern: str = Field(min_length=1, max_length=300)
    sample: str | None = Field(default=None, max_length=300)


class ConfirmImport(BaseModel):
    include_duplicates: bool = False


class AnomalyReview(BaseModel):
    status: Literal["reviewed", "dismissed", "open"]
