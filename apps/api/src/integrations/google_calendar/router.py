"""Google Calendar OAuth2 consent, channel webhook, and synchronization endpoints."""

import base64
import hashlib
import secrets
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional
from uuid import UUID, uuid4

import httpx
import jwt
from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, Query, Request, Response, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import settings
from src.db.session import set_tenant_context
from src.domains.identity.models import Workspace
from src.integrations.crypto import encrypt_token
from src.integrations.google_calendar.sync import (
    google_calendar_sync,
    run_full_sync,
    run_incremental_sync,
)
from src.integrations.models import Integration, OAuthCredential, WebhookSubscription
from src.shared.deps import get_db_session, get_public_session, get_workspace

router = APIRouter(prefix="/integrations/google", tags=["google-calendar"])


class GoogleSyncPayload(BaseModel):
    events: Optional[list[Dict[str, Any]]] = None


@router.get("/authorize")
@router.get("/auth-url")
async def authorize(
    workspace: Workspace = Depends(get_workspace),
) -> Dict[str, str]:
    """Generate Google OAuth URL with PKCE, offline access, and calendar scope.

    State payload is a cryptographically signed JWT containing workspace_id and code_verifier.
    """
    # 1. Generate PKCE code verifier and code challenge (RFC 7636)
    code_verifier = secrets.token_urlsafe(64)
    code_challenge_digest = hashlib.sha256(code_verifier.encode("utf-8")).digest()
    code_challenge = base64.urlsafe_b64encode(code_challenge_digest).decode("utf-8").replace("=", "")

    # 2. Embed workspace_id and code_verifier in signed state JWT
    state_payload = {
        "workspace_id": str(workspace.id),
        "code_verifier": code_verifier,
        "iat": int(time.time()),
        "exp": int(time.time()) + 600,  # 10 minutes validity
    }
    state = jwt.encode(state_payload, settings.secret_key, algorithm=settings.jwt_algorithm)

    client_id = settings.google_client_id or "google-client-id-dev"
    redirect_uri = settings.google_redirect_uri
    scopes = "https://www.googleapis.com/auth/calendar https://www.googleapis.com/auth/calendar.events"

    auth_url = (
        "https://accounts.google.com/o/oauth2/v2/auth?"
        f"client_id={client_id}&"
        f"redirect_uri={redirect_uri}&"
        "response_type=code&"
        f"scope={scopes}&"
        "access_type=offline&"
        "prompt=consent&"
        f"code_challenge={code_challenge}&"
        "code_challenge_method=S256&"
        f"state={state}"
    )

    return {"auth_url": auth_url}


@router.get("/callback")
async def callback(
    code: str,
    state: str,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_public_session),
) -> Dict[str, str]:
    """Verify state JWT, exchange authorization code for tokens, encrypt with AES-256-GCM, and launch full sync."""
    # 1. Verify signed state JWT
    try:
        payload = jwt.decode(state, settings.secret_key, algorithms=[settings.jwt_algorithm])
        workspace_id = UUID(payload["workspace_id"])
        code_verifier = payload.get("code_verifier")
    except Exception as ex:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid or expired OAuth state parameter: {str(ex)}",
        )

    await set_tenant_context(session, workspace_id)

    # 2. Exchange authorization code for tokens
    if code.startswith("mock-") or not settings.google_client_id:
        access_token = f"mock-access-token-{code}"
        refresh_token = f"mock-refresh-token-{code}"
        expires_in = 3600
    else:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                "https://oauth2.googleapis.com/token",
                data={
                    "code": code,
                    "client_id": settings.google_client_id,
                    "client_secret": settings.google_client_secret,
                    "redirect_uri": settings.google_redirect_uri,
                    "grant_type": "authorization_code",
                    "code_verifier": code_verifier,
                },
            )
            if resp.status_code != 200:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Google token exchange failed: {resp.text}",
                )
            tokens = resp.json()
            access_token = tokens["access_token"]
            refresh_token = tokens.get("refresh_token")
            expires_in = tokens.get("expires_in", 3600)

    # 3. Encrypt tokens with AES-256-GCM
    enc_access = encrypt_token(access_token)
    enc_refresh = encrypt_token(refresh_token) if refresh_token else None
    token_expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)

    # 4. Upsert Integration record
    stmt_integ = select(Integration).where(
        Integration.workspace_id == workspace_id,
        Integration.provider == "google_calendar",
    )
    res_integ = await session.execute(stmt_integ)
    integration = res_integ.scalar_one_or_none()

    if not integration:
        integration = Integration(
            id=uuid4(),
            workspace_id=workspace_id,
            provider="google_calendar",
            status="connected",
            config={},
        )
        session.add(integration)
        await session.flush()
    else:
        integration.status = "connected"
        integration.sync_error = None

    # 5. Upsert OAuthCredential with AES-256-GCM payload
    stmt_cred = select(OAuthCredential).where(OAuthCredential.integration_id == integration.id)
    res_cred = await session.execute(stmt_cred)
    cred = res_cred.scalar_one_or_none()

    if not cred:
        cred = OAuthCredential(
            id=uuid4(),
            workspace_id=workspace_id,
            integration_id=integration.id,
            encrypted_access_token=enc_access["combined"],
            iv_access=enc_access["iv"],
            tag_access=enc_access["tag"],
            encrypted_refresh_token=enc_refresh["combined"] if enc_refresh else None,
            iv_refresh=enc_refresh["iv"] if enc_refresh else None,
            tag_refresh=enc_refresh["tag"] if enc_refresh else None,
            token_expires_at=token_expires_at,
            key_version=1,
        )
        session.add(cred)
    else:
        cred.encrypted_access_token = enc_access["combined"]
        cred.iv_access = enc_access["iv"]
        cred.tag_access = enc_access["tag"]
        if enc_refresh:
            cred.encrypted_refresh_token = enc_refresh["combined"]
            cred.iv_refresh = enc_refresh["iv"]
            cred.tag_refresh = enc_refresh["tag"]
        cred.token_expires_at = token_expires_at

    await session.commit()

    # 6. Schedule full_sync background task
    background_tasks.add_task(run_full_sync, workspace_id)
    return {"status": "connected"}


@router.post("/webhook")
async def google_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    x_goog_channel_token: Optional[str] = Header(None, alias="X-Goog-Channel-Token"),
    x_goog_resource_state: Optional[str] = Header(None, alias="X-Goog-Resource-State"),
    x_goog_channel_id: Optional[str] = Header(None, alias="X-Goog-Channel-ID"),
    x_goog_resource_id: Optional[str] = Header(None, alias="X-Goog-Resource-ID"),
    session: AsyncSession = Depends(get_public_session),
) -> Response:
    """Google Calendar push notifications webhook. Returns fast ACK 200 (<500ms) and schedules incremental sync."""
    # 1. Verify channel token / channel ID
    workspace_id: Optional[UUID] = None

    if x_goog_channel_token:
        try:
            token_payload = jwt.decode(
                x_goog_channel_token,
                settings.secret_key,
                algorithms=[settings.jwt_algorithm],
            )
            workspace_id = UUID(token_payload.get("workspace_id"))
        except Exception:
            try:
                workspace_id = UUID(x_goog_channel_token)
            except Exception:
                pass

    if not workspace_id and x_goog_channel_id:
        stmt = select(WebhookSubscription).where(
            WebhookSubscription.external_channel_id == x_goog_channel_id,
            WebhookSubscription.provider == "google_calendar",
        )
        res = await session.execute(stmt)
        sub = res.scalar_one_or_none()
        if sub:
            workspace_id = sub.workspace_id

    # 2. Fast ACK 200 immediately
    if x_goog_resource_state == "sync":
        # Initial sync ping from Google upon channel creation
        return Response(status_code=200, content="OK")

    # 3. Add background incremental sync task
    if workspace_id:
        background_tasks.add_task(run_incremental_sync, workspace_id)

    return Response(status_code=200, content="OK")


@router.delete("/disconnect")
async def disconnect(
    workspace: Workspace = Depends(get_workspace),
    session: AsyncSession = Depends(get_db_session),
) -> Dict[str, str]:
    """Delete OAuth credentials, deactivate integration, and stop push channels."""
    stmt_integ = select(Integration).where(
        Integration.workspace_id == workspace.id,
        Integration.provider == "google_calendar",
    )
    res = await session.execute(stmt_integ)
    integration = res.scalar_one_or_none()

    if integration:
        integration.status = "disconnected"

        # Remove OAuth credentials
        stmt_cred = select(OAuthCredential).where(OAuthCredential.integration_id == integration.id)
        res_cred = await session.execute(stmt_cred)
        cred = res_cred.scalar_one_or_none()
        if cred:
            await session.delete(cred)

        # Remove Webhook subscriptions
        stmt_sub = select(WebhookSubscription).where(
            WebhookSubscription.integration_id == integration.id,
            WebhookSubscription.provider == "google_calendar",
        )
        res_sub = await session.execute(stmt_sub)
        for sub in res_sub.scalars().all():
            await session.delete(sub)

        await session.commit()

    return {"status": "disconnected"}


@router.post("/sync")
async def sync_calendar(
    body: GoogleSyncPayload,
    session: AsyncSession = Depends(get_db_session),
    workspace: Workspace = Depends(get_workspace),
) -> Dict[str, Any]:
    """Manual trigger sync route (supports inline test event payloads)."""
    return await google_calendar_sync.sync_workspace_calendar(
        session=session,
        workspace_id=workspace.id,
        incoming_events=body.events,
    )
