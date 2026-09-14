"""SQLAlchemy models for Finance: Accounts, Categories, Immutable Transactions and Budgets."""

from datetime import date, datetime
from typing import Optional
from uuid import UUID

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    ForeignKey,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import TIMESTAMP, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, synonym

from src.db.base import Base, TimestampMixin, UUIDMixin, WorkspaceMixin


class Account(Base, UUIDMixin, TimestampMixin, WorkspaceMixin):
    """Financial account (bank, cash, card, crypto) maintaining accurate balances."""

    __tablename__ = "accounts"

    name: Mapped[str] = mapped_column(Text, nullable=False)
    currency: Mapped[str] = mapped_column(Text, nullable=False)  # ISO 4217
    balance_minor: Mapped[int] = mapped_column(
        "current_balance_minor", BigInteger, nullable=False, default=0
    )  # cents
    account_type: Mapped[str] = mapped_column(
        "type", Text, nullable=False, default="checking"
    )  # cash/card/crypto
    initial_balance_minor: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    is_archived: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # Aliases / Synonyms for backward compatibility
    current_balance_minor = synonym("balance_minor")
    type = synonym("account_type")

    __table_args__ = (
        CheckConstraint(
            "type IN ('checking', 'savings', 'credit_card', 'cash', 'investment', 'crypto')",
            name="chk_accounts_type",
        ),
        CheckConstraint("length(currency) = 3", name="chk_accounts_currency"),
    )


class Category(Base, UUIDMixin, TimestampMixin, WorkspaceMixin):
    """Financial classification category."""

    __tablename__ = "categories"

    parent_id: Mapped[Optional[UUID]] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("categories.id", ondelete="CASCADE"),
        nullable=True,
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    icon: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    color: Mapped[str] = mapped_column(String(7), default="#10B981", nullable=False)
    type: Mapped[str] = mapped_column(Text, nullable=False)

    __table_args__ = (
        CheckConstraint("type IN ('income', 'expense', 'transfer')", name="chk_categories_type"),
        CheckConstraint("color ~* '^#[0-9A-Fa-f]{6}$'", name="chk_categories_color"),
    )


class Transaction(Base, UUIDMixin, TimestampMixin, WorkspaceMixin):
    """Immutable financial ledger transaction. Posted entries cannot be updated or deleted."""

    __tablename__ = "transactions"

    account_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("accounts.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    destination_account_id: Mapped[Optional[UUID]] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("accounts.id", ondelete="RESTRICT"),
        nullable=True,
    )
    amount_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)  # NEVER float
    currency: Mapped[str] = mapped_column(Text, nullable=False)
    transaction_type: Mapped[str] = mapped_column("type", Text, nullable=False)  # income/expense/transfer
    status: Mapped[str] = mapped_column(Text, nullable=False, default="draft")
    category_id: Mapped[Optional[UUID]] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("categories.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    occurred_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, index=True)
    note: Mapped[Optional[str]] = mapped_column("description", Text, nullable=True)
    reversal_of_id: Mapped[Optional[UUID]] = mapped_column(
        "reversed_transaction_id",
        PGUUID(as_uuid=True),
        ForeignKey("transactions.id", ondelete="RESTRICT"),
        nullable=True,
    )
    posted_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)

    # Aliases / Synonyms for backward compatibility
    type = synonym("transaction_type")
    description = synonym("note")
    reversed_transaction_id = synonym("reversal_of_id")

    __table_args__ = (
        CheckConstraint(
            "type IN ('income','expense','transfer','reversal','reconciliation')",
            name="chk_transactions_type",
        ),
        CheckConstraint(
            "status IN ('draft','pending_review','posted','reversed','rejected')",
            name="chk_transactions_status",
        ),
    )


class Budget(Base, UUIDMixin, TimestampMixin, WorkspaceMixin):
    """Budget envelope for expenditure control."""

    __tablename__ = "budgets"

    category_id: Mapped[Optional[UUID]] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("categories.id", ondelete="RESTRICT"),
        nullable=True,
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    amount_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="UZS", nullable=False)
    period_type: Mapped[str] = mapped_column(Text, default="monthly", nullable=False)


class BudgetPeriod(Base, UUIDMixin, TimestampMixin, WorkspaceMixin):
    """Time-bounded period tracking cumulative spending against a budget."""

    __tablename__ = "budget_periods"

    budget_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("budgets.id", ondelete="CASCADE"),
        nullable=False,
    )
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    spent_minor: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
