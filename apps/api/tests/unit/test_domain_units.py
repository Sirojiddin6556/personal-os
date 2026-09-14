"""Unit tests for domain invariants, state machine transitions, and edge cases.

This suite covers:
1. Calendar free window calculations and date/time timezone bounds (Dashboard domain)
2. Task state machine transitions, optimistic locking, and model invariants (Tasks domain)
3. Financial minor units accounting, immutable ledger, and reversal balancing (Finance domain)
4. AI Tool Gateway risk tier governance, SQL injection filtering, and blocked destructive calls
5. Prompt injection defense XML wrapping and cursor pagination invariants
"""

from datetime import datetime, time, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4
import pytest
from pydantic import ValidationError

from src.domains.ai_advisor.llm_client import (
    extract_untrusted_data,
    wrap_untrusted_data,
)
from src.domains.ai_advisor.tool_gateway import (
    RISK_TIER_INT_MAP,
    RiskTier,
    ToolGateway,
)
from src.domains.calendar.schemas import EventResponse
from src.domains.dashboard.service import (
    calculate_free_windows,
    get_day_bounds,
)
from src.domains.finance.models import Account, Transaction
from src.domains.finance.schemas import (
    AccountResponse,
    TransactionCreate,
    TransactionResponse,
)
from src.domains.finance.service import finance_service
from src.domains.tasks.models import Priority, Task, TaskPriority, TaskStatus
from src.domains.tasks.schemas import (
    KanbanBoardResponse,
    KanbanColumnResponse,
    TaskCreate,
    TaskResponse,
    TaskUpdate,
)
from src.domains.tasks.service import task_service
from src.shared.exceptions import (
    ConflictError,
    ForbiddenError,
    NotFoundError,
    ValidationDomainError,
)
from src.shared.pagination import CursorPage, decode_cursor, encode_cursor


def create_mock_session():
    s = AsyncMock()
    s.add = MagicMock()
    return s


# =============================================================================
# 1. CALENDAR FREE SLOTS & DATE/TIME TIMEZONE TESTS
# =============================================================================

def test_get_day_bounds_utc_and_timezones():
    """Verify get_day_bounds returns midnight start and end for various timezones."""
    for tz_name in ["UTC", "Europe/Moscow", "America/New_York", "Asia/Tokyo"]:
        start, end = get_day_bounds(tz_name)
        assert start.hour == 0
        assert start.minute == 0
        assert start.second == 0
        assert end.hour == 23
        assert end.minute == 59
        assert end.second == 59
        assert start < end


def test_get_day_bounds_invalid_timezone_fallback_to_utc():
    """Verify fallback to UTC when timezone string is invalid."""
    start, end = get_day_bounds("Invalid/Non_Existent_Timezone")
    assert start.tzinfo == timezone.utc
    assert end.tzinfo == timezone.utc
    assert start.hour == 0
    assert end.hour == 23


def test_calculate_free_windows_empty_calendar():
    """Verify when no events exist, the entire day is a single free window."""
    now = datetime.now(timezone.utc)
    day_start = now.replace(hour=9, minute=0, second=0, microsecond=0)
    day_end = now.replace(hour=18, minute=0, second=0, microsecond=0)

    windows = calculate_free_windows([], day_start, day_end)
    assert len(windows) == 1
    assert windows[0].start == day_start
    assert windows[0].end == day_end
    assert windows[0].duration_minutes == 9 * 60  # 540 minutes


def test_calculate_free_windows_back_to_back_events():
    """Verify adjacent events without gaps do not create empty free windows."""
    now = datetime.now(timezone.utc)
    day_start = now.replace(hour=9, minute=0, second=0, microsecond=0)
    day_end = now.replace(hour=12, minute=0, second=0, microsecond=0)

    ev1 = EventResponse(
        id=uuid4(),
        workspace_id=uuid4(),
        title="Event 1",
        starts_at=now.replace(hour=9, minute=0, second=0, microsecond=0),
        ends_at=now.replace(hour=10, minute=30, second=0, microsecond=0),
        is_all_day=False,
        status="confirmed",
        sync_status="local",
        version=1,
        created_at=now,
        updated_at=now,
    )
    ev2 = EventResponse(
        id=uuid4(),
        workspace_id=uuid4(),
        title="Event 2",
        starts_at=now.replace(hour=10, minute=30, second=0, microsecond=0),
        ends_at=now.replace(hour=12, minute=0, second=0, microsecond=0),
        is_all_day=False,
        status="confirmed",
        sync_status="local",
        version=1,
        created_at=now,
        updated_at=now,
    )

    windows = calculate_free_windows([ev1, ev2], day_start, day_end)
    assert len(windows) == 0


def test_calculate_free_windows_filters_slots_less_than_15_min():
    """Verify slots shorter than 15 minutes are discarded per business rule."""
    now = datetime.now(timezone.utc)
    day_start = now.replace(hour=10, minute=0, second=0, microsecond=0)
    day_end = now.replace(hour=11, minute=0, second=0, microsecond=0)

    # Gap of 10 minutes (10:20 -> 10:30)
    ev1 = EventResponse(
        id=uuid4(),
        workspace_id=uuid4(),
        title="Event 1",
        starts_at=now.replace(hour=10, minute=0, second=0, microsecond=0),
        ends_at=now.replace(hour=10, minute=20, second=0, microsecond=0),
        is_all_day=False,
        status="confirmed",
        sync_status="local",
        version=1,
        created_at=now,
        updated_at=now,
    )
    ev2 = EventResponse(
        id=uuid4(),
        workspace_id=uuid4(),
        title="Event 2",
        starts_at=now.replace(hour=10, minute=30, second=0, microsecond=0),
        ends_at=now.replace(hour=11, minute=0, second=0, microsecond=0),
        is_all_day=False,
        status="confirmed",
        sync_status="local",
        version=1,
        created_at=now,
        updated_at=now,
    )

    windows = calculate_free_windows([ev1, ev2], day_start, day_end)
    assert len(windows) == 0


def test_calculate_free_windows_includes_exact_15_min_slot():
    """Verify a slot of exactly 15 minutes is included."""
    now = datetime.now(timezone.utc)
    day_start = now.replace(hour=10, minute=0, second=0, microsecond=0)
    day_end = now.replace(hour=11, minute=0, second=0, microsecond=0)

    # Gap of exactly 15 minutes: 10:15 -> 10:30
    ev1 = EventResponse(
        id=uuid4(),
        workspace_id=uuid4(),
        title="Event 1",
        starts_at=now.replace(hour=10, minute=0, second=0, microsecond=0),
        ends_at=now.replace(hour=10, minute=15, second=0, microsecond=0),
        is_all_day=False,
        status="confirmed",
        sync_status="local",
        version=1,
        created_at=now,
        updated_at=now,
    )
    ev2 = EventResponse(
        id=uuid4(),
        workspace_id=uuid4(),
        title="Event 2",
        starts_at=now.replace(hour=10, minute=30, second=0, microsecond=0),
        ends_at=now.replace(hour=11, minute=0, second=0, microsecond=0),
        is_all_day=False,
        status="confirmed",
        sync_status="local",
        version=1,
        created_at=now,
        updated_at=now,
    )

    windows = calculate_free_windows([ev1, ev2], day_start, day_end)
    assert len(windows) == 1
    assert windows[0].duration_minutes == 15


def test_calculate_free_windows_overlapping_events():
    """Verify overlapping events are merged cleanly without negative or bogus windows."""
    now = datetime.now(timezone.utc)
    day_start = now.replace(hour=9, minute=0, second=0, microsecond=0)
    day_end = now.replace(hour=12, minute=0, second=0, microsecond=0)

    # ev1: 9:30 -> 10:30, ev2: 10:00 -> 11:00 (overlapping)
    ev1 = EventResponse(
        id=uuid4(),
        workspace_id=uuid4(),
        title="Meeting A",
        starts_at=now.replace(hour=9, minute=30, second=0, microsecond=0),
        ends_at=now.replace(hour=10, minute=30, second=0, microsecond=0),
        is_all_day=False,
        status="confirmed",
        sync_status="local",
        version=1,
        created_at=now,
        updated_at=now,
    )
    ev2 = EventResponse(
        id=uuid4(),
        workspace_id=uuid4(),
        title="Meeting B",
        starts_at=now.replace(hour=10, minute=0, second=0, microsecond=0),
        ends_at=now.replace(hour=11, minute=0, second=0, microsecond=0),
        is_all_day=False,
        status="confirmed",
        sync_status="local",
        version=1,
        created_at=now,
        updated_at=now,
    )

    windows = calculate_free_windows([ev1, ev2], day_start, day_end)
    # Expected: 9:00 -> 9:30 (30m) and 11:00 -> 12:00 (60m)
    assert len(windows) == 2
    assert windows[0].duration_minutes == 30
    assert windows[1].duration_minutes == 60


# =============================================================================
# 2. TASK DOMAIN INVARIANTS & STATE MACHINE TESTS
# =============================================================================

def test_task_enums_and_aliases():
    """Verify TaskStatus and Priority enum constants."""
    assert TaskStatus.INBOX.value == "inbox"
    assert TaskStatus.TODO.value == "todo"
    assert TaskStatus.SCHEDULED.value == "scheduled"
    assert TaskStatus.IN_PROGRESS.value == "in_progress"
    assert TaskStatus.WAITING.value == "waiting"
    assert TaskStatus.DONE.value == "done"
    assert TaskStatus.CANCELLED.value == "cancelled"
    assert TaskStatus.ARCHIVED.value == "archived"

    assert Priority.LOW.value == "low"
    assert Priority.MEDIUM.value == "medium"
    assert Priority.HIGH.value == "high"
    assert Priority.CRITICAL.value == "critical"
    assert TaskPriority is Priority


def test_task_create_pydantic_schema_validation():
    """Verify TaskCreate schema validation rules."""
    # Valid task creation
    task_in = TaskCreate(
        title="Valid Task",
        priority="high",
        estimate_minutes=60,
    )
    assert task_in.title == "Valid Task"
    assert task_in.status == "inbox"

    # Title min_length=1 constraint
    with pytest.raises(ValidationError):
        TaskCreate(title="")

    # Title max_length=500 constraint
    with pytest.raises(ValidationError):
        TaskCreate(title="A" * 501)

    # estimate_minutes range [1, 1440]
    with pytest.raises(ValidationError):
        TaskCreate(title="Too short estimate", estimate_minutes=0)

    with pytest.raises(ValidationError):
        TaskCreate(title="Too long estimate", estimate_minutes=1441)


def test_kanban_schemas_serialization():
    """Verify Kanban column and board response schemas."""
    now = datetime.now(timezone.utc)
    t_id = uuid4()
    ws_id = uuid4()

    task_resp = TaskResponse(
        id=t_id,
        workspace_id=ws_id,
        title="Kanban Item",
        status="todo",
        priority="medium",
        version=1,
        is_deleted=False,
        created_at=now,
        updated_at=now,
    )

    col = KanbanColumnResponse(status="todo", count=1, tasks=[task_resp])
    assert col.status == "todo"
    assert col.count == 1
    assert len(col.tasks) == 1

    board = KanbanBoardResponse(columns={"todo": col})
    assert "todo" in board.columns
    assert board.columns["todo"].tasks[0].id == t_id


@pytest.mark.asyncio
async def test_task_state_machine_transition_to_done_sets_completed_at():
    """State machine invariant: Moving task to DONE sets completed_at to now."""
    session = create_mock_session()
    ws_id = uuid4()
    task_id = uuid4()

    mock_task = Task(
        id=task_id,
        workspace_id=ws_id,
        title="Complete me",
        status="in_progress",
        priority="medium",
        version=1,
        is_deleted=False,
        completed_at=None,
        cancelled_at=None,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )

    mock_res = MagicMock()
    mock_res.scalar_one_or_none.return_value = mock_task
    session.execute.return_value = mock_res

    updated = await task_service.update(
        session=session,
        task_id=task_id,
        workspace_id=ws_id,
        body=TaskUpdate(status="done"),
        version=1,
    )

    assert mock_task.status == "done"
    assert mock_task.completed_at is not None
    assert mock_task.cancelled_at is None
    assert mock_task.version == 2
    assert session.commit.called


@pytest.mark.asyncio
async def test_task_state_machine_reopening_done_task_clears_completed_at():
    """State machine invariant: Reopening DONE task (e.g. to todo) clears completed_at."""
    session = create_mock_session()
    ws_id = uuid4()
    task_id = uuid4()

    now = datetime.now(timezone.utc)
    mock_task = Task(
        id=task_id,
        workspace_id=ws_id,
        title="Reopen me",
        status="done",
        priority="medium",
        version=3,
        is_deleted=False,
        completed_at=now,
        cancelled_at=None,
        created_at=now,
        updated_at=now,
    )

    mock_res = MagicMock()
    mock_res.scalar_one_or_none.return_value = mock_task
    session.execute.return_value = mock_res

    await task_service.update(
        session=session,
        task_id=task_id,
        workspace_id=ws_id,
        body=TaskUpdate(status="todo"),
        version=3,
    )

    assert mock_task.status == "todo"
    assert mock_task.completed_at is None
    assert mock_task.version == 4


@pytest.mark.asyncio
async def test_task_state_machine_transition_to_cancelled_sets_cancelled_at():
    """State machine invariant: Moving task to CANCELLED sets cancelled_at."""
    session = create_mock_session()
    ws_id = uuid4()
    task_id = uuid4()

    mock_task = Task(
        id=task_id,
        workspace_id=ws_id,
        title="Cancel me",
        status="todo",
        priority="medium",
        version=1,
        is_deleted=False,
        completed_at=None,
        cancelled_at=None,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )

    mock_res = MagicMock()
    mock_res.scalar_one_or_none.return_value = mock_task
    session.execute.return_value = mock_res

    await task_service.update(
        session=session,
        task_id=task_id,
        workspace_id=ws_id,
        body=TaskUpdate(status="cancelled"),
        version=1,
    )

    assert mock_task.status == "cancelled"
    assert mock_task.cancelled_at is not None
    assert mock_task.completed_at is None
    assert mock_task.version == 2


@pytest.mark.asyncio
async def test_task_service_soft_delete_preserves_audit():
    """Soft-delete invariant: task is flagged is_deleted=True with version increment."""
    session = create_mock_session()
    ws_id = uuid4()
    task_id = uuid4()

    mock_task = Task(
        id=task_id,
        workspace_id=ws_id,
        title="Delete me",
        status="todo",
        version=1,
        is_deleted=False,
    )

    mock_res = MagicMock()
    mock_res.scalar_one_or_none.return_value = mock_task
    session.execute.return_value = mock_res

    await task_service.delete(
        session=session,
        task_id=task_id,
        workspace_id=ws_id,
        version=1,
    )

    assert mock_task.is_deleted is True
    assert mock_task.version == 2
    assert session.commit.called


# =============================================================================
# 3. FINANCE DOMAIN LEDGER & MINOR UNITS TESTS
# =============================================================================

def test_account_model_invariants_and_synonyms():
    """Verify Account model minor units balance and synonym mapping."""
    acc_id = uuid4()
    ws_id = uuid4()
    acc = Account(
        id=acc_id,
        workspace_id=ws_id,
        name="Crypto Vault",
        currency="USD",
        balance_minor=1500000,  # $15,000.00
        account_type="crypto",
    )
    assert acc.balance_minor == 1500000
    assert acc.current_balance_minor == 1500000
    assert acc.account_type == "crypto"
    assert acc.type == "crypto"
    assert not acc.is_archived


def test_transaction_model_invariants_and_synonyms():
    """Verify Transaction model minor units and synonyms."""
    tx_id = uuid4()
    acc_id = uuid4()
    now = datetime.now(timezone.utc)

    tx = Transaction(
        id=tx_id,
        workspace_id=uuid4(),
        account_id=acc_id,
        amount_minor=5050,  # 50.50
        currency="RUB",
        transaction_type="expense",
        status="posted",
        note="Groceries lunch",
        occurred_at=now,
    )
    assert tx.amount_minor == 5050
    assert tx.transaction_type == "expense"
    assert tx.type == "expense"
    assert tx.note == "Groceries lunch"
    assert tx.description == "Groceries lunch"
    assert tx.status == "posted"


@pytest.mark.asyncio
async def test_finance_post_income_increases_balance():
    """Posting income increases account.balance_minor by amount_minor."""
    session = create_mock_session()
    ws_id = uuid4()
    acc_id = uuid4()

    mock_account = Account(
        id=acc_id,
        workspace_id=ws_id,
        name="Main Account",
        currency="RUB",
        balance_minor=10000,  # 100.00
        account_type="checking",
    )
    mock_res = MagicMock()
    mock_res.scalar_one_or_none.return_value = mock_account
    session.execute.return_value = mock_res

    body = TransactionCreate(
        account_id=acc_id,
        amount_minor=5000,  # 50.00
        currency="RUB",
        type="income",
        note="Bonus",
    )

    tx = await finance_service.post_transaction(session, ws_id, body)
    assert tx.status == "posted"
    assert tx.amount_minor == 5000
    assert mock_account.balance_minor == 15000  # 100.00 + 50.00 = 150.00
    assert session.commit.called


@pytest.mark.asyncio
async def test_finance_post_transfer_updates_both_accounts():
    """Posting transfer decreases source and increases destination account balance."""
    session = create_mock_session()
    ws_id = uuid4()
    src_id = uuid4()
    dest_id = uuid4()

    src_acc = Account(
        id=src_id,
        workspace_id=ws_id,
        name="Source Bank",
        currency="USD",
        balance_minor=20000,  # $200.00
        account_type="checking",
    )
    dest_acc = Account(
        id=dest_id,
        workspace_id=ws_id,
        name="Dest Savings",
        currency="USD",
        balance_minor=5000,  # $50.00
        account_type="savings",
    )

    # First execute call -> src_acc, second -> dest_acc
    res_src = MagicMock()
    res_src.scalar_one_or_none.return_value = src_acc
    res_dest = MagicMock()
    res_dest.scalar_one_or_none.return_value = dest_acc

    session.execute.side_effect = [res_src, res_dest]

    body = TransactionCreate(
        account_id=src_id,
        destination_account_id=dest_id,
        amount_minor=7500,  # $75.00
        currency="USD",
        type="transfer",
        note="Savings transfer",
    )

    tx = await finance_service.post_transaction(session, ws_id, body)
    assert tx.status == "posted"
    assert tx.destination_account_id == dest_id
    assert src_acc.balance_minor == 12500  # 200 - 75 = 125
    assert dest_acc.balance_minor == 12500  # 50 + 75 = 125


def test_finance_post_transfer_requires_destination_account_id():
    """Transfer without destination_account_id or with identical accounts raises ValidationError."""
    src_id = uuid4()

    # Missing destination_account_id
    with pytest.raises(ValidationError) as exc_info:
        TransactionCreate(
            account_id=src_id,
            destination_account_id=None,
            amount_minor=1000,
            currency="USD",
            type="transfer",
        )
    assert "destination_account_id is required for transfer transactions" in str(exc_info.value)

    # Identical source and destination
    with pytest.raises(ValidationError) as exc_info2:
        TransactionCreate(
            account_id=src_id,
            destination_account_id=src_id,
            amount_minor=1000,
            currency="USD",
            type="transfer",
        )
    assert "Source and destination accounts must be different" in str(exc_info2.value)


@pytest.mark.asyncio
async def test_finance_reverse_non_posted_transaction_raises_conflict():
    """Only posted transactions can be reversed; draft/reversed raises ConflictError."""
    session = create_mock_session()
    ws_id = uuid4()
    tx_id = uuid4()

    draft_tx = Transaction(
        id=tx_id,
        workspace_id=ws_id,
        account_id=uuid4(),
        amount_minor=500,
        currency="USD",
        transaction_type="expense",
        status="draft",  # Not posted
        occurred_at=datetime.now(timezone.utc),
    )

    res = MagicMock()
    res.scalar_one_or_none.return_value = draft_tx
    session.execute.return_value = res

    with pytest.raises(ConflictError):
        await finance_service.reverse_transaction(session, ws_id, tx_id)


@pytest.mark.asyncio
async def test_finance_reverse_expense_restores_balance_and_creates_reversal():
    """Reversing posted expense restores balance and marks original as reversed."""
    session = create_mock_session()
    ws_id = uuid4()
    tx_id = uuid4()
    acc_id = uuid4()

    orig_tx = Transaction(
        id=tx_id,
        workspace_id=ws_id,
        account_id=acc_id,
        amount_minor=3000,
        currency="RUB",
        transaction_type="expense",
        status="posted",
        occurred_at=datetime.now(timezone.utc),
    )
    mock_acc = Account(
        id=acc_id,
        workspace_id=ws_id,
        name="Card",
        currency="RUB",
        balance_minor=7000,  # Balance after expense
        account_type="checking",
    )

    res_tx = MagicMock()
    res_tx.scalar_one_or_none.return_value = orig_tx
    res_acc = MagicMock()
    res_acc.scalar_one_or_none.return_value = mock_acc

    session.execute.side_effect = [res_tx, res_acc]

    reversal = await finance_service.reverse_transaction(
        session=session,
        workspace_id=ws_id,
        transaction_id=tx_id,
        reason="User requested cancel",
    )

    # Balance restored: 7000 + 3000 = 10000
    assert mock_acc.balance_minor == 10000
    assert orig_tx.status == "reversed"
    assert reversal.transaction_type == "reversal"
    assert reversal.reversal_of_id == tx_id
    assert reversal.amount_minor == 3000
    assert session.commit.called


# =============================================================================
# 4. AI TOOL GATEWAY RISK TIERS & GOVERNANCE TESTS
# =============================================================================

def test_risk_tier_constants_and_numeric_mapping():
    """Verify RiskTier enum values and check constraint mappings."""
    assert RiskTier.READ.value == "read"
    assert RiskTier.LOW_WRITE.value == "low_write"
    assert RiskTier.MEDIUM_WRITE.value == "medium_write"
    assert RiskTier.FINANCIAL.value == "financial"
    assert RiskTier.BULK.value == "bulk"
    assert RiskTier.DESTRUCTIVE.value == "destructive"

    assert RISK_TIER_INT_MAP[RiskTier.READ] == 1
    assert RISK_TIER_INT_MAP[RiskTier.LOW_WRITE] == 2
    assert RISK_TIER_INT_MAP[RiskTier.MEDIUM_WRITE] == 3
    assert RISK_TIER_INT_MAP[RiskTier.FINANCIAL] == 4
    assert RISK_TIER_INT_MAP[RiskTier.BULK] == 5
    assert RISK_TIER_INT_MAP[RiskTier.DESTRUCTIVE] == 6


def test_tool_gateway_risk_tier_classifications():
    """Verify every registered tool is appropriately classified."""
    registry = ToolGateway.TOOL_REGISTRY

    # Read tools
    assert registry["get_tasks"] == RiskTier.READ
    assert registry["get_free_busy"] == RiskTier.READ
    assert registry["search_notes"] == RiskTier.READ

    # Low write
    assert registry["create_draft_note"] == RiskTier.LOW_WRITE

    # Medium write
    assert registry["move_task"] == RiskTier.MEDIUM_WRITE
    assert registry["create_time_block"] == RiskTier.MEDIUM_WRITE
    assert registry["create_task"] == RiskTier.MEDIUM_WRITE

    # Financial
    assert registry["post_expense"] == RiskTier.FINANCIAL
    assert registry["record_expense"] == RiskTier.FINANCIAL

    # Destructive (Blocked)
    assert registry["execute_sql"] == RiskTier.DESTRUCTIVE
    assert registry["drop_table"] == RiskTier.DESTRUCTIVE
    assert registry["delete_workspace"] == RiskTier.DESTRUCTIVE
    assert registry["delete_financial_ledger"] == RiskTier.DESTRUCTIVE


def test_tool_gateway_risk_evaluation_unknown_tool_defaults_to_destructive():
    """Any unregistered tool must default to RiskTier.DESTRUCTIVE."""
    session = create_mock_session()
    gateway = ToolGateway(session, workspace_id=uuid4())

    tier = gateway.evaluate_risk("random_unregistered_tool", {})
    assert tier == RiskTier.DESTRUCTIVE


def test_tool_gateway_evaluate_risk_detects_sql_injection():
    """Attempting SQL injection in tool args raises ValidationDomainError."""
    session = create_mock_session()
    gateway = ToolGateway(session, workspace_id=uuid4())

    injection_patterns = [
        "drop table tasks;",
        "SELECT * FROM users;",
        "1; DELETE FROM accounts;",
        "test' --",
        "exec('cmd')",
    ]

    for pattern in injection_patterns:
        with pytest.raises(ValidationDomainError):
            gateway.evaluate_risk("get_tasks", {"query": pattern})


@pytest.mark.asyncio
async def test_tool_gateway_dispatch_hard_blocks_destructive_tool():
    """Dispatching destructive tools raises ForbiddenError and logs blocked status."""
    session = create_mock_session()
    gateway = ToolGateway(session, workspace_id=uuid4())

    destructive_calls = [
        {"tool_name": "drop_table", "args": {"table": "tasks"}},
        {"tool_name": "delete_workspace", "args": {}},
        {"tool_name": "execute_sql", "args": {"sql": "TRUNCATE"}},
    ]

    for call in destructive_calls:
        with pytest.raises(ForbiddenError):
            await gateway.dispatch(call)


@pytest.mark.asyncio
async def test_tool_gateway_mutations_require_confirmation():
    """Mutating tool calls return payload with requires_confirmation=True."""
    session = create_mock_session()
    gateway = ToolGateway(session, workspace_id=uuid4())

    # 1. move_task
    res_move = await gateway.move_task(task_id=str(uuid4()), new_status="done")
    assert res_move["requires_confirmation"] is True
    assert res_move["tool_name"] == "move_task"

    # 2. create_time_block
    res_block = await gateway.create_time_block(
        task_id=str(uuid4()),
        start_at="2026-09-11T10:00:00Z",
        end_at="2026-09-11T11:00:00Z",
    )
    assert res_block["requires_confirmation"] is True
    assert res_block["tool_name"] == "create_time_block"

    # 3. post_expense
    res_exp = await gateway.post_expense(
        amount_minor=1500,
        currency="USD",
        category="food",
        account_id=str(uuid4()),
    )
    assert res_exp["requires_confirmation"] is True
    assert res_exp["tool_name"] == "post_expense"


# =============================================================================
# 5. UNTRUSTED DATA WRAPPING & PAGINATION INVARIANTS
# =============================================================================

def test_wrap_untrusted_data_xml_delimiters():
    """Verify wrap_untrusted_data encloses content in safe XML delimiters."""
    user_input = "Hello world <script>alert(1)</script>"
    wrapped = wrap_untrusted_data(user_input, origin="telegram")

    assert '<untrusted_external_data origin="telegram" sanitized="true">' in wrapped
    assert "</untrusted_external_data>" in wrapped
    assert "<script>" not in wrapped  # Must be escaped to &lt;script&gt;
    assert "&lt;script&gt;" in wrapped


def test_wrap_untrusted_data_strips_binary_control_chars():
    """Verify ASCII control chars are stripped from untrusted data."""
    dirty = "Hello\x00\x05\x08World\x1F"
    clean_wrapped = wrap_untrusted_data(dirty)
    assert "\x00" not in clean_wrapped
    assert "\x05" not in clean_wrapped
    assert "HelloWorld" in clean_wrapped


def test_extract_untrusted_data_roundtrip():
    """Verify extract_untrusted_data strips outer XML tags correctly."""
    raw = "Schedule meeting with Bob"
    wrapped = wrap_untrusted_data(raw, origin="quick_add")
    extracted = extract_untrusted_data(wrapped)
    assert extracted == raw


def test_cursor_pagination_encode_decode_roundtrip():
    """Verify opaque base64 cursor pagination encode/decode roundtrip."""
    payload = {
        "updated_at": "2026-09-11T12:00:00+00:00",
        "id": str(uuid4()),
    }
    encoded = encode_cursor(payload)
    assert isinstance(encoded, str)

    decoded = decode_cursor(encoded)
    assert decoded["updated_at"] == payload["updated_at"]
    assert decoded["id"] == payload["id"]


def test_goal_and_project_schemas_status_normalization():
    """Verify that GoalCreate, GoalUpdate, ProjectCreate, and ProjectUpdate normalize 'paused' to 'on_hold'."""
    from src.domains.projects.schemas import (
        GoalCreate,
        GoalUpdate,
        ProjectCreate,
        ProjectUpdate,
    )

    g_create = GoalCreate(title="Test Strategic Goal", status="paused")
    assert g_create.status == "on_hold"

    g_update = GoalUpdate(status="paused")
    assert g_update.status == "on_hold"

    p_create = ProjectCreate(name="Test Project", status="paused")
    assert p_create.status == "on_hold"

    p_update = ProjectUpdate(status="paused")
    assert p_update.status == "on_hold"

    # Verify canonical statuses are unchanged
    for canonical in ["planning", "active", "on_hold", "completed", "archived"]:
        assert GoalCreate(title="Valid", status=canonical).status == canonical
        assert ProjectCreate(name="Valid", status=canonical).status == canonical

    # Verify invalid status raises validation error
    with pytest.raises(ValidationError):
        GoalCreate(title="Invalid", status="in_progress")

    with pytest.raises(ValidationError):
        ProjectCreate(name="Invalid", status="blocked")

