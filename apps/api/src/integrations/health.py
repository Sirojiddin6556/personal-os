"""Integration health for the morning digest: background syncs fail quietly (only a log line),
so anything that stopped working is listed for the user instead.

Found on 2026-11-16: Uzcard notices had stopped for five days because the card bot failed an
identity check after a restart; nothing told the user.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.integrations.models import Integration, SyncState

CALENDAR_STALE = timedelta(hours=2)  # syncs every 15 minutes
GITHUB_STALE = timedelta(hours=3)  # syncs every 30 minutes
BANK_QUIET = timedelta(days=7)

NAMES = {
    "google_calendar": "Google Календарь",
    "github": "GitHub",
    "telegram_user": "Аккаунт Telegram (уведомления банка)",
}
BANKS = {"humo": "HUMO", "uzcard": "Uzcard"}


@dataclass
class IntegrationState:
    provider: str
    status: str
    sync_error: Optional[str]
    config: Dict
    last_synced_at: Optional[datetime]


def _ago(delta: timedelta) -> str:
    hours = int(delta.total_seconds() // 3600)
    return f"{hours} ч" if hours < 48 else f"{hours // 24} дн."


def describe(states: List[IntegrationState], last_notice_at: Optional[datetime], now: datetime) -> List[str]:
    """One line per problem; empty when everything works."""
    out: List[str] = []
    for st in states:
        if st.provider not in NAMES:
            continue
        name = NAMES[st.provider]
        if st.status == "error" or st.sync_error:
            out.append(f"• {name}: {st.sync_error or 'ошибка подключения'}")
            continue
        if st.status != "connected":
            continue
        if st.provider == "telegram_user":
            lost = sorted(set((st.config or {}).get("last_ids") or {}) - set((st.config or {}).get("sources") or []))
            for bank in lost:
                out.append(f"• Бот {BANKS.get(bank, bank)} больше не читается — покупки по карте не записываются")
        elif st.provider == "google_calendar":
            if st.last_synced_at is None or now - st.last_synced_at > CALENDAR_STALE:
                when = f"{_ago(now - st.last_synced_at)} назад" if st.last_synced_at else "ни разу"
                out.append(f"• {name}: синхронизация была {when}")
        elif st.provider == "github":
            if st.last_synced_at is not None and now - st.last_synced_at > GITHUB_STALE:
                out.append(f"• {name}: задачи не обновлялись {_ago(now - st.last_synced_at)}")
    listening = any(
        st.provider == "telegram_user" and st.status == "connected" and (st.config or {}).get("sources")
        for st in states
    )
    if listening and last_notice_at is not None and now - last_notice_at > BANK_QUIET:
        out.append(
            f"• Уведомлений от банка не было {_ago(now - last_notice_at)} — проверьте в боте карты, "
            "что пакет уведомлений активен"
        )
    return out


async def problems(s: AsyncSession, ws: UUID, now: datetime) -> List[str]:
    from src.domains.finance.models import BankNotice

    integs = (await s.execute(select(Integration).where(Integration.workspace_id == ws))).scalars().all()
    calendar_synced = (await s.execute(
        select(func.max(SyncState.last_synced_at)).where(SyncState.workspace_id == ws,
                                                         SyncState.provider == "google_calendar")
    )).scalar_one_or_none()
    states = [
        IntegrationState(
            provider=i.provider,
            status=i.status,
            sync_error=i.sync_error,
            config=dict(i.config or {}),
            last_synced_at=calendar_synced if i.provider == "google_calendar" else i.last_synced_at,
        )
        for i in integs
    ]
    last_notice = (await s.execute(
        select(func.max(BankNotice.created_at)).where(BankNotice.workspace_id == ws)
    )).scalar_one_or_none()
    return describe(states, last_notice, now)
