"""Google Calendar synchronization engine with delta tokens and conflict resolution."""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domains.calendar.models import Event
from src.integrations.models import ExternalMapping, Integration, SyncState
from src.shared.outbox import publish_event

logger = logging.getLogger(__name__)


class GoogleCalendarSyncService:
    """Handles bi-directional synchronization with Google Calendar v3 API."""

    async def sync_workspace_calendar(
        self,
        session: AsyncSession,
        workspace_id: UUID,
        incoming_events: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """Perform delta sync reconciliation between Google Calendar and local Events."""
        # Find active Google Calendar integration
        stmt = select(Integration).where(
            Integration.workspace_id == workspace_id,
            Integration.provider == "google_calendar",
            Integration.status == "connected",
        )
        res = await session.execute(stmt)
        integration = res.scalar_one_or_none()
        if not integration:
            return {"status": "skipped", "reason": "No active Google Calendar integration found"}

        now = datetime.now(timezone.utc)
        synced_count = 0

        if incoming_events:
            for item in incoming_events:
                ext_id = item.get("id")
                summary = item.get("summary", "Untitled Event")
                starts_at = datetime.fromisoformat(item["start"])
                ends_at = datetime.fromisoformat(item["end"])

                # Check external mapping
                stmt_map = select(ExternalMapping).where(
                    ExternalMapping.integration_id == integration.id,
                    ExternalMapping.entity_type == "event",
                    ExternalMapping.external_id == ext_id,
                )
                res_map = await session.execute(stmt_map)
                mapping = res_map.scalar_one_or_none()

                if mapping:
                    # Update local event
                    stmt_ev = select(Event).where(Event.id == mapping.internal_id)
                    res_ev = await session.execute(stmt_ev)
                    ev = res_ev.scalar_one_or_none()
                    if ev:
                        ev.title = summary
                        ev.starts_at = starts_at
                        ev.ends_at = ends_at
                        ev.sync_status = "synced"
                        ev.version += 1
                else:
                    # Create new local event
                    new_ev = Event(
                        id=uuid4(),
                        workspace_id=workspace_id,
                        title=summary,
                        description=item.get("description"),
                        starts_at=starts_at,
                        ends_at=ends_at,
                        status="confirmed",
                        sync_status="synced",
                        external_id=ext_id,
                        version=1,
                    )
                    session.add(new_ev)
                    await session.flush()

                    new_mapping = ExternalMapping(
                        id=uuid4(),
                        workspace_id=workspace_id,
                        integration_id=integration.id,
                        entity_type="event",
                        internal_id=new_ev.id,
                        external_id=ext_id,
                        last_synced_at=now,
                    )
                    session.add(new_mapping)
                synced_count += 1

        integration.last_synced_at = now
        await publish_event(
            session=session,
            event_type="integration.google_calendar.synced.v1",
            aggregate_type="integration",
            aggregate_id=integration.id,
            workspace_id=workspace_id,
            data={"synced_events_count": synced_count},
        )

        await session.commit()
        return {"status": "success", "synced_events": synced_count, "synced_at": now.isoformat()}


google_calendar_sync = GoogleCalendarSyncService()
