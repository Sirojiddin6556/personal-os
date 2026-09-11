"""GitHub Integration FastAPI router."""

from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from src.domains.identity.models import Workspace
from src.domains.projects.schemas import ProjectResponse
from src.domains.tasks.schemas import TaskResponse
from src.integrations.github.service import github_service
from src.shared.deps import get_db_session, get_workspace

router = APIRouter(prefix="/integrations/github", tags=["github-integration"])


class GitHubConnectRequest(BaseModel):
    token: str = Field(min_length=1, description="GitHub Personal Access Token (classic or fine-grained)")


class GitHubImportRequest(BaseModel):
    repo_full_name: str = Field(min_length=3, description="Full repository name: owner/repo")
    name: Optional[str] = Field(default=None, description="Optional custom project name")
    color: Optional[str] = Field(default="#3B82F6", description="Project color hex")


class GitHubCommitRequest(BaseModel):
    path: str = Field(min_length=1, description="Relative file path in repository (e.g. src/index.ts)")
    content: str = Field(description="New file contents")
    commit_message: str = Field(min_length=1, max_length=500, description="Git commit message")
    branch: Optional[str] = Field(default=None, description="Target branch (defaults to project default branch)")
    sha: Optional[str] = Field(default=None, description="File blob SHA if updating existing file")


@router.post("/connect", summary="Connect GitHub Personal Access Token")
async def connect_github(
    body: GitHubConnectRequest,
    session: AsyncSession = Depends(get_db_session),
    workspace: Workspace = Depends(get_workspace),
) -> Dict[str, Any]:
    try:
        return await github_service.connect_github(session, workspace.id, body.token)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/status", summary="Get GitHub connection status and profile")
async def get_github_status(
    session: AsyncSession = Depends(get_db_session),
    workspace: Workspace = Depends(get_workspace),
) -> Dict[str, Any]:
    return await github_service.get_github_status(session, workspace.id)


@router.delete("", status_code=status.HTTP_204_NO_CONTENT, summary="Disconnect GitHub integration")
async def disconnect_github(
    session: AsyncSession = Depends(get_db_session),
    workspace: Workspace = Depends(get_workspace),
) -> None:
    await github_service.disconnect_github(session, workspace.id)


@router.get("/repos", summary="List user GitHub repositories")
async def list_repositories(
    session: AsyncSession = Depends(get_db_session),
    workspace: Workspace = Depends(get_workspace),
) -> List[Dict[str, Any]]:
    try:
        return await github_service.list_repositories(session, workspace.id)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/import", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED, summary="Import GitHub repository as Project")
async def import_repository(
    body: GitHubImportRequest,
    session: AsyncSession = Depends(get_db_session),
    workspace: Workspace = Depends(get_workspace),
) -> ProjectResponse:
    try:
        project = await github_service.import_repository_as_project(
            session=session,
            workspace_id=workspace.id,
            repo_full_name=body.repo_full_name,
            name=body.name,
            color=body.color,
        )
        return ProjectResponse.model_validate(project)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/projects/{project_id}/commits", summary="Get repository commits for project")
async def get_project_commits(
    project_id: UUID,
    branch: Optional[str] = Query(None, description="Optional branch name"),
    limit: int = Query(20, ge=1, le=50),
    session: AsyncSession = Depends(get_db_session),
    workspace: Workspace = Depends(get_workspace),
) -> List[Dict[str, Any]]:
    try:
        return await github_service.get_project_commits(session, workspace.id, project_id, branch, limit)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/projects/{project_id}/contents", summary="Get repository directory contents or file tree")
async def get_project_contents(
    project_id: UUID,
    path: str = Query("", description="Directory path inside repository"),
    ref: Optional[str] = Query(None, description="Branch, tag or commit SHA"),
    session: AsyncSession = Depends(get_db_session),
    workspace: Workspace = Depends(get_workspace),
) -> List[Dict[str, Any]]:
    try:
        return await github_service.get_project_contents(session, workspace.id, project_id, path, ref)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/projects/{project_id}/file", summary="Get file text content from repository")
async def get_project_file(
    project_id: UUID,
    path: str = Query(..., description="File path in repository"),
    ref: Optional[str] = Query(None, description="Branch or commit SHA"),
    session: AsyncSession = Depends(get_db_session),
    workspace: Workspace = Depends(get_workspace),
) -> Dict[str, Any]:
    try:
        return await github_service.get_project_file(session, workspace.id, project_id, path, ref)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/projects/{project_id}/commit", summary="Commit changes directly to GitHub repository")
async def create_project_commit(
    project_id: UUID,
    body: GitHubCommitRequest,
    session: AsyncSession = Depends(get_db_session),
    workspace: Workspace = Depends(get_workspace),
) -> Dict[str, Any]:
    try:
        return await github_service.create_commit(
            session=session,
            workspace_id=workspace.id,
            project_id=project_id,
            path=body.path,
            content=body.content,
            commit_message=body.commit_message,
            branch=body.branch,
            sha=body.sha,
        )
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/projects/{project_id}/sync-issues", response_model=List[TaskResponse], summary="Import open GitHub issues as project tasks")
async def sync_project_issues(
    project_id: UUID,
    session: AsyncSession = Depends(get_db_session),
    workspace: Workspace = Depends(get_workspace),
) -> List[TaskResponse]:
    try:
        tasks = await github_service.sync_project_issues_as_tasks(session, workspace.id, project_id)
        return [TaskResponse.model_validate(t) for t in tasks]
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
