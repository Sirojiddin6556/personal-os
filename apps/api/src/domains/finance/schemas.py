"""Pydantic v2 schemas for the Finance domain."""

from datetime import datetime
from typing import Optional, Union
from uuid import UUID

from pydantic import BaseModel, Field, model_validator


class AccountCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    type: str = Field(default="checking", pattern="^(checking|savings|credit_card|cash|investment|crypto)$")
    currency: str = Field(default="UZS", min_length=3, max_length=3)
    initial_balance_minor: int = 0


class AccountUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    type: Optional[str] = Field(None, pattern="^(checking|savings|credit_card|cash|investment|crypto)$")
    currency: Optional[str] = Field(None, min_length=3, max_length=3)
    balance_minor: Optional[int] = None
    is_archived: Optional[bool] = None


class AccountResponse(BaseModel):
    id: UUID
    workspace_id: UUID
    name: str
    type: str
    currency: str
    initial_balance_minor: int
    current_balance_minor: int
    balance_minor: Optional[int] = None
    account_type: Optional[str] = None
    is_archived: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

    @model_validator(mode="after")
    def populate_aliases(self):
        if self.balance_minor is None:
            self.balance_minor = self.current_balance_minor
        if self.account_type is None:
            self.account_type = self.type
        return self


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
    category_id: Optional[Union[UUID, str]] = None
    category_name: Optional[str] = None
    amount_minor: int = Field(gt=0, description="Amount in minor units (cents/kopecks/tiyin)")
    currency: str = Field(default="UZS", min_length=3, max_length=3)
    type: Optional[str] = None
    transaction_type: Optional[str] = None
    description: Optional[str] = None
    note: Optional[str] = None
    transaction_date: Optional[Union[datetime, str]] = None
    occurred_at: Optional[Union[datetime, str]] = None

    @model_validator(mode="after")
    def normalize_and_validate(self):
        tx_type = self.transaction_type or self.type or "expense"
        self.type = tx_type
        self.transaction_type = tx_type

        tx_desc = self.note or self.description
        self.description = tx_desc
        self.note = tx_desc

        if not self.occurred_at and self.transaction_date:
            self.occurred_at = self.transaction_date

        if self.category_id:
            if isinstance(self.category_id, str):
                try:
                    self.category_id = UUID(self.category_id)
                except ValueError:
                    if not self.category_name:
                        self.category_name = str(self.category_id)
                    self.category_id = None

        if self.type == "transfer":
            if not self.destination_account_id:
                raise ValueError("destination_account_id is required for transfer transactions")
            if self.account_id == self.destination_account_id:
                raise ValueError("Source and destination accounts must be different")
        return self


class TransactionUpdate(BaseModel):
    note: Optional[str] = None
    description: Optional[str] = None
    category_id: Optional[UUID] = None


class TransactionResponse(BaseModel):
    id: UUID
    workspace_id: UUID
    account_id: UUID
    account_name: Optional[str] = None
    destination_account_id: Optional[UUID] = None
    category_id: Optional[UUID] = None
    category: Optional[str] = None
    category_name: Optional[str] = None
    reversed_transaction_id: Optional[UUID] = None
    reversal_of_id: Optional[UUID] = None
    amount_minor: int
    amount: Optional[float] = None
    currency: str
    type: str
    transaction_type: Optional[str] = None
    status: str
    description: Optional[str] = None
    note: Optional[str] = None
    occurred_at: datetime
    posted_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

    @model_validator(mode="after")
    def populate_aliases(self):
        if self.transaction_type is None:
            self.transaction_type = self.type
        if self.note is None:
            self.note = self.description
        if self.reversal_of_id is None:
            self.reversal_of_id = self.reversed_transaction_id
        if self.amount is None:
            self.amount = self.amount_minor / 100
        if self.category is None:
            self.category = self.category_name
        return self


class BudgetCreate(BaseModel):
    category_id: Optional[UUID] = None
    name: str = Field(min_length=1, max_length=100)
    amount_minor: int = Field(gt=0)
    currency: str = Field(default="UZS", min_length=3, max_length=3)
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
