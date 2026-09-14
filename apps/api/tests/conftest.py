"""Pytest test configuration and fixtures for Personal OS API."""

from datetime import datetime, timezone
import json
from typing import Any, AsyncGenerator, Dict, List, Optional
from uuid import UUID, uuid4
import pytest
from httpx import ASGITransport, AsyncClient
import jwt
from fastapi import Depends, Header

from src.config import settings
from src.domains.finance.models import Account, Transaction
from src.domains.identity.models import User, Workspace
from src.domains.knowledge.models import Note, NoteChunk
from src.domains.tasks.models import Priority, Task, TaskStatus
from src.integrations.models import Integration
from src.main import app
from src.shared.deps import (
    get_current_user,
    get_db_session,
    get_public_session,
    get_workspace,
)
from src.shared.outbox import OutboxEvent


class MockScalarResult:
    """Mock result returning scalars from execute()."""

    def __init__(self, items: List[Any]):
        self._items = items

    def scalar_one_or_none(self) -> Optional[Any]:
        return self._items[0] if self._items else None

    def scalars(self):
        class _Scalars:
            def __init__(self, it):
                self._it = it

            def all(self):
                return self._it

            def first(self):
                return self._it[0] if self._it else None

        return _Scalars(self._items)

    def all(self) -> List[Any]:
        return self._items

    def first(self) -> Optional[Any]:
        return self._items[0] if self._items else None


class InMemoryDB:
    """Fast in-memory datastore for unit & integration testing."""

    def __init__(self):
        self.tasks: Dict[UUID, Task] = {}
        self.accounts: Dict[UUID, Account] = {}
        self.transactions: Dict[UUID, Transaction] = {}
        self.notes: Dict[UUID, Note] = {}
        self.note_chunks: Dict[UUID, NoteChunk] = {}
        self.integrations: Dict[UUID, Integration] = {}
        self.outbox: List[OutboxEvent] = []

    def clear(self):
        self.tasks.clear()
        self.accounts.clear()
        self.transactions.clear()
        self.notes.clear()
        self.note_chunks.clear()
        self.integrations.clear()
        self.outbox.clear()


class FakeAsyncSession:
    """AsyncSession mock matching SQLAlchemy semantics."""

    def __init__(self, db: InMemoryDB):
        self.db = db

    def add(self, obj: Any) -> None:
        now = datetime.now(timezone.utc)
        if hasattr(obj, "id") and getattr(obj, "id", None) is None:
            obj.id = uuid4()
        if hasattr(obj, "created_at") and getattr(obj, "created_at", None) is None:
            obj.created_at = now
        if hasattr(obj, "updated_at") and getattr(obj, "updated_at", None) is None:
            obj.updated_at = now

        if isinstance(obj, Task):
            if not getattr(obj, "version", None):
                obj.version = 1
            self.db.tasks[obj.id] = obj
        elif isinstance(obj, Account):
            self.db.accounts[obj.id] = obj
        elif isinstance(obj, Transaction):
            self.db.transactions[obj.id] = obj
        elif isinstance(obj, Note):
            self.db.notes[obj.id] = obj
        elif isinstance(obj, NoteChunk):
            self.db.note_chunks[obj.id] = obj
        elif isinstance(obj, Integration):
            self.db.integrations[obj.id] = obj
        elif isinstance(obj, OutboxEvent):
            self.db.outbox.append(obj)

    async def commit(self) -> None:
        pass

    async def flush(self) -> None:
        pass

    async def refresh(self, obj: Any) -> None:
        pass

    async def get(self, entity_cls: Any, ident: Any) -> Optional[Any]:
        if entity_cls is Task:
            return self.db.tasks.get(ident)
        if entity_cls is Transaction:
            return self.db.transactions.get(ident)
        if entity_cls is Account:
            return self.db.accounts.get(ident)
        if entity_cls is Note:
            return self.db.notes.get(ident)
        if entity_cls is Integration:
            return self.db.integrations.get(ident)
        return None

    async def execute(self, statement: Any, *args, **kwargs) -> MockScalarResult:
        sql = str(statement).lower()
        try:
            params = statement.compile().params or {}
        except Exception:
            params = {}

        target_id = None
        target_ws = None
        for k, v in params.items():
            if isinstance(v, (UUID, str)):
                try:
                    val_uuid = UUID(str(v))
                except (ValueError, TypeError):
                    continue
                if "workspace" in k.lower():
                    target_ws = val_uuid
                elif "id" in k.lower() or "account" in k.lower() or "task" in k.lower() or "transaction" in k.lower() or "integration" in k.lower():
                    target_id = val_uuid

        # Handle Integration queries
        if "from integrations" in sql:
            filtered = list(self.db.integrations.values())
            if target_id:
                filtered = [i for i in filtered if i.id == target_id]
            if target_ws:
                filtered = [i for i in filtered if i.workspace_id == target_ws]
            if "status" in sql and "connected" in sql:
                filtered = [i for i in filtered if i.status == "connected"]
            return MockScalarResult(filtered)

        # Handle Task queries
        if "from tasks" in sql:
            filtered = list(self.db.tasks.values())
            if target_id:
                filtered = [t for t in filtered if t.id == target_id]
            if target_ws:
                filtered = [t for t in filtered if t.workspace_id == target_ws]
            return MockScalarResult(filtered)

        # Handle Account queries
        if "from accounts" in sql:
            filtered = list(self.db.accounts.values())
            if target_id:
                filtered = [a for a in filtered if a.id == target_id]
            if target_ws:
                filtered = [a for a in filtered if a.workspace_id == target_ws]
            return MockScalarResult(filtered)

        # Handle Transaction queries
        if "from transactions" in sql:
            filtered = list(self.db.transactions.values())
            if target_id:
                filtered = [tx for tx in filtered if tx.id == target_id]
            if target_ws:
                filtered = [tx for tx in filtered if tx.workspace_id == target_ws]
            return MockScalarResult(filtered)

        # Handle NoteChunk queries (Semantic search / RAG)
        if "from note_chunks" in sql:
            filtered = list(self.db.note_chunks.values())
            if target_ws:
                filtered = [c for c in filtered if c.workspace_id == target_ws]
            return MockScalarResult(filtered)

        # Handle Note queries
        if "from notes" in sql:
            filtered = list(self.db.notes.values())
            if target_ws:
                filtered = [n for n in filtered if n.workspace_id == target_ws]
            return MockScalarResult(filtered)

        return MockScalarResult([])


# Global shared in-memory test DB instance
_test_db = InMemoryDB()


def make_jwt(user_id: UUID) -> str:
    return jwt.encode(
        {"sub": str(user_id)},
        settings.secret_key,
        algorithm=settings.jwt_algorithm,
    )


@pytest.fixture(autouse=True)
def clean_db():
    """Reset test database between test runs."""
    _test_db.clear()


@pytest.fixture
def workspace_a_id() -> UUID:
    return uuid4()


@pytest.fixture
def workspace_b_id() -> UUID:
    return uuid4()


@pytest.fixture
def user_a_id() -> UUID:
    return uuid4()


@pytest.fixture
def user_b_id() -> UUID:
    return uuid4()


@pytest.fixture
def auth_headers_a(workspace_a_id: UUID, user_a_id: UUID) -> Dict[str, str]:
    token = make_jwt(user_a_id)
    return {
        "Authorization": f"Bearer {token}",
        "X-Workspace-Id": str(workspace_a_id),
    }


@pytest.fixture
def auth_headers_b(workspace_b_id: UUID, user_b_id: UUID) -> Dict[str, str]:
    token = make_jwt(user_b_id)
    return {
        "Authorization": f"Bearer {token}",
        "X-Workspace-Id": str(workspace_b_id),
    }


@pytest.fixture
def auth_headers(auth_headers_a: Dict[str, str]) -> Dict[str, str]:
    return auth_headers_a


@pytest.fixture
def session() -> FakeAsyncSession:
    return FakeAsyncSession(_test_db)


async def _override_get_public_session():
    yield FakeAsyncSession(_test_db)


async def _override_get_db_session():
    yield FakeAsyncSession(_test_db)


async def _override_get_current_user(
    authorization: Optional[str] = Header(None, alias="Authorization"),
) -> User:
    user_id = uuid4()
    if authorization and authorization.startswith("Bearer "):
        token = authorization[7:].strip()
        try:
            payload = jwt.decode(token, settings.secret_key, algorithms=[settings.jwt_algorithm])
            user_id = UUID(payload["sub"])
        except Exception:
            pass
    return User(
        id=user_id,
        email=f"user_{user_id}@personal-os.local",
        full_name="Test User",
        is_active=True,
        status="active",
    )


async def _override_get_workspace(
    workspace_id_header: Optional[str] = Header(None, alias="X-Workspace-Id"),
    user: User = Depends(_override_get_current_user),
) -> Workspace:
    ws_id = UUID(workspace_id_header) if workspace_id_header else uuid4()
    return Workspace(
        id=ws_id,
        name=f"Workspace {ws_id}",
        slug=f"workspace-{ws_id}",
        owner_id=user.id,
        plan="free",
        plan_tier="free",
        settings={},
    )


@pytest.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    app.dependency_overrides[get_public_session] = _override_get_public_session
    app.dependency_overrides[get_db_session] = _override_get_db_session
    app.dependency_overrides[get_current_user] = _override_get_current_user
    app.dependency_overrides[get_workspace] = _override_get_workspace

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c

    app.dependency_overrides.clear()


@pytest.fixture
async def client_a(client: AsyncClient) -> AsyncClient:
    return client


@pytest.fixture
async def client_b(client: AsyncClient) -> AsyncClient:
    return client


@pytest.fixture
async def created_task(client: AsyncClient, auth_headers: Dict[str, str]) -> Dict[str, Any]:
    payload = {"title": "Base test task", "priority": "medium"}
    r = await client.post("/v1/tasks", json=payload, headers=auth_headers)
    assert r.status_code == 201
    return r.json()


@pytest.fixture
async def posted_transaction(client: AsyncClient, auth_headers: Dict[str, str]) -> Dict[str, Any]:
    acc_r = await client.post(
        "/v1/finance/accounts",
        json={"name": "Checking", "currency": "RUB"},
        headers=auth_headers,
    )
    account = acc_r.json()
    tx_r = await client.post(
        "/v1/finance/transactions",
        json={
            "account_id": account["id"],
            "amount_minor": 5000,
            "currency": "RUB",
            "transaction_type": "income",
        },
        headers=auth_headers,
    )
    return tx_r.json()
