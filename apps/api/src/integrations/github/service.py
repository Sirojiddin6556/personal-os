"""GitHub Integration domain service."""

import base64
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID, uuid4

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domains.projects.models import Project
from src.domains.tasks.models import Task, TaskPriority, TaskStatus
from src.integrations.crypto import AESGCMCryptoService
from src.integrations.github.client import GitHubClient
from src.integrations.models import ExternalMapping, Integration, OAuthCredential
from src.shared.exceptions import NotFoundError
from src.shared.outbox import publish_event


class GitHubService:
    """Business operations for GitHub integration, repositories, commits, and project tasks."""

    PROVIDER = "github"

    def __init__(self):
        self.crypto = AESGCMCryptoService()

    async def _get_integration(self, session: AsyncSession, workspace_id: UUID) -> Optional[Integration]:
        stmt = select(Integration).where(
            Integration.workspace_id == workspace_id,
            Integration.provider == self.PROVIDER,
        )
        res = await session.execute(stmt)
        return res.scalar_one_or_none()

    async def get_client(self, session: AsyncSession, workspace_id: UUID) -> GitHubClient:
        """Instantiate an authenticated GitHub client for the workspace."""
        integration = await self._get_integration(session, workspace_id)
        if not integration or integration.status != "connected":
            raise ValueError("Интеграция с GitHub не подключена. Пожалуйста, подключите GitHub токен в настройках.")

        stmt = select(OAuthCredential).where(OAuthCredential.integration_id == integration.id)
        res = await session.execute(stmt)
        cred = res.scalar_one_or_none()
        if not cred:
            raise ValueError("Учетные данные GitHub не найдены.")

        token = self.crypto.decrypt_token(cred)
        return GitHubClient(token=token)

    async def connect_github(self, session: AsyncSession, workspace_id: UUID, token: str) -> Dict[str, Any]:
        """Validate personal access token, save integration and encrypted credentials."""
        client = GitHubClient(token=token)
        user_info = await client.get_current_user()

        # Check existing integration
        integration = await self._get_integration(session, workspace_id)
        now = datetime.now(timezone.utc)

        if not integration:
            integration = Integration(
                id=uuid4(),
                workspace_id=workspace_id,
                provider=self.PROVIDER,
                status="connected",
                config={
                    "login": user_info.get("login"),
                    "name": user_info.get("name"),
                    "avatar_url": user_info.get("avatar_url"),
                    "html_url": user_info.get("html_url"),
                    "public_repos": user_info.get("public_repos", 0),
                },
                last_synced_at=now,
                sync_error=None,
            )
            session.add(integration)
            await session.flush()
        else:
            integration.status = "connected"
            integration.config = {
                "login": user_info.get("login"),
                "name": user_info.get("name"),
                "avatar_url": user_info.get("avatar_url"),
                "html_url": user_info.get("html_url"),
                "public_repos": user_info.get("public_repos", 0),
            }
            integration.last_synced_at = now
            integration.sync_error = None

        # Encrypt token with AES-256-GCM
        enc = self.crypto.encrypt_token(token)

        # Upsert OAuthCredential
        stmt = select(OAuthCredential).where(OAuthCredential.integration_id == integration.id)
        res = await session.execute(stmt)
        cred = res.scalar_one_or_none()

        if not cred:
            cred = OAuthCredential(
                id=uuid4(),
                workspace_id=workspace_id,
                integration_id=integration.id,
                encrypted_access_token=enc["ciphertext"],
                iv_access=enc["iv"],
                tag_access=enc["tag"],
                key_version=1,
            )
            session.add(cred)
        else:
            cred.encrypted_access_token = enc["ciphertext"]
            cred.iv_access = enc["iv"]
            cred.tag_access = enc["tag"]

        await publish_event(
            session=session,
            event_type="integration.github.connected.v1",
            aggregate_type="integration",
            aggregate_id=integration.id,
            workspace_id=workspace_id,
            data={"login": user_info.get("login")},
        )
        await session.commit()
        return {
            "status": "connected",
            "user": integration.config,
            "last_synced_at": now.isoformat(),
        }

    async def get_github_status(self, session: AsyncSession, workspace_id: UUID) -> Dict[str, Any]:
        """Return status and linked GitHub user info."""
        integration = await self._get_integration(session, workspace_id)
        if not integration or integration.status != "connected":
            return {"status": "disconnected", "user": None}

        return {
            "status": "connected",
            "user": integration.config,
            "last_synced_at": integration.last_synced_at.isoformat() if integration.last_synced_at else None,
            "sync_error": integration.sync_error,
        }

    async def disconnect_github(self, session: AsyncSession, workspace_id: UUID) -> None:
        """Remove GitHub integration and credentials."""
        integration = await self._get_integration(session, workspace_id)
        if integration:
            await session.delete(integration)
            await session.commit()

    async def list_repositories(self, session: AsyncSession, workspace_id: UUID) -> List[Dict[str, Any]]:
        """List GitHub repositories accessible to user."""
        client = await self.get_client(session, workspace_id)
        repos = await client.list_user_repos()
        return [
            {
                "id": r.get("id"),
                "name": r.get("name"),
                "full_name": r.get("full_name"),
                "description": r.get("description"),
                "private": r.get("private", False),
                "html_url": r.get("html_url"),
                "default_branch": r.get("default_branch", "main"),
                "language": r.get("language"),
                "stargazers_count": r.get("stargazers_count", 0),
                "updated_at": r.get("updated_at"),
            }
            for r in repos
        ]

    async def import_repository_as_project(
        self,
        session: AsyncSession,
        workspace_id: UUID,
        repo_full_name: str,
        name: Optional[str] = None,
        color: Optional[str] = "#3B82F6",
    ) -> Project:
        """Import a GitHub repo into Personal OS Projects."""
        client = await self.get_client(session, workspace_id)
        parts = repo_full_name.split("/")
        if len(parts) != 2:
            raise ValueError("Неверный формат репозитория. Ожидается: owner/repo")
        owner, repo_name = parts

        repo_data = await client.get_repo(owner, repo_name)
        project_name = name or repo_data.get("name", repo_name)
        description = repo_data.get("description")
        default_branch = repo_data.get("default_branch", "main")

        # Create or update project
        project = Project(
            id=uuid4(),
            workspace_id=workspace_id,
            name=project_name,
            description=description,
            color=color or "#3B82F6",
            icon="github",
            status="active",
            github_repo=repo_full_name,
            github_default_branch=default_branch,
        )
        session.add(project)
        await session.flush()

        # External mapping
        integration = await self._get_integration(session, workspace_id)
        if integration:
            mapping = ExternalMapping(
                id=uuid4(),
                workspace_id=workspace_id,
                integration_id=integration.id,
                entity_type="project",
                internal_id=project.id,
                external_id=repo_full_name,
                last_synced_at=datetime.now(timezone.utc),
            )
            session.add(mapping)

        await publish_event(
            session=session,
            event_type="project.github_imported.v1",
            aggregate_type="project",
            aggregate_id=project.id,
            workspace_id=workspace_id,
            data={"repo": repo_full_name, "name": project.name},
        )
        await session.commit()
        await session.refresh(project)
        return project

    def _parse_repo_from_project(self, project: Project) -> Tuple[str, str, str]:
        if not project.github_repo:
            raise ValueError(f"Проект '{project.name}' не привязан к GitHub-репозиторию.")
        parts = project.github_repo.split("/")
        if len(parts) != 2:
            raise ValueError(f"Неверный формат github_repo: {project.github_repo}")
        return parts[0], parts[1], project.github_default_branch or "main"

    async def get_project_commits(
        self, session: AsyncSession, workspace_id: UUID, project_id: UUID, branch: Optional[str] = None, limit: int = 20
    ) -> List[Dict[str, Any]]:
        """Get recent git commits for a connected project."""
        stmt = select(Project).where(Project.id == project_id, Project.workspace_id == workspace_id)
        res = await session.execute(stmt)
        project = res.scalar_one_or_none()
        if not project:
            raise NotFoundError("Project", project_id)

        owner, repo, default_branch = self._parse_repo_from_project(project)
        client = await self.get_client(session, workspace_id)
        commits_data = await client.list_commits(owner, repo, branch=branch or default_branch, limit=limit)

        results = []
        for c in commits_data:
            commit_obj = c.get("commit", {})
            author_obj = commit_obj.get("author", {})
            results.append({
                "sha": c.get("sha"),
                "short_sha": (c.get("sha") or "")[:7],
                "message": commit_obj.get("message"),
                "author_name": author_obj.get("name"),
                "author_email": author_obj.get("email"),
                "date": author_obj.get("date"),
                "html_url": c.get("html_url"),
            })
        return results

    async def get_project_contents(
        self, session: AsyncSession, workspace_id: UUID, project_id: UUID, path: str = "", ref: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Get directory tree or contents in a connected project."""
        stmt = select(Project).where(Project.id == project_id, Project.workspace_id == workspace_id)
        res = await session.execute(stmt)
        project = res.scalar_one_or_none()
        if not project:
            raise NotFoundError("Project", project_id)

        owner, repo, default_branch = self._parse_repo_from_project(project)
        client = await self.get_client(session, workspace_id)
        contents = await client.get_contents(owner, repo, path=path, ref=ref or default_branch)

        if isinstance(contents, list):
            return [
                {
                    "name": item.get("name"),
                    "path": item.get("path"),
                    "type": item.get("type"),  # 'file' | 'dir'
                    "size": item.get("size", 0),
                    "sha": item.get("sha"),
                    "html_url": item.get("html_url"),
                }
                for item in contents
            ]
        elif isinstance(contents, dict):
            # Single file
            return [
                {
                    "name": contents.get("name"),
                    "path": contents.get("path"),
                    "type": contents.get("type", "file"),
                    "size": contents.get("size", 0),
                    "sha": contents.get("sha"),
                    "html_url": contents.get("html_url"),
                }
            ]
        return []

    async def get_project_file(
        self, session: AsyncSession, workspace_id: UUID, project_id: UUID, path: str, ref: Optional[str] = None
    ) -> Dict[str, Any]:
        """Fetch file text content and current SHA for editing."""
        stmt = select(Project).where(Project.id == project_id, Project.workspace_id == workspace_id)
        res = await session.execute(stmt)
        project = res.scalar_one_or_none()
        if not project:
            raise NotFoundError("Project", project_id)

        owner, repo, default_branch = self._parse_repo_from_project(project)
        client = await self.get_client(session, workspace_id)
        data = await client.get_contents(owner, repo, path=path, ref=ref or default_branch)

        if isinstance(data, list) or data.get("type") != "file":
            raise ValueError(f"Путь '{path}' является директорией, а не файлом.")

        encoded_content = data.get("content", "")
        encoding = data.get("encoding", "base64")
        if encoding == "base64" and encoded_content:
            decoded_text = base64.b64decode(encoded_content).decode("utf-8", errors="replace")
        else:
            decoded_text = encoded_content

        return {
            "name": data.get("name"),
            "path": data.get("path"),
            "sha": data.get("sha"),
            "size": data.get("size"),
            "content": decoded_text,
            "html_url": data.get("html_url"),
        }

    async def create_commit(
        self,
        session: AsyncSession,
        workspace_id: UUID,
        project_id: UUID,
        path: str,
        content: str,
        commit_message: str,
        branch: Optional[str] = None,
        sha: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Create a commit on GitHub repository modifying or creating a file."""
        stmt = select(Project).where(Project.id == project_id, Project.workspace_id == workspace_id)
        res = await session.execute(stmt)
        project = res.scalar_one_or_none()
        if not project:
            raise NotFoundError("Project", project_id)

        owner, repo, default_branch = self._parse_repo_from_project(project)
        target_branch = branch or default_branch or "main"
        client = await self.get_client(session, workspace_id)

        # If sha is not provided, try to fetch current sha if file exists
        if not sha:
            try:
                existing = await client.get_contents(owner, repo, path=path, ref=target_branch)
                if isinstance(existing, dict) and "sha" in existing:
                    sha = existing["sha"]
            except Exception:
                sha = None

        commit_res = await client.create_or_update_file(
            owner=owner,
            repo=repo,
            path=path,
            content=content,
            commit_message=commit_message,
            branch=target_branch,
            sha=sha,
        )

        commit_info = commit_res.get("commit", {})
        return {
            "success": True,
            "commit_sha": commit_info.get("sha"),
            "short_sha": (commit_info.get("sha") or "")[:7],
            "message": commit_message,
            "path": path,
            "html_url": commit_info.get("html_url"),
        }

    async def sync_project_issues_as_tasks(
        self, session: AsyncSession, workspace_id: UUID, project_id: UUID
    ) -> List[Task]:
        """Import open GitHub issues as local Tasks under this project."""
        stmt = select(Project).where(Project.id == project_id, Project.workspace_id == workspace_id)
        res = await session.execute(stmt)
        project = res.scalar_one_or_none()
        if not project:
            raise NotFoundError("Project", project_id)

        owner, repo, _ = self._parse_repo_from_project(project)
        client = await self.get_client(session, workspace_id)
        issues = await client.list_issues(owner, repo, state="open", limit=30)

        imported_tasks: List[Task] = []
        for iss in issues:
            # Skip pull requests (which GitHub returns in issues endpoint if 'pull_request' key is present)
            if "pull_request" in iss:
                continue

            issue_title = f"[#{iss.get('number')}] {iss.get('title')}"
            issue_body = iss.get("body") or ""
            issue_url = iss.get("html_url")

            desc = f"{issue_body}\n\nGitHub Issue: {issue_url}".strip()

            # Check if task already exists
            existing_task_stmt = select(Task).where(
                Task.workspace_id == workspace_id,
                Task.project_id == project_id,
                Task.title == issue_title,
                Task.is_deleted.is_(False),
            )
            existing_res = await session.execute(existing_task_stmt)
            if existing_res.scalar_one_or_none():
                continue

            task = Task(
                id=uuid4(),
                workspace_id=workspace_id,
                project_id=project_id,
                title=issue_title,
                description=desc,
                status=TaskStatus.TODO,
                priority=TaskPriority.MEDIUM,
                version=1,
            )
            session.add(task)
            imported_tasks.append(task)

        if imported_tasks:
            await session.commit()
            for t in imported_tasks:
                await session.refresh(t)

        return imported_tasks


github_service = GitHubService()
