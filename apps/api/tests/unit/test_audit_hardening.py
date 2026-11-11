"""Closed sign-up and the restricted (RLS-enforced) database role."""

from types import SimpleNamespace

import pytest

from src.db.app_role import build_statements
from src.domains.identity import service as identity_module
from src.domains.identity.schemas import UserRegisterRequest
from src.shared.exceptions import ForbiddenError


class _Session:
    """execute() answers whether any user exists."""

    def __init__(self, has_user: bool):
        self.has_user = has_user

    async def execute(self, _stmt):
        return SimpleNamespace(first=lambda: (1,) if self.has_user else None)


# ---------------------------------------------------------------- registration
async def test_registration_open_when_enabled(monkeypatch):
    monkeypatch.setattr(identity_module.settings, "allow_registration", True)
    assert await identity_module.identity_service.registration_open(_Session(has_user=True))


async def test_registration_closed_once_a_user_exists(monkeypatch):
    monkeypatch.setattr(identity_module.settings, "allow_registration", False)
    assert not await identity_module.identity_service.registration_open(_Session(has_user=True))


async def test_first_account_can_always_be_created(monkeypatch):
    monkeypatch.setattr(identity_module.settings, "allow_registration", False)
    assert await identity_module.identity_service.registration_open(_Session(has_user=False))


async def test_register_refused_when_closed(monkeypatch):
    # Also covers first Google sign-in, which goes through identity_service.register.
    monkeypatch.setattr(identity_module.settings, "allow_registration", False)
    body = UserRegisterRequest(email="x@example.com", password="password123", full_name="X")
    with pytest.raises(ForbiddenError):
        await identity_module.identity_service.register(_Session(has_user=True), body)


# ---------------------------------------------------------------- app role
def test_app_role_cannot_bypass_rls():
    sql = "\n".join(build_statements("personal_os_app", "a" * 64, "personal_os", "personal_os"))
    assert "NOSUPERUSER NOBYPASSRLS" in sql
    assert "GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO personal_os_app" in sql
    assert "ALTER DEFAULT PRIVILEGES FOR ROLE personal_os" in sql
    assert "REVOKE ALL ON TABLE alembic_version" in sql


@pytest.mark.parametrize(
    "role,password,owner",
    [
        ("personal_os_app", "short", "personal_os"),  # weak password
        ("personal_os_app", "a' OR '1'='1" + "a" * 20, "personal_os"),  # quoting
        ("Bad-Name", "a" * 64, "personal_os"),  # identifier
        ("personal_os", "a" * 64, "personal_os"),  # same as owner
    ],
)
def test_app_role_rejects_unsafe_input(role, password, owner):
    with pytest.raises(ValueError):
        build_statements(role, password, owner, "personal_os")
