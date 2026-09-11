"""SQLAlchemy models for Finance: Accounts, Categories, Immutable Transactions and Budgets."""

from datetime import date, datetime
from typing import List, Optional
from uuid import UUID

from sqlalchemy import BigInteger, Boolean, Date, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import TIMESTAMP, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db.base import Base, TimestampMixin, UUIDMixin, WorkspaceMixin


class Account(Base, UUIDMixin, TimestampMixin, WorkspaceMixin):
    """Financial account (bank, cash, card, crypto) maintaining accurate balances."""

    __tablename__ = "accounts"

    name: Mapped[str] = mapped_column(Text, nullable=False)
    type: Mapped[str] = mapped_column(Text, default="checking", nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="RUB", nullable=False)
    initial_balance_minor: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    current_balance_minor: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


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
    category_id: Mapped[Optional[UUID]] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("categories.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    reversed_transaction_id: Mapped[Optional[UUID]] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("transactions.id", ondelete="RESTRICT"),
        nullable=True,
    )
    amount_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    type: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, default="draft", nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, index=True)
    posted_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)


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
    currency: Mapped[str] = mapped_column(String(3), default="RUB", nullable=False)
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
