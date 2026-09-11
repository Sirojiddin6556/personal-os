"""WebSocket router for live multi-tenant push notifications and synchronization."""

import logging
from typing import Optional, Tuple
from uuid import UUID

import jwt
from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect, status
from sqlalchemy import select

from src.config import settings
from src.db.session import async_session_factory
from src.domains.identity.models import Membership, User, Workspace
from src.ws.manager import ws_manager

logger = logging.getLogger(__name__)

router = APIRouter(tags=["websocket"])
manager = ws_manager


async def authenticate_ws(token: str, workspace_id: Optional[UUID] = None) -> Tuple[User, Workspace]:
    """Validate JWT token and verify user workspace membership."""
    user_id = None
    try:
        payload = jwt.decode(
            token,
            settings.secret_key,
            algorithms=[settings.jwt_algorithm],
        )
        if "sub" in payload:
            user_id = UUID(payload["sub"])
    except Exception as ex:
        if settings.environment != "development":
            logger.warning("WebSocket JWT validation failed: %s", ex)
            raise ValueError("Invalid authentication token")

    async with async_session_factory() as session:
        if user_id:
            user = await session.get(User, user_id)
            if user and user.is_active:
                stmt = (
                    select(Membership, Workspace)
                    .join(Workspace, Membership.workspace_id == Workspace.id)
                    .where(
                        Membership.user_id == user_id,
                        Membership.status == "active",
                    )
                )
                if workspace_id:
                    stmt = stmt.where(Membership.workspace_id == workspace_id)

                res = await session.execute(stmt)
                row = res.first()
                if row:
                    return user, row[1]

        if settings.environment == "development":
            from src.shared.deps import get_or_create_default_user, get_or_create_default_workspace
            user = await get_or_create_default_user(session)
            ws = await get_or_create_default_workspace(session, user)
            return user, ws

        raise ValueError("No active workspace membership found for user")


@router.websocket("/ws")
@router.websocket("/v1/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    token: str = Query(..., description="JWT Bearer token"),
    workspace_id: Optional[UUID] = Query(None, description="Optional target workspace ID"),
):
    """Real-time bi-directional WebSocket connection for tenant events."""
    try:
        user, workspace = await authenticate_ws(token, workspace_id)
    except Exception as ex:
        logger.warning("WebSocket authentication failed: %s", ex)
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Unauthorized")
        return

    await manager.connect(websocket, workspace.id)
    try:
        await manager.send_personal_message(
            websocket,
            {
                "type": "connected",
                "workspace_id": str(workspace.id),
                "user_id": str(user.id),
            },
        )
        while True:
            data = await websocket.receive_json()
            if data.get("type") == "ping":
                await websocket.send_json({"type": "pong"})
    except WebSocketDisconnect:
        manager.disconnect(websocket, workspace.id)
    except Exception as ex:
        logger.error("WebSocket runtime error: %s", ex)
        manager.disconnect(websocket, workspace.id)
