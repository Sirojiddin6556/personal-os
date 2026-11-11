"""Google Calendar auto-sync loop and closed API docs."""

from unittest.mock import AsyncMock, patch
from uuid import uuid4

from src.integrations.google_calendar import scheduler


async def test_sync_all_keeps_going_when_one_workspace_fails():
    ok_ws, bad_ws = uuid4(), uuid4()

    async def fake_sync(ws):
        if ws == bad_ws:
            raise RuntimeError("token revoked")

    with patch.object(scheduler, "connected_workspaces", AsyncMock(return_value=[bad_ws, ok_ws])), \
         patch.object(scheduler, "sync_workspace", AsyncMock(side_effect=fake_sync)) as sync:
        assert await scheduler.sync_all() == 1
    assert [c.args[0] for c in sync.await_args_list] == [bad_ws, ok_ws]


async def test_scheduler_disabled_with_zero_interval():
    s = scheduler.CalendarSyncScheduler(interval=0)
    await s.start()
    assert s._task is None


def test_api_docs_can_be_turned_off(monkeypatch):
    from src import main

    monkeypatch.setattr(main.settings, "api_docs_enabled", False)
    app = main.create_app()
    paths = {getattr(r, "path", "") for r in app.routes}
    assert "/docs" not in paths and "/openapi.json" not in paths
    assert app.openapi()["paths"]  # schema still available in-process (docs/api.md test)
