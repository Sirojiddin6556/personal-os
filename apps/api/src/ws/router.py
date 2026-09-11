"""WebSocket endpoint for real-time domain event streaming."""

import json
import logging
from uuid import UUID

import jwt
from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect
from sqlalchemy import select

from src.config import settings
from src.db.session import async_session_factory
from src.domains.identity.models import Membership
from src.ws.manager import ws_manager

logger = logging.getLogger(__name__)

router = APIRouter(tags=["websocket"])


@router.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    token: str = Query(..., description="JWT Bearer token"),
    workspace_id: UUID = Query(..., description="Target workspace ID"),
):
    """Authenticate and connect client to real-time tenant event stream."""
    # 1. Validate JWT Token
    try:
        payload = jwt.decode(
            token,
            settings.secret_key,
            algorithms=[settings.jwt_algorithm],
        )
        user_id = UUID(payload["sub"])
    except Exception as ex:
        logger.warning("WebSocket authentication failed: %s", ex)
        await websocket.close(code=4001, reason="Unauthorized")
        return

    # 2. Verify workspace membership
    async with async_session_factory() as session:
        stmt = select(Membership).where(
            Membership.workspace_id == workspace_id,
            Membership.user_id == user_id,
            Membership.status == "active",
        )
        res = await session.execute(stmt)
        if not res.scalar_one_or_none():
            logger.warning("User %s has no active membership in workspace %s", user_id, workspace_id)
            await websocket.close(code=4003, reason="Forbidden")
            return

    # 3. Connect and loop
    await ws_manager.connect(websocket, workspace_id)
    try:
        await ws_manager.send_personal_message(
            websocket,
            {"type": "connected", "workspace_id": str(workspace_id), "user_id": str(user_id)},
        )
        while True:
            data_text = await websocket.receive_text()
            try:
                msg = json.loads(data_text)
                if msg.get("type") == "ping":
                    await websocket.send_text(json.dumps({"type": "pong"}))
            except Exception:
                pass
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket, workspace_id)
    except Exception as ex:
        logger.error("WebSocket runtime error: %s", ex)
        ws_manager.disconnect(websocket, workspace_id)
