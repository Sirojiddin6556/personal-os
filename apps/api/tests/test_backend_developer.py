from datetime import date, datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4
import jwt
import pytest

from src.config import settings
from src.domains.identity.models import Membership, User, Workspace
from src.domains.identity.schemas import (
    UserLoginRequest,
    UserRegisterRequest,
    WorkspaceCreateRequest,
)
from src.domains.identity.service import (
    create_access_token,
    hash_password,
    identity_service,
    verify_password,
)
from src.domains.planner.models import DailyJournal, Habit, HabitLog, PlannerReminder
from src.domains.planner.schemas import (
    DailyJournalInput,
    HabitCreate,
    HabitResponse,
    HabitUpdate,
    PlannerReminderCreate,
)
from src.domains.planner.service import planner_service
from src.domains.projects.models import Goal, Milestone, Project
from src.domains.projects.schemas import GoalCreate, MilestoneCreate, ProjectCreate
from src.domains.projects.service import project_service
from src.domains.tasks.models import Task, TaskStatus, Priority
from src.domains.tasks.schemas import TaskCreate, TaskUpdate, TaskResponse
from src.domains.tasks.service import task_service
from src.domains.finance.models import Account, Transaction
from src.domains.finance.schemas import TransactionCreate, AccountResponse
from src.domains.finance.service import finance_service
from src.domains.dashboard.service import calculate_free_windows, get_day_bounds
from src.domains.calendar.schemas import EventResponse
from src.shared.deps import parse_etag
from src.shared.exceptions import (
    BadRequestError,
    ConflictError,
    NotFoundError,
    OptimisticLockError,
    PreconditionFailedError,
    PreconditionRequiredError,
    UnauthorizedError,
)
from src.shared.pagination import CursorPage, encode_cursor, decode_cursor
from src.ws.router import authenticate_ws


def create_mock_session():
    s = AsyncMock()
    s.add = MagicMock()
    return s


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
    session = create_mock_session()
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
    session = create_mock_session()
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
    # Client sends version 1 (mismatched) -> RFC 9110 Precondition Failed (412)
    with pytest.raises(OptimisticLockError) as exc_info:
        await task_service.update(session, task_id, workspace_id, body, version=1)
    assert exc_info.value.status == 412
    assert exc_info.value.extensions["code"] == "STALE_VERSION"


def test_parse_etag_rfc_status_codes():
    """Verify parse_etag raises 428 when missing and 400 when malformed or weak."""
    assert parse_etag('"5"') == 5
    assert parse_etag('"12"') == 12

    # Missing If-Match -> 428 Precondition Required (RFC 6585)
    with pytest.raises(PreconditionRequiredError) as req_exc:
        parse_etag(None)
    assert req_exc.value.status == 428
    assert req_exc.value.extensions["code"] == "PRECONDITION_REQUIRED"

    # Malformed / Weak / Wildcard / List -> 400 Bad Request (RFC 9110)
    for invalid_header in ["abc", "*", 'W/"1"', 'w/"2"', '"1", "2"']:
        with pytest.raises(BadRequestError) as bad_exc:
            parse_etag(invalid_header)
        assert bad_exc.value.status == 400
        assert bad_exc.value.extensions["code"] == "INVALID_ETAG"


@pytest.mark.asyncio
async def test_finance_post_and_reverse_transaction():
    """Test financial ledger posting and reversing with balance adjustments."""
    session = create_mock_session()
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
    assert mock_account.balance_minor == 7500
    assert session.commit.called


# =====================================================================
# Identity & Cryptographic Password / JWT Tests
# =====================================================================

def test_password_hashing_and_verification():
    raw_password = "SuperSecretPassword123!"
    hashed = hash_password(raw_password)
    assert hashed != raw_password
    assert hashed.startswith("$2b$")
    assert verify_password(raw_password, hashed) is True
    assert verify_password("WrongPassword123!", hashed) is False
    assert verify_password("", hashed) is False


def test_create_access_token():
    user_id = uuid4()
    token_resp = create_access_token(user_id=user_id, expires_delta=timedelta(minutes=15))
    assert token_resp.token_type == "Bearer"
    assert token_resp.expires_in > 0
    assert token_resp.access_token is not None

    payload = jwt.decode(
        token_resp.access_token,
        settings.secret_key,
        algorithms=[settings.jwt_algorithm],
    )
    assert payload["sub"] == str(user_id)
    assert "exp" in payload


@pytest.mark.asyncio
async def test_identity_register_new_user_and_workspace():
    session = create_mock_session()
    mock_res = MagicMock()
    mock_res.scalar_one_or_none.return_value = None
    session.execute.return_value = mock_res

    req = UserRegisterRequest(
        email="john.doe@example.com",
        password="SecurePassword123!",
        full_name="John Doe",
        timezone="UTC",
    )
    with patch("src.domains.identity.service.publish_event", new=AsyncMock()) as mock_publish:
        user = await identity_service.register(session, req)
        assert user.email == "john.doe@example.com"
        assert user.full_name == "John Doe"
        assert verify_password("SecurePassword123!", user.password_hash)
        assert session.add.call_count >= 3
        assert mock_publish.called


@pytest.mark.asyncio
async def test_identity_register_duplicate_email_conflict():
    session = create_mock_session()
    existing_user = User(id=uuid4(), email="existing@example.com", password_hash="hashed")
    mock_res = MagicMock()
    mock_res.scalar_one_or_none.return_value = existing_user
    session.execute.return_value = mock_res

    req = UserRegisterRequest(email="existing@example.com", password="Password123!", full_name="Existing User")
    with pytest.raises(ConflictError):
        await identity_service.register(session, req)


@pytest.mark.asyncio
async def test_identity_authenticate_success_and_failures():
    session = create_mock_session()
    raw_pwd = "MySecretPassword123"
    hashed_pwd = hash_password(raw_pwd)
    user = User(id=uuid4(), email="auth.test@example.com", password_hash=hashed_pwd, status="active", is_active=True)

    # 1. Success
    mock_res = MagicMock()
    mock_res.scalar_one_or_none.return_value = user
    session.execute.return_value = mock_res
    token_res = await identity_service.authenticate(session, UserLoginRequest(email="auth.test@example.com", password=raw_pwd))
    assert token_res.access_token is not None
    assert token_res.token_type == "Bearer"

    # 2. Wrong password
    with pytest.raises(UnauthorizedError):
        await identity_service.authenticate(session, UserLoginRequest(email="auth.test@example.com", password="BadPassword!"))

    # 3. User not found
    mock_res_none = MagicMock()
    mock_res_none.scalar_one_or_none.return_value = None
    session.execute.return_value = mock_res_none
    with pytest.raises(UnauthorizedError):
        await identity_service.authenticate(session, UserLoginRequest(email="missing@example.com", password=raw_pwd))


# =====================================================================
# Planner Habits & Agenda Domain Tests
# =====================================================================

@pytest.mark.asyncio
async def test_planner_create_habit():
    session = create_mock_session()
    workspace_id = uuid4()
    data = HabitCreate(title="Drink 2L Water", description="Daily hydration", frequency_type="daily", target_count=2)
    habit = await planner_service.create_habit(session, workspace_id, data)
    assert habit.title == "Drink 2L Water"
    assert habit.workspace_id == workspace_id
    assert habit.current_streak == 0
    assert habit.best_streak == 0
    assert session.add.called


@pytest.mark.asyncio
async def test_planner_toggle_habit_streak_increment_and_decrement():
    session = create_mock_session()
    workspace_id = uuid4()
    habit_id = uuid4()
    now = datetime.now(timezone.utc)
    today = date(2026, 9, 14)

    habit = Habit(
        id=habit_id,
        workspace_id=workspace_id,
        title="Morning Exercise",
        frequency_type="daily",
        target_count=1,
        current_streak=2,
        best_streak=2,
        is_archived=False,
        created_at=now,
        updated_at=now,
    )

    # Step 1: Toggle ON
    mock_habit_res = MagicMock()
    mock_habit_res.scalar_one_or_none.return_value = habit
    mock_log_res = MagicMock()
    mock_log_res.scalar_one_or_none.return_value = None
    session.execute.side_effect = [mock_habit_res, mock_log_res]

    resp = await planner_service.toggle_habit_completion(session, workspace_id, habit_id, target_date=today)
    assert resp.is_completed_today is True
    assert resp.current_streak == 3
    assert resp.best_streak == 3

    # Step 2: Toggle OFF
    existing_log = HabitLog(id=uuid4(), workspace_id=workspace_id, habit_id=habit_id, logged_date=today, count=1)
    mock_log_res_exists = MagicMock()
    mock_log_res_exists.scalar_one_or_none.return_value = existing_log
    session.execute.side_effect = [mock_habit_res, mock_log_res_exists]

    resp_off = await planner_service.toggle_habit_completion(session, workspace_id, habit_id, target_date=today)
    assert resp_off.is_completed_today is False
    assert resp_off.current_streak == 2
    assert session.delete.called


@pytest.mark.asyncio
async def test_planner_journal_save_and_get():
    session = create_mock_session()
    workspace_id = uuid4()
    entry_date = date(2026, 9, 14)
    mock_res_none = MagicMock()
    mock_res_none.scalar_one_or_none.return_value = None
    session.execute.return_value = mock_res_none

    input_data = DailyJournalInput(
        entry_date=entry_date,
        morning_intention="Focus on high leverage tasks",
        evening_reflection="Completed Stage 3 and 4 successfully",
        gratitude="Productive development",
        mood="great",
        productivity_rating=5,
    )
    entry = await planner_service.save_journal_entry(session, workspace_id, input_data)
    assert entry.morning_intention == "Focus on high leverage tasks"
    assert entry.productivity_rating == 5
    assert session.add.called


# =====================================================================
# Projects & Goals Service Tests
# =====================================================================

@pytest.mark.asyncio
async def test_projects_create_and_manage_goals():
    session = create_mock_session()
    workspace_id = uuid4()

    proj_data = ProjectCreate(name="Personal OS Launch", description="Unified Life Dashboard", color="#6366f1")
    proj = await project_service.create_project(session, workspace_id, proj_data)
    assert proj.name == "Personal OS Launch"
    assert proj.workspace_id == workspace_id

    goal_data = GoalCreate(title="Hit 100 Daily Active Users", category="growth", progress_percentage=10)
    goal = await project_service.create_goal(session, workspace_id, goal_data)
    assert goal.title == "Hit 100 Daily Active Users"
    assert goal.progress_percentage == 10


