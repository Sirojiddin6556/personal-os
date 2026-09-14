"""Pytest fixtures and configuration for Staging & E2E integration test suite."""

import os
from typing import AsyncGenerator, Dict
from uuid import UUID, uuid4

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from src.config import settings
from src.domains.identity.models import Workspace
from src.main import app
from src.shared.deps import get_current_user, get_db_session, get_public_session, get_workspace


@pytest.fixture(scope="session")
def staging_base_url() -> str:
    """Resolve base URL for live staging server or local development host."""
    return os.getenv("STAGING_API_URL", "http://localhost:8008")


@pytest.fixture(scope="session")
def staging_telegram_bot_token() -> str:
    """Resolve live staging telegram bot token from environment if configured."""
    return os.getenv("STAGING_TELEGRAM_BOT_TOKEN", "123456789:ABCdefGHIjklMNOpqrsTUVwxyz_staging")


@pytest.fixture(scope="session")
def staging_google_client_id() -> str:
    """Resolve staging Google OAuth client ID."""
    return os.getenv("STAGING_GOOGLE_CLIENT_ID", "staging-client-id.apps.googleusercontent.com")


@pytest.fixture(scope="session")
def staging_google_client_secret() -> str:
    """Resolve staging Google OAuth client secret."""
    return os.getenv("STAGING_GOOGLE_CLIENT_SECRET", "staging-client-secret-12345")


@pytest_asyncio.fixture
async def e2e_client() -> AsyncGenerator[AsyncClient, None]:
    """Provide AsyncClient against live staging server or ASGI test application."""
    staging_url = os.getenv("STAGING_API_URL")
    if staging_url:
        async with AsyncClient(base_url=staging_url, timeout=15.0) as c:
            yield c
    else:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://localhost:8008", timeout=15.0) as c:
            yield c
