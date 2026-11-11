"""One-time sign-up invitations."""

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from src.domains.identity import invites
from src.integrations.telegram import invites_bot


def _inv(**kw):
    base = dict(revoked=False, used_at=None, expires_at=datetime.now(timezone.utc) + timedelta(days=1))
    base.update(kw)
    return SimpleNamespace(**base)


def test_usable_rules():
    assert invites.usable(_inv())
    assert not invites.usable(None)
    assert not invites.usable(_inv(revoked=True))
    assert not invites.usable(_inv(used_at=datetime.now(timezone.utc)))
    assert not invites.usable(_inv(expires_at=datetime.now(timezone.utc) - timedelta(seconds=1)))


def test_code_hash_is_stable_and_not_the_code():
    assert invites.hash_code("abc") == invites.hash_code(" abc ")
    assert invites.hash_code("abc") != "abc" and len(invites.hash_code("abc")) == 64


def test_bot_command_regexes():
    assert invites_bot.INVITE_RE.match("пригласить Акмаль")[1] == "Акмаль"
    assert invites_bot.INVITE_RE.match("Пригласи маму")[1] == "маму"
    assert invites_bot.INVITE_RE.match("приглашение")[1] == ""
    assert invites_bot.INVITE_RE.match("приглашения") is None  # list, not create
    assert invites_bot.LIST_RE.match("Приглашения")
    assert invites_bot.INVITE_RE.match("пригласительный билет купить") is None


def test_link_and_forward_text():
    base = invites_bot.base_url({"public_url": "https://x.trycloudflare.com/"})
    link = invites_bot.invite_link(base, "CODE123")
    assert link == "https://x.trycloudflare.com/login?invite=CODE123"
    text = invites_bot.forward_text(link, 7)
    assert link in text and "@BotFather" in text and "7 дн." in text


async def test_register_requires_valid_invite_when_closed(monkeypatch):
    from unittest.mock import AsyncMock, MagicMock

    import pytest

    from src.domains.identity.schemas import UserRegisterRequest
    from src.domains.identity.service import identity_service
    from src.shared.exceptions import ForbiddenError

    monkeypatch.setattr(identity_service, "registration_open", AsyncMock(return_value=False))
    monkeypatch.setattr(invites, "find", AsyncMock(return_value=None))
    body = UserRegisterRequest(email="a@example.com", password="password123", full_name="A", invite_code="bad")
    with pytest.raises(ForbiddenError, match="Приглашение недействительно"):
        await identity_service.register(MagicMock(), body)
    body.invite_code = None
    with pytest.raises(ForbiddenError, match="Регистрация новых аккаунтов отключена"):
        await identity_service.register(MagicMock(), body)
