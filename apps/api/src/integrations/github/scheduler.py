"""Periodic GitHub issues -> tasks for every project linked to a repository.

New open issues become tasks (and the linked Telegram chat hears about them), closed
issues close their task. One-way: nothing is written to GitHub.
"""

import asyncio
import logging
from typing import List, Optional, Tuple
from uuid import UUID

from sqlalchemy import select

from src.config import settings
from src.db.session import TENANT_INFO_KEY, async_session_factory, set_tenant_context
from src.domains.projects.models import Project
from src.integrations.github.service import github_service
from src.integrations.models import Integration

logger = logging.getLogger("personal_os.github")
MAX_LISTED = 7


def notice_text(created: List[Tuple[str, str]], closed: List[Tuple[str, str]]) -> str:
    """(project, task title) pairs -> one Telegram message."""
    out: List[str] = []
    if created:
        out.append(f"🐙 Новые задачи из GitHub: {len(created)}")
        out += [f"• {title} ({project})" for project, title in created[:MAX_LISTED]]
        if len(created) > MAX_LISTED:
            out.append(f"  …и ещё {len(created) - MAX_LISTED}")
    if closed:
        out.append(f"✅ Закрыты на GitHub: {len(closed)}")
        out += [f"• {title}" for _, title in closed[:MAX_LISTED]]
    return "\n".join(out)


async def connected_workspaces() -> List[UUID]:
    async with async_session_factory() as session:
        res = await session.execute(
            select(Integration.workspace_id)
            .where(Integration.provider == "github", Integration.status == "connected")
            .distinct()
        )
        return list(res.scalars().all())


async def sync_workspace(workspace_id: UUID, notify: bool = True) -> Tuple[int, int]:
    created: List[Tuple[str, str]] = []
    closed: List[Tuple[str, str]] = []
    async with async_session_factory() as session:
        session.sync_session.info[TENANT_INFO_KEY] = str(workspace_id)
        await set_tenant_context(session, workspace_id)
        client = await github_service.get_client(session, workspace_id)
        projects = (await session.execute(
            select(Project).where(Project.workspace_id == workspace_id, Project.github_repo.is_not(None),
                                  Project.status != "archived")
        )).scalars().all()
        for project in projects:
            try:
                result = await github_service.sync_issues(session, workspace_id, project, client)
                await session.commit()
            except asyncio.CancelledError:
                raise
            except Exception as ex:
                await session.rollback()
                logger.warning("GitHub issues sync failed for %s: %s", project.github_repo, ex)
                continue
            created += [(project.name, t.title) for t in result.created]
            closed += [(project.name, t.title) for t in result.closed]

        if notify and (created or closed):
            from src.integrations.telegram.handler import send_message
            from src.integrations.telegram.reminders import _chat_and_token

            integ = (await session.execute(
                select(Integration).where(Integration.workspace_id == workspace_id,
                                          Integration.provider == "telegram", Integration.status == "connected")
            )).scalars().first()
            chat, token = _chat_and_token(integ) if integ else (None, None)
            if chat:
                try:
                    await send_message(chat, notice_text(created, closed), bot_token=token)
                except Exception as ex:
                    logger.warning("GitHub sync notice not delivered: %s", ex)
    return len(created), len(closed)


async def sync_all() -> None:
    for workspace_id in await connected_workspaces():
        try:
            n_new, n_closed = await sync_workspace(workspace_id)
            if n_new or n_closed:
                logger.info("GitHub issues for %s: %d new, %d closed", workspace_id, n_new, n_closed)
        except asyncio.CancelledError:
            raise
        except Exception as ex:
            logger.warning("GitHub sync failed for workspace %s: %s", workspace_id, ex)


class GitHubIssuesScheduler:
    def __init__(self, interval: float):
        self.interval = interval
        self._task: Optional[asyncio.Task] = None

    async def start(self) -> None:
        if self.interval <= 0 or self._task is not None:
            return
        self._task = asyncio.create_task(self._loop())
        logger.info("GitHub issues auto-sync started (every %ss).", self.interval)

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None

    async def _loop(self) -> None:
        await asyncio.sleep(90)
        while True:
            try:
                await sync_all()
            except asyncio.CancelledError:
                raise
            except Exception as ex:
                logger.warning("GitHub sync pass failed: %s", ex)
            await asyncio.sleep(self.interval)


github_issues_scheduler = GitHubIssuesScheduler(settings.github_sync_interval_seconds)
