"""Regression tests for auth / tenancy hardening."""

from types import SimpleNamespace
from uuid import uuid4

import pytest

from src.config import DEV_SECRET_KEY, Settings
from src.db import session as db_session
from src.shared import deps
from src.shared.exceptions import BadRequestError, ForbiddenError, UnauthorizedError


# ---------------------------------------------------------------- settings
def test_default_environment_is_production(monkeypatch):
    monkeypatch.delenv("ENVIRONMENT", raising=False)
    monkeypatch.setenv("SECRET_KEY", "x" * 64)
    assert Settings(_env_file=None).environment == "production"


@pytest.mark.parametrize("secret", [DEV_SECRET_KEY, "short", ""])
def test_production_refuses_weak_secret(monkeypatch, secret):
    monkeypatch.setenv("SECRET_KEY", secret)
    with pytest.raises(ValueError):
        Settings(_env_file=None, environment="production")


def test_development_allows_dev_secret(monkeypatch):
    monkeypatch.delenv("SECRET_KEY", raising=False)
    s = Settings(_env_file=None, environment="development")
    assert s.is_development and s.secret_key == DEV_SECRET_KEY


# ---------------------------------------------------------------- auth fallback
async def test_no_token_is_unauthorized_outside_development(monkeypatch):
    monkeypatch.setattr(deps.settings, "environment", "production")
    with pytest.raises(UnauthorizedError):
        await deps.get_current_user(authorization=None, session=None)


async def test_bad_token_is_unauthorized_outside_development(monkeypatch):
    monkeypatch.setattr(deps.settings, "environment", "production")
    with pytest.raises(UnauthorizedError):
        await deps.get_current_user(authorization="Bearer not-a-jwt", session=None)


# ---------------------------------------------------------------- workspace resolution
class _Result:
    def __init__(self, item):
        self._item = item

    def scalars(self):
        return SimpleNamespace(first=lambda: self._item)


class _Session:
    """Returns the queued workspace (or None) for each execute()."""

    def __init__(self, *items):
        self.items = list(items)

    async def execute(self, _stmt):
        return _Result(self.items.pop(0) if self.items else None)


USER = SimpleNamespace(id=uuid4())


async def test_foreign_workspace_header_is_forbidden(monkeypatch):
    monkeypatch.setattr(deps.settings, "environment", "production")
    with pytest.raises(ForbiddenError):
        await deps.get_workspace(workspace_id_header=str(uuid4()), user=USER, session=_Session(None))


async def test_malformed_workspace_header_is_bad_request():
    with pytest.raises(BadRequestError):
        await deps.get_workspace(workspace_id_header="nope", user=USER, session=_Session())


async def test_member_workspace_header_is_returned():
    ws = SimpleNamespace(id=uuid4())
    assert await deps.get_workspace(workspace_id_header=str(ws.id), user=USER, session=_Session(ws)) is ws


async def test_no_workspace_is_forbidden_outside_development(monkeypatch):
    monkeypatch.setattr(deps.settings, "environment", "production")
    called = False

    async def provision(*_a):
        nonlocal called
        called = True

    monkeypatch.setattr(deps, "get_or_create_default_workspace", provision)
    with pytest.raises(ForbiddenError):
        await deps.get_workspace(workspace_id_header=None, user=USER, session=_Session(None))
    assert not called


# ---------------------------------------------------------------- RLS context
def test_tenant_context_reapplied_on_each_transaction():
    calls = []
    conn = SimpleNamespace(execute=lambda stmt, params: calls.append(params))
    wid = str(uuid4())

    db_session._apply_tenant_context(SimpleNamespace(info={db_session.TENANT_INFO_KEY: wid}), None, conn)
    db_session._apply_tenant_context(SimpleNamespace(info={db_session.TENANT_INFO_KEY: wid}), None, conn)
    assert calls == [{"wid": wid}, {"wid": wid}]

    db_session._apply_tenant_context(SimpleNamespace(info={}), None, conn)  # public session: untouched
    assert len(calls) == 2


# ---------------------------------------------------------------- telegram bot routing
async def test_unknown_chat_is_not_routed_to_the_only_workspace(monkeypatch):
    from src.integrations.telegram import handler

    integ = SimpleNamespace(workspace_id=uuid4(), config={"chat_id": "111"})

    class S:
        async def execute(self, _stmt):
            return SimpleNamespace(scalars=lambda: SimpleNamespace(all=lambda: [integ]))

    assert await handler.get_workspace_by_telegram_chat(999, session=S()) is None
    assert await handler.get_workspace_by_telegram_chat(111, session=S()) == integ.workspace_id
