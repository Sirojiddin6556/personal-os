"""Pydantic v2 schemas for the Finance domain."""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field, model_validator


class AccountCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    type: str = Field(default="checking", pattern="^(checking|savings|credit_card|cash|investment|crypto)$")
    currency: str = Field(default="RUB", min_length=3, max_length=3)
    initial_balance_minor: int = 0


class AccountResponse(BaseModel):
    id: UUID
    workspace_id: UUID
    name: str
    type: str
    currency: str
    initial_balance_minor: int
    current_balance_minor: int
    is_archived: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class CategoryCreate(BaseModel):
    parent_id: Optional[UUID] = None
    name: str = Field(min_length=1, max_length=100)
    icon: Optional[str] = None
    color: str = Field(default="#10B981", pattern="^#[0-9A-Fa-f]{6}$")
    type: str = Field(pattern="^(income|expense|transfer)$")


class CategoryResponse(BaseModel):
    id: UUID
    workspace_id: UUID
    parent_id: Optional[UUID] = None
    name: str
    icon: Optional[str] = None
    color: str
    type: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class TransactionCreate(BaseModel):
    account_id: UUID
    destination_account_id: Optional[UUID] = None
    category_id: Optional[UUID] = None
    amount_minor: int = Field(gt=0, description="Amount in minor units (e.g. cents/kopecks)")
    currency: str = Field(min_length=3, max_length=3)
    type: str = Field(pattern="^(income|expense|transfer)$")
    description: Optional[str] = None
    occurred_at: Optional[datetime] = None

    @model_validator(mode="after")
    def validate_transfer(self):
        if self.type == "transfer":
            if not self.destination_account_id:
                raise ValueError("destination_account_id is required for transfer transactions")
            if self.account_id == self.destination_account_id:
                raise ValueError("Source and destination accounts must be different")
        return self


class TransactionResponse(BaseModel):
    id: UUID
    workspace_id: UUID
    account_id: UUID
    destination_account_id: Optional[UUID] = None
    category_id: Optional[UUID] = None
    reversed_transaction_id: Optional[UUID] = None
    amount_minor: int
    currency: str
    type: str
    status: str
    description: Optional[str] = None
    occurred_at: datetime
    posted_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class BudgetCreate(BaseModel):
    category_id: Optional[UUID] = None
    name: str = Field(min_length=1, max_length=100)
    amount_minor: int = Field(gt=0)
    currency: str = Field(default="RUB", min_length=3, max_length=3)
    period_type: str = Field(default="monthly", pattern="^(weekly|monthly|quarterly|yearly)$")


class BudgetResponse(BaseModel):
    id: UUID
    workspace_id: UUID
    category_id: Optional[UUID] = None
    name: str
    amount_minor: int
    currency: str
    period_type: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
