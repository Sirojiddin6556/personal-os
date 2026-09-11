"""Finance service implementing an immutable double-entry style ledger."""

from datetime import datetime, timezone
from typing import List, Optional
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domains.finance.models import Account, Budget, Category, Transaction
from src.domains.finance.schemas import (
    AccountCreate,
    BudgetCreate,
    CategoryCreate,
    TransactionCreate,
    TransactionUpdate,
)
from src.shared.exceptions import ConflictError, NotFoundError, ValidationDomainError
from src.shared.idempotency import idempotency_service
from src.shared.outbox import publish_event


class FinanceService:
    """Operations for Accounts, Categories, and Immutable Ledger Transactions."""

    async def create_account(
        self, session: AsyncSession, workspace_id: UUID, body: AccountCreate
    ) -> Account:
        acc = Account(
            id=uuid4(),
            workspace_id=workspace_id,
            name=body.name,
            account_type=body.type,
            currency=body.currency.upper(),
            initial_balance_minor=body.initial_balance_minor,
            balance_minor=body.initial_balance_minor,
            is_archived=False,
        )
        session.add(acc)
        await session.commit()
        await session.refresh(acc)
        return acc

    async def list_accounts(self, session: AsyncSession, workspace_id: UUID) -> List[Account]:
        stmt = select(Account).where(
            Account.workspace_id == workspace_id,
            Account.is_archived.is_(False),
        )
        res = await session.execute(stmt)
        return list(res.scalars().all())

    async def create_category(
        self, session: AsyncSession, workspace_id: UUID, body: CategoryCreate
    ) -> Category:
        cat = Category(
            id=uuid4(),
            workspace_id=workspace_id,
            parent_id=body.parent_id,
            name=body.name,
            icon=body.icon,
            color=body.color,
            type=body.type,
        )
        session.add(cat)
        await session.commit()
        await session.refresh(cat)
        return cat

    async def list_categories(self, session: AsyncSession, workspace_id: UUID) -> List[Category]:
        stmt = select(Category).where(
            Category.workspace_id == workspace_id
        ).order_by(Category.name.asc())
        res = await session.execute(stmt)
        return list(res.scalars().all())

    async def post_transaction(
        self,
        session: AsyncSession,
        workspace_id: UUID,
        body: TransactionCreate,
        idempotency_key: Optional[str] = None,
    ) -> Transaction:
        """Create and immediately post an immutable transaction, updating account balance(s)."""
        if idempotency_key:
            cached = await idempotency_service.get(workspace_id, idempotency_key)
            if cached:
                status_code, body_dict = cached
                # Fetch stored transaction
                tx_id = UUID(body_dict["id"])
                existing = await session.get(Transaction, tx_id)
                if existing:
                    return existing

        # 1. Атомарно SELECT FOR UPDATE для исходного счета
        stmt = (
            select(Account)
            .where(Account.id == body.account_id, Account.workspace_id == workspace_id)
            .with_for_update()
        )
        res = await session.execute(stmt)
        source_account = res.scalar_one_or_none()
        if not source_account:
            raise NotFoundError(resource="Account", identifier=body.account_id)

        tx_type = body.transaction_type or body.type or "expense"
        dest_account = None

        if tx_type == "transfer":
            if not body.destination_account_id:
                raise ValidationDomainError(
                    title="Invalid Transfer",
                    detail="destination_account_id is required for transfer transactions.",
                )
            stmt_dest = (
                select(Account)
                .where(
                    Account.id == body.destination_account_id,
                    Account.workspace_id == workspace_id,
                )
                .with_for_update()
            )
            res_dest = await session.execute(stmt_dest)
            dest_account = res_dest.scalar_one_or_none()
            if not dest_account:
                raise NotFoundError(
                    resource="Destination Account", identifier=body.destination_account_id
                )

        now = datetime.now(timezone.utc)
        occurred = body.occurred_at or now

        # 2. Обновить Account.balance_minor (атомарно)
        if tx_type == "expense":
            source_account.balance_minor -= body.amount_minor
        elif tx_type == "income":
            source_account.balance_minor += body.amount_minor
        elif tx_type == "transfer" and dest_account:
            source_account.balance_minor -= body.amount_minor
            dest_account.balance_minor += body.amount_minor

        # 3. Создать Transaction(status='posted')
        tx = Transaction(
            id=uuid4(),
            workspace_id=workspace_id,
            account_id=body.account_id,
            destination_account_id=body.destination_account_id,
            category_id=body.category_id,
            reversal_of_id=None,
            amount_minor=body.amount_minor,
            currency=body.currency.upper(),
            transaction_type=tx_type,
            status="posted",
            note=body.note or body.description,
            occurred_at=occurred,
            posted_at=now,
            created_at=now,
            updated_at=now,
        )
        session.add(tx)

        # 4. publish_event('finance.transaction.posted.v1', ...)
        await publish_event(
            session=session,
            event_type="finance.transaction.posted.v1",
            aggregate_type="transaction",
            aggregate_id=tx.id,
            workspace_id=workspace_id,
            data={
                "transaction_id": str(tx.id),
                "account_id": str(tx.account_id),
                "amount_minor": tx.amount_minor,
                "type": tx.transaction_type,
                "status": tx.status,
            },
        )

        # 5. commit()
        await session.commit()
        await session.refresh(tx)

        if idempotency_key:
            await idempotency_service.set(
                workspace_id=workspace_id,
                idempotency_key=idempotency_key,
                status_code=201,
                body={
                    "id": str(tx.id),
                    "amount_minor": tx.amount_minor,
                    "status": tx.status,
                },
                ttl_seconds=86400,
            )

        return tx

    async def reverse_transaction(
        self,
        session: AsyncSession,
        workspace_id: UUID,
        transaction_id: UUID,
        reason: Optional[str] = None,
    ) -> Transaction:
        """Create an offsetting reversal transaction. The original posted transaction is immutable."""
        # 1. Проверить status == 'posted' (иначе ошибка)
        stmt = (
            select(Transaction)
            .where(
                Transaction.id == transaction_id,
                Transaction.workspace_id == workspace_id,
            )
            .with_for_update()
        )
        res = await session.execute(stmt)
        orig = res.scalar_one_or_none()
        if not orig:
            raise NotFoundError(resource="Transaction", identifier=transaction_id)

        if orig.status != "posted":
            raise ConflictError(
                title="Invalid Transaction State",
                detail=f"Only posted transactions can be reversed. Current status is '{orig.status}'.",
            )

        # 2. Обновить баланс обратно (SELECT FOR UPDATE)
        stmt_acc = (
            select(Account)
            .where(Account.id == orig.account_id)
            .with_for_update()
        )
        res_acc = await session.execute(stmt_acc)
        source_account = res_acc.scalar_one_or_none()
        if not source_account:
            raise NotFoundError(resource="Account", identifier=orig.account_id)

        now = datetime.now(timezone.utc)

        if orig.transaction_type == "expense":
            source_account.balance_minor += orig.amount_minor
        elif orig.transaction_type == "income":
            source_account.balance_minor -= orig.amount_minor
        elif orig.transaction_type == "transfer":
            stmt_dest = (
                select(Account)
                .where(Account.id == orig.destination_account_id)
                .with_for_update()
            )
            res_dest = await session.execute(stmt_dest)
            dest_acc = res_dest.scalar_one_or_none()
            source_account.balance_minor += orig.amount_minor
            if dest_acc:
                dest_acc.balance_minor -= orig.amount_minor

        orig.status = "reversed"

        # 3. Создать reversal transaction (reversal_of_id)
        reversal_tx = Transaction(
            id=uuid4(),
            workspace_id=workspace_id,
            account_id=orig.account_id,
            destination_account_id=orig.destination_account_id,
            category_id=orig.category_id,
            reversal_of_id=orig.id,
            amount_minor=orig.amount_minor,
            currency=orig.currency,
            transaction_type="reversal",
            status="posted",
            note=f"Reversal of {orig.id}: {reason or 'Requested reversal'}",
            occurred_at=now,
            posted_at=now,
        )
        session.add(reversal_tx)

        await publish_event(
            session=session,
            event_type="finance.transaction.reversed.v1",
            aggregate_type="transaction",
            aggregate_id=orig.id,
            workspace_id=workspace_id,
            data={
                "reversed_id": str(orig.id),
                "reversal_id": str(reversal_tx.id),
            },
        )

        await session.commit()
        await session.refresh(reversal_tx)
        return reversal_tx

    async def list_transactions(
        self,
        session: AsyncSession,
        workspace_id: UUID,
        account_id: Optional[UUID] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[Transaction]:
        stmt = select(Transaction).where(Transaction.workspace_id == workspace_id)
        if account_id:
            stmt = stmt.where(Transaction.account_id == account_id)
        stmt = stmt.order_by(Transaction.occurred_at.desc()).limit(limit).offset(offset)
        res = await session.execute(stmt)
        return list(res.scalars().all())

    async def create_budget(
        self, session: AsyncSession, workspace_id: UUID, body: BudgetCreate
    ) -> Budget:
        budget = Budget(
            id=uuid4(),
            workspace_id=workspace_id,
            category_id=body.category_id,
            name=body.name,
            amount_minor=body.amount_minor,
            currency=body.currency.upper(),
            period_type=body.period_type,
        )
        session.add(budget)
        await session.commit()
        await session.refresh(budget)
        return budget

    async def list_budgets(self, session: AsyncSession, workspace_id: UUID) -> List[Budget]:
        stmt = select(Budget).where(Budget.workspace_id == workspace_id).order_by(Budget.name.asc())
        res = await session.execute(stmt)
        return list(res.scalars().all())

    async def update_transaction(
        self,
        session: AsyncSession,
        workspace_id: UUID,
        transaction_id: UUID,
        body: TransactionUpdate,
    ) -> Transaction:
        """Update draft transaction or reject mutation for posted/reversed transactions."""
        stmt = select(Transaction).where(
            Transaction.id == transaction_id,
            Transaction.workspace_id == workspace_id,
        )
        res = await session.execute(stmt)
        tx = res.scalar_one_or_none()
        if not tx:
            raise NotFoundError(resource="Transaction", identifier=transaction_id)

        if tx.status in ("posted", "reversed"):
            raise ConflictError(
                title="Immutable Transaction",
                detail=f"Cannot modify a {tx.status} transaction (id={transaction_id}). Create a reversal instead.",
            )

        if body.note or body.description:
            tx.note = body.note or body.description
        if body.category_id is not None:
            tx.category_id = body.category_id

        await session.commit()
        await session.refresh(tx)
        return tx


finance_service = FinanceService()
