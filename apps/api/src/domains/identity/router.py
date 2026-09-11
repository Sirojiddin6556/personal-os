"""FastAPI router for Auth and Workspaces."""

from typing import List
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.domains.identity.models import User
from src.domains.identity.schemas import (
    TokenResponse,
    UserLoginRequest,
    UserRegisterRequest,
    UserResponse,
    WorkspaceCreateRequest,
    WorkspaceResponse,
)
from src.domains.identity.service import identity_service
from src.shared.deps import get_current_user, get_public_session

router = APIRouter(tags=["identity"])


@router.post(
    "/auth/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user account",
)
async def register(
    body: UserRegisterRequest,
    session: AsyncSession = Depends(get_public_session),
) -> UserResponse:
    user = await identity_service.register(session, body)
    return UserResponse.model_validate(user)


@router.post(
    "/auth/login",
    response_model=TokenResponse,
    summary="Authenticate and receive JWT token",
)
async def login(
    body: UserLoginRequest,
    session: AsyncSession = Depends(get_public_session),
) -> TokenResponse:
    return await identity_service.authenticate(session, body)


@router.get(
    "/auth/me",
    response_model=UserResponse,
    summary="Retrieve current user profile",
)
async def get_me(current_user: User = Depends(get_current_user)) -> UserResponse:
    return UserResponse.model_validate(current_user)


@router.post(
    "/workspaces",
    response_model=WorkspaceResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new workspace",
)
async def create_workspace(
    body: WorkspaceCreateRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_public_session),
) -> WorkspaceResponse:
    ws = await identity_service.create_workspace(session, current_user, body)
    return WorkspaceResponse.model_validate(ws)


@router.get(
    "/workspaces",
    response_model=List[WorkspaceResponse],
    summary="List all workspaces where current user is a member",
)
async def list_workspaces(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_public_session),
) -> List[WorkspaceResponse]:
    workspaces = await identity_service.list_user_workspaces(session, current_user)
    return [WorkspaceResponse.model_validate(w) for w in workspaces]
