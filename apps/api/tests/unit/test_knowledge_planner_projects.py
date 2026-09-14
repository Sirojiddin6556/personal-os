"""Unit tests for Knowledge, Planner, Projects, and Notifications services."""

from datetime import date, datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4
import pytest

from src.domains.knowledge.models import Note, NoteChunk
from src.domains.knowledge.schemas import NoteCreate, NoteUpdate
from src.domains.knowledge.service import (
    chunk_text,
    embed_texts,
    index_note,
    knowledge_service,
)
from src.domains.notifications.models import Notification
from src.domains.notifications.schemas import NotificationCreate
from src.domains.notifications.service import notification_service
from src.domains.planner.models import DailyJournal, Habit, HabitLog, PlannerReminder
from src.domains.planner.schemas import (
    DailyJournalInput,
    HabitCreate,
    HabitUpdate,
    PlannerReminderCreate,
)
from src.domains.planner.service import planner_service
from src.domains.projects.models import Goal, Milestone, Project
from src.domains.projects.schemas import (
    GoalCreate,
    GoalUpdate,
    MilestoneCreate,
    MilestoneUpdate,
    ProjectCreate,
    ProjectUpdate,
)
from src.domains.projects.service import project_service
from src.shared.exceptions import NotFoundError


@pytest.fixture
def mock_session():
    s = AsyncMock()
    s.add = MagicMock()
    s.commit = AsyncMock()
    s.flush = AsyncMock()
    s.refresh = AsyncMock()
    s.delete = AsyncMock()
    return s


# =============================================================================
# KNOWLEDGE DOMAIN
# =============================================================================

def test_chunk_text_empty_and_short():
    assert chunk_text("") == []
    assert chunk_text("   ") == []
    short = chunk_text("Hello world", chunk_size=512)
    assert len(short) == 1
    assert short[0].text == "Hello world"
    assert short[0].index == 0


def test_chunk_text_splitting():
    long_text = "word " * 200  # ~1000 chars
    chunks = chunk_text(long_text, chunk_size=200, overlap=30)
    assert len(chunks) > 1
    for i, c in enumerate(chunks):
        assert c.index == i
        assert len(c.text) <= 250


@pytest.mark.asyncio
async def test_embed_texts_fallback():
    vecs = await embed_texts(["First chunk", "Second chunk"])
    assert len(vecs) == 2
    assert len(vecs[0]) == 1536
    assert len(vecs[1]) == 1536
    assert isinstance(vecs[0][0], float)


@pytest.mark.asyncio
async def test_knowledge_crud(mock_session):
    ws_id = uuid4()
    note_id = uuid4()
    body = NoteCreate(title="Test Note", content="Content for note", tags=["tag1"])

    # Create Note
    with patch("src.domains.knowledge.service.publish_event", new=AsyncMock()), \
         patch("src.domains.knowledge.service.index_note", new=AsyncMock()):
        note = await knowledge_service.create_note(mock_session, ws_id, body)
        assert note.title == "Test Note"
        assert note.workspace_id == ws_id
        mock_session.add.assert_called()

    # List Notes
    mock_res_list = MagicMock()
    mock_res_list.scalars.return_value.all.return_value = [note]
    mock_session.execute.return_value = mock_res_list
    notes = await knowledge_service.list_notes(mock_session, ws_id)
    assert len(notes) == 1

    # Get Note success
    mock_res = MagicMock()
    mock_res.scalar_one_or_none.return_value = note
    mock_session.execute.return_value = mock_res
    fetched = await knowledge_service.get_note(mock_session, ws_id, note_id)
    assert fetched.title == "Test Note"

    # Update Note
    update_body = NoteUpdate(title="Updated Title", content="Updated Content")
    with patch("src.domains.knowledge.service.publish_event", new=AsyncMock()), \
         patch("src.domains.knowledge.service.index_note", new=AsyncMock()):
        updated = await knowledge_service.update_note(mock_session, ws_id, note_id, update_body)
        assert updated.title == "Updated Title"

    # Delete Note
    with patch("src.domains.knowledge.service.publish_event", new=AsyncMock()):
        await knowledge_service.delete_note(mock_session, ws_id, note_id)
        assert note.is_archived is True

    # Get Note not found
    mock_res_none = MagicMock()
    mock_res_none.scalar_one_or_none.return_value = None
    mock_session.execute.return_value = mock_res_none
    with pytest.raises(NotFoundError):
        await knowledge_service.get_note(mock_session, ws_id, uuid4())


# =============================================================================
# PLANNER & HABITS DOMAIN
# =============================================================================

@pytest.mark.asyncio
async def test_planner_habits_crud_and_toggle(mock_session):
    ws_id = uuid4()
    habit_id = uuid4()

    # Create habit
    body = HabitCreate(
        title="Drink water",
        description="2 liters a day",
        frequency_type="daily",
        target_count=1,
    )
    habit = await planner_service.create_habit(mock_session, ws_id, body)
    assert habit.title == "Drink water"
    assert habit.current_streak == 0

    # List habits
    habit.id = habit_id
    habit.is_archived = False
    habit.created_at = datetime.now(timezone.utc)
    habit.updated_at = datetime.now(timezone.utc)

    mock_res_habits = MagicMock()
    mock_res_habits.scalars.return_value.all.return_value = [habit]
    mock_res_logs = MagicMock()
    mock_res_logs.scalars.return_value.all.return_value = []
    mock_session.execute.side_effect = [mock_res_habits, mock_res_logs]
    habits = await planner_service.list_habits(mock_session, ws_id)
    assert len(habits) == 1

    # Toggle habit completion (first toggle = complete)
    test_habit = Habit(
        id=habit_id,
        workspace_id=ws_id,
        title="Drink water",
        target_count=1,
        frequency_type="daily",
        current_streak=0,
        best_streak=0,
        is_archived=False,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    
    mock_res_habit = MagicMock()
    mock_res_habit.scalar_one_or_none.return_value = test_habit
    mock_res_log_none = MagicMock()
    mock_res_log_none.scalar_one_or_none.return_value = None

    mock_session.execute.side_effect = [mock_res_habit, mock_res_log_none]

    with patch("src.domains.planner.service.publish_event", new=AsyncMock()):
        resp = await planner_service.toggle_habit_completion(mock_session, ws_id, habit_id)
        assert resp.is_completed_today is True
        assert resp.current_streak == 1
        assert resp.best_streak == 1

    # Toggle again (uncomplete)
    existing_log = HabitLog(
        id=uuid4(),
        workspace_id=ws_id,
        habit_id=habit_id,
        logged_date=date.today(),
        count=1,
    )
    mock_session.execute.side_effect = [mock_res_habit, MagicMock(scalar_one_or_none=MagicMock(return_value=existing_log))]
    with patch("src.domains.planner.service.publish_event", new=AsyncMock()):
        resp_uncomplete = await planner_service.toggle_habit_completion(mock_session, ws_id, habit_id)
        assert resp_uncomplete.is_completed_today is False
        assert resp_uncomplete.current_streak == 0


@pytest.mark.asyncio
async def test_planner_journal_and_reminders(mock_session):
    ws_id = uuid4()
    body = DailyJournalInput(
        entry_date=date.today(),
        morning_intention="Write high quality code",
        evening_reflection="All tests passed cleanly",
        productivity_rating=5,
    )

    mock_res = MagicMock()
    mock_res.scalar_one_or_none.return_value = None
    mock_session.execute.return_value = mock_res

    with patch("src.domains.planner.service.publish_event", new=AsyncMock()):
        journal = await planner_service.save_journal_entry(mock_session, ws_id, body)
        assert journal.morning_intention == "Write high quality code"
        assert journal.productivity_rating == 5
        mock_session.add.assert_called()

    # Get journal
    mock_res_j = MagicMock()
    mock_res_j.scalar_one_or_none.return_value = journal
    mock_session.execute.return_value = mock_res_j
    fetched = await planner_service.get_journal_entry(mock_session, ws_id, date.today())
    assert fetched.morning_intention == "Write high quality code"

    # Reminders CRUD
    rem_body = PlannerReminderCreate(
        title="Check Standup",
        remind_at=datetime.now(timezone.utc),
    )
    with patch("src.domains.planner.service.publish_event", new=AsyncMock()):
        rem = await planner_service.create_reminder(mock_session, ws_id, rem_body)
        assert rem.title == "Check Standup"

    mock_res_rem = MagicMock()
    mock_res_rem.scalars.return_value.all.return_value = [rem]
    mock_session.execute.return_value = mock_res_rem
    rems = await planner_service.list_active_reminders(mock_session, ws_id)
    assert len(rems) == 1

    # Dismiss reminder
    mock_res_single_rem = MagicMock()
    mock_res_single_rem.scalar_one_or_none.return_value = rem
    mock_session.execute.return_value = mock_res_single_rem
    with patch("src.domains.planner.service.publish_event", new=AsyncMock()):
        await planner_service.dismiss_reminder(mock_session, ws_id, rem.id)
        assert rem.is_dismissed is True


# =============================================================================
# PROJECTS & GOALS DOMAIN
# =============================================================================

@pytest.mark.asyncio
async def test_projects_and_goals_crud(mock_session):
    ws_id = uuid4()
    goal_id = uuid4()
    proj_id = uuid4()
    ms_id = uuid4()

    # Create Goal
    goal_body = GoalCreate(
        title="Launch Product",
        description="Ship v1.0",
        category="career",
        status="active",
        progress_percentage=20,
    )
    with patch("src.domains.projects.service.publish_event", new=AsyncMock()):
        goal = await project_service.create_goal(mock_session, ws_id, goal_body)
        assert goal.title == "Launch Product"
        assert goal.progress_percentage == 20

    # List & Get Goal
    mock_res_g = MagicMock()
    mock_res_g.scalars.return_value.all.return_value = [goal]
    mock_res_g.scalar_one_or_none.return_value = goal
    mock_session.execute.return_value = mock_res_g
    goals = await project_service.list_goals(mock_session, ws_id)
    assert len(goals) == 1
    g = await project_service.get_goal(mock_session, ws_id, goal_id)
    assert g.title == "Launch Product"

    # Update & Delete Goal
    with patch("src.domains.projects.service.publish_event", new=AsyncMock()):
        upd_g = await project_service.update_goal(mock_session, ws_id, goal_id, GoalUpdate(title="Launch Product v2"))
        assert upd_g.title == "Launch Product v2"
        await project_service.delete_goal(mock_session, ws_id, goal_id)
        mock_session.delete.assert_called_with(goal)

    # Create Project
    proj_body = ProjectCreate(
        name="Personal OS Web",
        goal_id=goal.id,
        status="active",
        color="#3B82F6",
        github_repo="siroj/personal-os",
    )
    with patch("src.domains.projects.service.publish_event", new=AsyncMock()):
        proj = await project_service.create_project(mock_session, ws_id, proj_body)
        assert proj.name == "Personal OS Web"
        assert proj.github_repo == "siroj/personal-os"

    # List & Get Project
    mock_res_p = MagicMock()
    mock_res_p.scalars.return_value.all.return_value = [proj]
    mock_res_p.scalar_one_or_none.return_value = proj
    mock_session.execute.return_value = mock_res_p
    projects = await project_service.list_projects(mock_session, ws_id)
    assert len(projects) == 1
    p = await project_service.get_project(mock_session, ws_id, proj_id)
    assert p.name == "Personal OS Web"

    # Update & Delete Project
    with patch("src.domains.projects.service.publish_event", new=AsyncMock()):
        upd_p = await project_service.update_project(mock_session, ws_id, proj_id, ProjectUpdate(name="Personal OS App"))
        assert upd_p.name == "Personal OS App"
        await project_service.delete_project(mock_session, ws_id, proj_id)
        mock_session.delete.assert_called_with(proj)

    # Milestones CRUD
    ms_body = MilestoneCreate(
        title="Beta Release",
        project_id=proj_id,
        due_date=date.today(),
        status="pending",
    )
    with patch("src.domains.projects.service.publish_event", new=AsyncMock()):
        ms = await project_service.create_milestone(mock_session, ws_id, ms_body)
        assert ms.title == "Beta Release"

    mock_res_ms = MagicMock()
    mock_res_ms.scalars.return_value.all.return_value = [ms]
    mock_res_ms.scalar_one_or_none.return_value = ms
    mock_session.execute.return_value = mock_res_ms

    milestones = await project_service.list_milestones(mock_session, ws_id)
    assert len(milestones) == 1
    fetched_ms = await project_service.get_milestone(mock_session, ws_id, ms_id)
    assert fetched_ms.title == "Beta Release"

    with patch("src.domains.projects.service.publish_event", new=AsyncMock()):
        upd_ms = await project_service.update_milestone(mock_session, ws_id, ms_id, MilestoneUpdate(title="GA Release"))
        assert upd_ms.title == "GA Release"
        await project_service.delete_milestone(mock_session, ws_id, ms_id)


# =============================================================================
# NOTIFICATIONS DOMAIN
# =============================================================================

@pytest.mark.asyncio
async def test_notifications_service(mock_session):
    ws_id = uuid4()
    user_id = uuid4()
    notif_id = uuid4()
    body = NotificationCreate(
        user_id=user_id,
        title="Sync complete",
        body="Google calendar successfully synced 5 events",
        channel="in_app",
    )
    with patch("src.domains.notifications.service.publish_event", new=AsyncMock()):
        notif = await notification_service.create_notification(mock_session, ws_id, body)
        assert notif.title == "Sync complete"
        assert notif.status == "pending"

    # List notifications
    mock_res_n = MagicMock()
    mock_res_n.scalars.return_value.all.return_value = [notif]
    mock_res_n.scalar_one_or_none.return_value = notif
    mock_session.execute.return_value = mock_res_n

    notifs = await notification_service.list_notifications(mock_session, ws_id, user_id)
    assert len(notifs) == 1

    # Mark read
    with patch("src.domains.notifications.service.publish_event", new=AsyncMock()):
        read_n = await notification_service.mark_as_read(mock_session, ws_id, notif_id)
        assert read_n.read_at is not None


# =============================================================================
# DASHBOARD DOMAIN
# =============================================================================

@pytest.mark.asyncio
async def test_dashboard_service_today_and_summary(mock_session):
    from src.domains.dashboard.service import (
        dashboard_service,
        get_day_bounds,
        calculate_free_windows,
    )
    from src.domains.calendar.schemas import EventResponse

    ws_id = uuid4()
    user_id = uuid4()

    # Day bounds
    start_utc, end_utc = get_day_bounds("UTC")
    assert start_utc < end_utc

    # Calculate free windows
    now = datetime.now(timezone.utc)
    mock_events = [
        EventResponse(
            id=uuid4(),
            workspace_id=ws_id,
            title="Meeting 1",
            starts_at=now.replace(hour=10, minute=0, second=0, microsecond=0),
            ends_at=now.replace(hour=11, minute=0, second=0, microsecond=0),
            is_all_day=False,
            status="confirmed",
            version=1,
            sync_status="local",
            created_at=now,
            updated_at=now,
        )
    ]
    free_wins = calculate_free_windows(mock_events, start_utc, end_utc)
    assert isinstance(free_wins, list)

    # Dashboard Today
    mock_session.execute.side_effect = [
        MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[])))),  # events
        MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[])))),  # top tasks
        MagicMock(scalar_one=MagicMock(return_value=0)),  # overdue count
        MagicMock(one=MagicMock(return_value=(1500000, 3))),  # budget summary
    ]
    today_data = await dashboard_service.get_today(mock_session, ws_id)
    assert today_data.overdue_count == 0
    assert today_data.budget_summary.total_balance_minor == 1500000
    assert today_data.budget_summary.active_accounts_count == 3

