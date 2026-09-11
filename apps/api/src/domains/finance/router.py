"""Finance API endpoints for Accounts, Categories, Immutable Transactions and Budgets."""

from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.domains.finance.schemas import (
    AccountCreate,
    AccountResponse,
    AccountUpdate,
    BudgetCreate,
    BudgetResponse,
    CategoryCreate,
    CategoryResponse,
    TransactionCreate,
    TransactionResponse,
    TransactionUpdate,
)
from src.domains.finance.service import finance_service
from src.domains.identity.models import Workspace
from src.shared.deps import get_db_session, get_workspace

router = APIRouter(prefix="/finance", tags=["finance"])


@router.post("/accounts", response_model=AccountResponse, status_code=status.HTTP_201_CREATED)
async def create_account(
    body: AccountCreate,
    session: AsyncSession = Depends(get_db_session),
    workspace: Workspace = Depends(get_workspace),
) -> AccountResponse:
    acc = await finance_service.create_account(session, workspace.id, body)
    return AccountResponse.model_validate(acc)


@router.get("/accounts", response_model=List[AccountResponse])
async def list_accounts(
    session: AsyncSession = Depends(get_db_session),
    workspace: Workspace = Depends(get_workspace),
) -> List[AccountResponse]:
    accounts = await finance_service.list_accounts(session, workspace.id)
    return [AccountResponse.model_validate(a) for a in accounts]


@router.delete("/accounts/{account_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_account(
    account_id: UUID,
    session: AsyncSession = Depends(get_db_session),
    workspace: Workspace = Depends(get_workspace),
) -> None:
    await finance_service.delete_account(session, workspace.id, account_id)


@router.patch("/accounts/{account_id}", response_model=AccountResponse)
async def update_account(
    account_id: UUID,
    body: AccountUpdate,
    session: AsyncSession = Depends(get_db_session),
    workspace: Workspace = Depends(get_workspace),
) -> AccountResponse:
    acc = await finance_service.update_account(session, workspace.id, account_id, body)
    return AccountResponse.model_validate(acc)


@router.post("/categories", response_model=CategoryResponse, status_code=status.HTTP_201_CREATED)
async def create_category(
    body: CategoryCreate,
    session: AsyncSession = Depends(get_db_session),
    workspace: Workspace = Depends(get_workspace),
) -> CategoryResponse:
    cat = await finance_service.create_category(session, workspace.id, body)
    return CategoryResponse.model_validate(cat)


@router.get("/categories", response_model=List[CategoryResponse])
async def list_categories(
    session: AsyncSession = Depends(get_db_session),
    workspace: Workspace = Depends(get_workspace),
) -> List[CategoryResponse]:
    categories = await finance_service.list_categories(session, workspace.id)
    return [CategoryResponse.model_validate(c) for c in categories]


@router.post("/transactions", response_model=TransactionResponse, status_code=status.HTTP_201_CREATED)
async def post_transaction(
    body: TransactionCreate,
    session: AsyncSession = Depends(get_db_session),
    workspace: Workspace = Depends(get_workspace),
) -> TransactionResponse:
    tx = await finance_service.post_transaction(session, workspace.id, body)
    return TransactionResponse.model_validate(tx)


@router.get("/transactions", response_model=List[TransactionResponse])
async def list_transactions(
    account_id: Optional[UUID] = Query(None),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_db_session),
    workspace: Workspace = Depends(get_workspace),
) -> List[TransactionResponse]:
    transactions = await finance_service.list_transactions(session, workspace.id, account_id, limit, offset)
    return [TransactionResponse.model_validate(t) for t in transactions]


@router.post("/transactions/{transaction_id}/reverse", response_model=TransactionResponse, status_code=status.HTTP_201_CREATED)
async def reverse_transaction(
    transaction_id: UUID,
    reason: Optional[str] = Query(None),
    session: AsyncSession = Depends(get_db_session),
    workspace: Workspace = Depends(get_workspace),
) -> TransactionResponse:
    reversal = await finance_service.reverse_transaction(session, workspace.id, transaction_id, reason)
    return TransactionResponse.model_validate(reversal)


@router.patch("/transactions/{transaction_id}", response_model=TransactionResponse)
async def update_transaction(
    transaction_id: UUID,
    body: TransactionUpdate,
    session: AsyncSession = Depends(get_db_session),
    workspace: Workspace = Depends(get_workspace),
) -> TransactionResponse:
    tx = await finance_service.update_transaction(session, workspace.id, transaction_id, body)
    return TransactionResponse.model_validate(tx)


@router.post("/budgets", response_model=BudgetResponse, status_code=status.HTTP_201_CREATED)
async def create_budget(
    body: BudgetCreate,
    session: AsyncSession = Depends(get_db_session),
    workspace: Workspace = Depends(get_workspace),
) -> BudgetResponse:
    b = await finance_service.create_budget(session, workspace.id, body)
    return BudgetResponse.model_validate(b)


@router.get("/budgets", response_model=List[BudgetResponse])
async def list_budgets(
    session: AsyncSession = Depends(get_db_session),
    workspace: Workspace = Depends(get_workspace),
) -> List[BudgetResponse]:
    budgets = await finance_service.list_budgets(session, workspace.id)
    return [BudgetResponse.model_validate(b) for b in budgets]
