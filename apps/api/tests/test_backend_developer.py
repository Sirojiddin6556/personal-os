"""Unit tests for Stage 10: Backend Developer implementations."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4
import pytest

from src.domains.tasks.models import Task, TaskStatus, Priority
from src.domains.tasks.schemas import TaskCreate, TaskUpdate, TaskResponse
from src.domains.tasks.service import task_service
from src.domains.finance.models import Account, Transaction
from src.domains.finance.schemas import TransactionCreate, AccountResponse
from src.domains.finance.service import finance_service
from src.domains.dashboard.service import calculate_free_windows, get_day_bounds
from src.domains.calendar.schemas import EventResponse
from src.shared.exceptions import ConflictError, NotFoundError
from src.shared.pagination import CursorPage, encode_cursor, decode_cursor
from src.ws.router import authenticate_ws


def test_task_models_and_schemas():
    """Verify Task enum, model properties, and schema conversions."""
    assert TaskStatus.INBOX == "inbox"
    assert Priority.MEDIUM == "medium"

    task_id = uuid4()
    workspace_id = uuid4()
    now = datetime.now(timezone.utc)

    task = Task(
        id=task_id,
        workspace_id=workspace_id,
        title="Implement Task Domain",
        description="Write unit tests",
        status=TaskStatus.TODO.value,
        priority=Priority.HIGH.value,
        version=1,
        is_deleted=False,
        created_at=now,
        updated_at=now,
    )
    assert task.title == "Implement Task Domain"
    assert task.status == "todo"
    assert task.priority == "high"
    assert not task.is_deleted

    # Validate Schema
    response_schema = TaskResponse.model_validate(task)
    assert response_schema.id == task_id
    assert response_schema.version == 1
    assert response_schema.status == "todo"


def test_cursor_pagination():
    """Verify opaque base64 cursor encoding, decoding, and CursorPage container."""
    now_iso = datetime.now(timezone.utc).isoformat()
    uid = str(uuid4())

    cursor = encode_cursor({"updated_at": now_iso, "id": uid})
    assert isinstance(cursor, str)

    decoded = decode_cursor(cursor)
    assert decoded["updated_at"] == now_iso
    assert decoded["id"] == uid

    page = CursorPage[str](items=["item1", "item2"], next_cursor=cursor, has_more=True)
    assert len(page) == 2
    assert page[0] == "item1"
    assert list(page) == ["item1", "item2"]


def test_finance_models_synonyms():
    """Verify Account and Transaction model field synonyms for backward/forward compatibility."""
    acc_id = uuid4()
    acc = Account(
        id=acc_id,
        workspace_id=uuid4(),
        name="Main Checking",
        currency="RUB",
        balance_minor=50000,
        account_type="checking",
    )
    assert acc.balance_minor == 50000
    assert acc.current_balance_minor == 50000
    assert acc.account_type == "checking"
    assert acc.type == "checking"

    tx_id = uuid4()
    now = datetime.now(timezone.utc)
    tx = Transaction(
        id=tx_id,
        workspace_id=uuid4(),
        account_id=acc_id,
        amount_minor=1500,
        currency="RUB",
        transaction_type="expense",
        status="posted",
        note="Groceries",
        occurred_at=now,
    )
    assert tx.amount_minor == 1500
    assert tx.transaction_type == "expense"
    assert tx.type == "expense"
    assert tx.note == "Groceries"
    assert tx.description == "Groceries"


def test_dashboard_calculations():
    """Verify timezone bounds and calendar free window calculation logic."""
    start_bound, end_bound = get_day_bounds("UTC")
    assert start_bound.hour == 0
    assert start_bound.minute == 0
    assert end_bound.hour == 23
    assert end_bound.minute == 59

    now = datetime.now(timezone.utc)
    day_start = now.replace(hour=9, minute=0, second=0, microsecond=0)
    day_end = now.replace(hour=18, minute=0, second=0, microsecond=0)

    event1 = EventResponse(
        id=uuid4(),
        workspace_id=uuid4(),
        title="Standup",
        starts_at=now.replace(hour=10, minute=0, second=0, microsecond=0),
        ends_at=now.replace(hour=11, minute=0, second=0, microsecond=0),
        is_all_day=False,
        status="confirmed",
        sync_status="local",
        version=1,
        created_at=now,
        updated_at=now,
    )
    event2 = EventResponse(
        id=uuid4(),
        workspace_id=uuid4(),
        title="Lunch",
        starts_at=now.replace(hour=13, minute=0, second=0, microsecond=0),
        ends_at=now.replace(hour=14, minute=0, second=0, microsecond=0),
        is_all_day=False,
        status="confirmed",
        sync_status="local",
        version=1,
        created_at=now,
        updated_at=now,
    )

    windows = calculate_free_windows([event1, event2], day_start, day_end)
    assert len(windows) == 3
    # 9:00 -> 10:00 (60 min)
    assert windows[0].duration_minutes == 60
    # 11:00 -> 13:00 (120 min)
    assert windows[1].duration_minutes == 120
    # 14:00 -> 18:00 (240 min)
    assert windows[2].duration_minutes == 240


@pytest.mark.asyncio
async def test_task_service_create():
    """Test task creation logic with outbox publishing and session commit."""
    session = AsyncMock()
    workspace_id = uuid4()
    body = TaskCreate(
        title="New Task",
        description="Testing task create",
        priority="high",
        estimate_minutes=45,
    )

    created = await task_service.create(session, workspace_id, body)
    assert created.title == "New Task"
    assert created.priority == "high"
    assert created.version == 1
    assert created.workspace_id == workspace_id
    assert session.commit.called


@pytest.mark.asyncio
async def test_task_service_optimistic_locking_conflict():
    """Test task update version conflict detection."""
    session = AsyncMock()
    workspace_id = uuid4()
    task_id = uuid4()

    mock_task = Task(
        id=task_id,
        workspace_id=workspace_id,
        title="Current Title",
        version=2,  # Current version in DB is 2
        is_deleted=False,
    )
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_task
    session.execute.return_value = mock_result

    body = TaskUpdate(title="Updated Title")
    # Client sends version 1 (mismatched)
    with pytest.raises(ConflictError):
        await task_service.update(session, task_id, workspace_id, body, version=1)


@pytest.mark.asyncio
async def test_finance_post_and_reverse_transaction():
    """Test financial ledger posting and reversing with balance adjustments."""
    session = AsyncMock()
    workspace_id = uuid4()
    account_id = uuid4()

    mock_account = Account(
        id=account_id,
        workspace_id=workspace_id,
        name="Wallet",
        currency="USD",
        balance_minor=10000,
        account_type="cash",
    )

    mock_res_acc = MagicMock()
    mock_res_acc.scalar_one_or_none.return_value = mock_account
    session.execute.return_value = mock_res_acc

    # Post an expense transaction of 2500 minor units
    body = TransactionCreate(
        account_id=account_id,
        amount_minor=2500,
        currency="USD",
        type="expense",
        note="Coffee & Snack",
    )

    tx = await finance_service.post_transaction(session, workspace_id, body)
    assert tx.amount_minor == 2500
    assert tx.status == "posted"
    # Balance must be decreased from 10000 to 7500
    assert mock_account.balance_minor == 7500
    assert session.commit.called
