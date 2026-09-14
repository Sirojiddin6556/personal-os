"""Unit tests for Calendar and GitHub integration services."""

from datetime import datetime, timezone, timedelta, date
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4
import pytest

from src.domains.calendar.models import Event, TimeBlock
from src.domains.calendar.schemas import EventCreate, TimeBlockCreate
from src.domains.calendar.service import calendar_service
from src.integrations.github.service import github_service
from src.integrations.models import Integration, OAuthCredential
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
# CALENDAR DOMAIN
# =============================================================================

@pytest.mark.asyncio
async def test_calendar_create_event_and_timeblock(mock_session):
    ws_id = uuid4()
    now = datetime.now(timezone.utc)
    later = now + timedelta(hours=1)

    event_body = EventCreate(
        title="Architecture Review",
        description="Review RFC status codes and ETag invariants",
        starts_at=now,
        ends_at=later,
        is_all_day=False,
    )

    with patch("src.domains.calendar.service.publish_event", new=AsyncMock()):
        event = await calendar_service.create_event(mock_session, ws_id, event_body)
        assert event.title == "Architecture Review"
        assert event.workspace_id == ws_id
        assert event.version == 1

    # List Events
    mock_res_ev = MagicMock()
    mock_res_ev.scalars.return_value.all.return_value = [event]
    mock_session.execute.return_value = mock_res_ev

    events = await calendar_service.list_events(mock_session, ws_id, now, later)
    assert len(events) == 1

    # TimeBlock CRUD
    tb_body = TimeBlockCreate(
        task_id=None,
        starts_at=now,
        ends_at=later,
        label="Deep Work Block",
        is_fixed=True,
    )
    with patch("src.domains.calendar.service.publish_event", new=AsyncMock()):
        tb = await calendar_service.create_time_block(mock_session, ws_id, tb_body)
        assert tb.label == "Deep Work Block"
        assert tb.is_fixed is True

    mock_res_tb = MagicMock()
    mock_res_tb.scalars.return_value.all.return_value = [tb]
    mock_session.execute.return_value = mock_res_tb

    tbs = await calendar_service.list_time_blocks(mock_session, ws_id, now, later)
    assert len(tbs) == 1

    # FreeBusy & Day Events
    mock_session.execute.side_effect = [mock_res_ev, mock_res_tb]
    fb = await calendar_service.get_free_busy(mock_session, ws_id, now, later)
    assert len(fb.busy_windows) >= 1

    mock_session.execute.side_effect = [mock_res_ev]
    day_events = await calendar_service.get_events_for_day(mock_session, ws_id, "2026-09-14")
    assert len(day_events) == 1


# =============================================================================
# GITHUB INTEGRATION DOMAIN
# =============================================================================

@pytest.mark.asyncio
async def test_github_service_connect_and_status(mock_session):
    ws_id = uuid4()
    test_token = "ghp_MockTestToken1234567890abcdef"

    mock_client = AsyncMock()
    mock_client.get_current_user.return_value = {
        "login": "octocat",
        "name": "The Octocat",
        "avatar_url": "https://avatars.githubusercontent.com/u/583231",
        "html_url": "https://github.com/octocat",
        "public_repos": 8,
    }
    mock_client.list_repositories.return_value = [
        {"full_name": "octocat/Hello-World", "private": False, "default_branch": "main"}
    ]
    mock_client.list_pull_requests.return_value = [
        {"number": 1, "title": "Initial feature", "state": "open", "html_url": "https://github.com/octocat/Hello-World/pull/1"}
    ]

    mock_res_integration = MagicMock()
    mock_res_integration.scalar_one_or_none.return_value = None

    mock_res_cred = MagicMock()
    mock_res_cred.scalar_one_or_none.return_value = None

    mock_session.execute.side_effect = [mock_res_integration, mock_res_cred]

    with patch("src.integrations.github.service.GitHubClient", return_value=mock_client), \
         patch("src.integrations.github.service.publish_event", new=AsyncMock()):
        res = await github_service.connect_github(mock_session, ws_id, test_token)
        assert res["status"] == "connected"
        assert res["user"]["login"] == "octocat"
        assert res["user"]["name"] == "The Octocat"

    # Status check with active credential
    integ_id = uuid4()
    mock_integ = Integration(
        id=integ_id,
        workspace_id=ws_id,
        provider="github",
        status="connected",
        config={"login": "octocat", "name": "The Octocat"},
    )
    mock_session.execute.side_effect = [
        MagicMock(scalar_one_or_none=MagicMock(return_value=mock_integ)),
    ]

    with patch.object(github_service, "get_client", new=AsyncMock(return_value=mock_client)):
        status = await github_service.get_github_status(mock_session, ws_id)
        assert status["status"] == "connected"
        assert status["user"]["login"] == "octocat"

        # List Repositories
        mock_client.list_user_repos.return_value = [
            {"id": 123, "name": "personal-os", "full_name": "octocat/personal-os", "private": False}
        ]
        repos = await github_service.list_repositories(mock_session, ws_id)
        assert len(repos) == 1
        assert repos[0]["name"] == "personal-os"

        # Disconnect GitHub
        mock_session.execute.side_effect = [MagicMock(scalar_one_or_none=MagicMock(return_value=mock_integ))]
        await github_service.disconnect_github(mock_session, ws_id)
        mock_session.delete.assert_called_with(mock_integ)


@pytest.mark.asyncio
async def test_github_service_project_operations(mock_session):
    from src.domains.projects.models import Project

    ws_id = uuid4()
    proj_id = uuid4()
    integ_id = uuid4()

    mock_client = AsyncMock()
    mock_client.get_repo.return_value = {
        "name": "personal-os",
        "description": "Personal AI OS",
        "default_branch": "main",
    }
    mock_client.list_commits.return_value = [
        {
            "sha": "abc1234567890",
            "commit": {"message": "Initial commit", "author": {"name": "Siroj", "email": "dev@example.com", "date": "2026-09-14T10:00:00Z"}},
            "html_url": "https://github.com/octocat/personal-os/commit/abc1234",
        }
    ]
    mock_client.list_pull_requests.return_value = [
        {"number": 1, "title": "Feature branch", "state": "open", "html_url": "https://github.com/octocat/personal-os/pull/1"}
    ]

    mock_integ = Integration(
        id=integ_id,
        workspace_id=ws_id,
        provider="github",
        status="connected",
        config={"login": "octocat"},
    )
    mock_proj = Project(
        id=proj_id,
        workspace_id=ws_id,
        name="personal-os",
        github_repo="octocat/personal-os",
        github_default_branch="main",
        status="active",
        color="#3B82F6",
    )

    with patch.object(github_service, "get_client", new=AsyncMock(return_value=mock_client)), \
         patch.object(github_service, "_get_integration", new=AsyncMock(return_value=mock_integ)), \
         patch("src.integrations.github.service.publish_event", new=AsyncMock()):
        
        # Import repository
        imported = await github_service.import_repository_as_project(
            mock_session, ws_id, "octocat/personal-os", name="Personal OS"
        )
        assert imported.name == "Personal OS"
        assert imported.github_repo == "octocat/personal-os"

        # Get commits
        mock_session.execute.side_effect = [MagicMock(scalar_one_or_none=MagicMock(return_value=mock_proj))]
        commits = await github_service.get_project_commits(mock_session, ws_id, proj_id)
        assert len(commits) == 1
        assert commits[0]["sha"] == "abc1234567890"

        # Get contents
        mock_client.get_contents.return_value = [
            {"name": "README.md", "path": "README.md", "type": "file", "size": 100}
        ]
        mock_session.execute.side_effect = [MagicMock(scalar_one_or_none=MagicMock(return_value=mock_proj))]
        contents = await github_service.get_project_contents(mock_session, ws_id, proj_id)
        assert len(contents) == 1
        assert contents[0]["name"] == "README.md"

        # Create commit
        mock_client.create_or_update_file.return_value = {
            "commit": {"sha": "def5678", "html_url": "https://github.com/octocat/personal-os/commit/def5678"}
        }
        mock_session.execute.side_effect = [MagicMock(scalar_one_or_none=MagicMock(return_value=mock_proj))]
        commit_res = await github_service.create_commit(
            mock_session, ws_id, proj_id, "src/main.py", "print('hello')", "feat: new file"
        )
        assert commit_res["success"] is True
        assert commit_res["commit_sha"] == "def5678"

        # Sync issues
        mock_client.list_issues.return_value = [
            {"number": 42, "title": "Fix bug in planner", "body": "Details", "html_url": "https://github.com/issue/42"}
        ]
        mock_session.execute.side_effect = [
            MagicMock(scalar_one_or_none=MagicMock(return_value=mock_proj)),
            MagicMock(scalar_one_or_none=MagicMock(return_value=None)),  # not existing task
        ]
        tasks = await github_service.sync_project_issues_as_tasks(mock_session, ws_id, proj_id)
        assert len(tasks) == 1
        assert tasks[0].title == "[#42] Fix bug in planner"

