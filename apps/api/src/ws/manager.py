"""WebSocket ConnectionManager handling multi-tenant live connections and fan-out broadcasts."""

import json
import logging
from collections import defaultdict
from typing import Any, Dict, List
from uuid import UUID

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class ConnectionManager:
    """Manages active WebSocket connections grouped by workspace_id."""

    def __init__(self):
        self._connections: Dict[UUID, List[WebSocket]] = defaultdict(list)

    async def connect(self, ws: WebSocket, workspace_id: UUID) -> None:
        """Accept connection and register under tenant workspace."""
        await ws.accept()
        self._connections[workspace_id].append(ws)
        logger.info("WebSocket connected for workspace %s (active: %d)", workspace_id, len(self._connections[workspace_id]))

    def disconnect(self, ws: WebSocket, workspace_id: UUID) -> None:
        """Unregister connection on disconnect."""
        if workspace_id in self._connections:
            if ws in self._connections[workspace_id]:
                self._connections[workspace_id].remove(ws)
            if not self._connections[workspace_id]:
                del self._connections[workspace_id]
        logger.info("WebSocket disconnected for workspace %s", workspace_id)

    async def send_personal_message(self, ws: WebSocket, message: Dict[str, Any]) -> None:
        """Send message directly to a specific socket."""
        try:
            await ws.send_text(json.dumps(message))
        except Exception as e:
            logger.warning("Failed to send direct WebSocket message: %s", e)

    async def broadcast_to_workspace(self, workspace_id: UUID, event: Dict[str, Any]) -> None:
        """Broadcast domain event to all connected clients in a workspace."""
        if workspace_id not in self._connections:
            return

        dead_connections: List[WebSocket] = []
        payload = json.dumps(event)

        for ws in self._connections[workspace_id]:
            try:
                await ws.send_text(payload)
            except Exception as ex:
                logger.warning("Failed broadcast to client in workspace %s: %s", workspace_id, ex)
                dead_connections.append(ws)

        for ws in dead_connections:
            self.disconnect(ws, workspace_id)


ws_manager = ConnectionManager()
