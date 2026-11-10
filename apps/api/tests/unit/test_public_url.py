"""Quick Tunnel URL follower: settings update and bot re-registration."""

from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

import httpx
import pytest

from src.integrations.telegram import public_url


class _Session:
    def __init__(self, integrations):
        self.integrations = integrations
        self.commits = 0

    async def execute(self, _stmt):
        items = self.integrations
        return SimpleNamespace(scalars=lambda: SimpleNamespace(all=lambda: items))

    async def commit(self):
        self.commits += 1


def _client(calls):
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/quicktunnel"):
            return httpx.Response(200, json={"hostname": "new-words.trycloudflare.com"})
        calls.append((request.url.path.rsplit("/", 1)[-1], request.read().decode()))
        return httpx.Response(200, json={"ok": True})

    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


@pytest.fixture(autouse=True)
def _restore_settings():
    s = public_url.settings
    saved = (s.frontend_url, s.telegram_miniapp_url, s.telegram_webhook_base_url, s.google_redirect_uri)
    yield
    s.frontend_url, s.telegram_miniapp_url, s.telegram_webhook_base_url, s.google_redirect_uri = saved


def test_apply_public_url():
    public_url.apply_public_url("https://a.trycloudflare.com/")
    s = public_url.settings
    assert s.frontend_url == "https://a.trycloudflare.com"
    assert s.telegram_miniapp_url == "https://a.trycloudflare.com/tg/"
    assert s.telegram_webhook_base_url == "https://a.trycloudflare.com/api"


async def test_reconfigure_bot_sets_webhook_menu_and_notifies():
    calls = []
    integ = SimpleNamespace(
        id=uuid4(),
        config={"enc_token": "aa", "webhook_id": "wid", "webhook_secret": "sec", "chat_id": "42"},
    )
    session = _Session([integ])
    with patch("src.integrations.crypto.crypto_service.decrypt_token", return_value="123:TOKEN"):
        async with _client(calls) as client:
            n = await public_url.reconfigure_bots(session, "https://new.trycloudflare.com", client)
    assert n == 1
    methods = [m for m, _ in calls]
    assert methods == ["setWebhook", "setChatMenuButton", "sendMessage"]
    assert "https://new.trycloudflare.com/api/v1/webhooks/telegram/wid" in calls[0][1]
    assert '"secret_token":"sec"' in calls[0][1].replace(" ", "")
    assert "https://new.trycloudflare.com/tg/" in calls[1][1]
    assert integ.config["public_url"] == "https://new.trycloudflare.com"
    assert session.commits == 1


async def test_already_current_bot_is_skipped():
    calls = []
    integ = SimpleNamespace(id=uuid4(), config={"enc_token": "aa", "public_url": "https://same.trycloudflare.com"})
    async with _client(calls) as client:
        assert await public_url.reconfigure_bots(_Session([integ]), "https://same.trycloudflare.com", client) == 0
    assert calls == []


async def test_watcher_tick_reads_hostname(monkeypatch):
    calls = []
    seen = {}

    async def fake_reconfigure(session, base, client):
        seen["base"] = base
        return 0

    class _Factory:
        async def __aenter__(self):
            return _Session([])

        async def __aexit__(self, *a):
            return False

    monkeypatch.setattr(public_url, "reconfigure_bots", fake_reconfigure)
    monkeypatch.setattr(public_url, "async_session_factory", lambda: _Factory())
    w = public_url.PublicUrlWatcher("http://tunnel:2000/quicktunnel")
    async with _client(calls) as client:
        await w.tick(client)
    assert w.current == "https://new-words.trycloudflare.com"
    assert seen["base"] == w.current
    assert public_url.settings.telegram_miniapp_url == "https://new-words.trycloudflare.com/tg/"
