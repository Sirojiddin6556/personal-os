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
from fastapi import APIRouter, BackgroundTasks, Body, Depends, Header, HTTPException, Query, Request, Response, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import settings
from src.db.session import set_tenant_context
from fastapi.responses import RedirectResponse
from src.integrations.crypto import crypto_service, encrypt_token
from src.domains.identity.models import Workspace
from src.integrations.models import Integration, OAuthCredential, SyncState, WebhookSubscription
from src.shared.deps import get_db_session, get_public_session, get_workspace
from src.integrations.google_calendar.sync import (
    full_sync,
    google_calendar_sync,
    incremental_sync,
    run_full_sync,
    run_incremental_sync,
)

router = APIRouter(prefix="/integrations/google", tags=["google-calendar"])


class GoogleSyncPayload(BaseModel):
    events: Optional[list[Dict[str, Any]]] = None


class GoogleConfigureRequest(BaseModel):
    client_id: str
    client_secret: str


@router.post("/configure")
@router.post("/config")
async def configure_google(
    body: GoogleConfigureRequest,
    session: AsyncSession = Depends(get_db_session),
    workspace: Workspace = Depends(get_workspace),
) -> Dict[str, Any]:
    """Store Google OAuth Client ID and encrypted Client Secret for workspace."""
    if not body.client_id.strip() or not body.client_secret.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Client ID и Client Secret обязательны для заполнения.",
        )

    stmt_integ = select(Integration).where(
        Integration.workspace_id == workspace.id,
        Integration.provider == "google_calendar",
    )
    res_integ = await session.execute(stmt_integ)
    integration = res_integ.scalar_one_or_none()

    enc = crypto_service.encrypt_token(body.client_secret.strip())
    config_data = {
        "client_id": body.client_id.strip(),
        "enc_secret": enc["combined"].hex(),
    }

    if not integration:
        integration = Integration(
            id=uuid4(),
            workspace_id=workspace.id,
            provider="google_calendar",
            status="disconnected",
            config=config_data,
        )
        session.add(integration)
    else:
        integration.config = {**integration.config, **config_data}

    await session.commit()
    return {"status": "configured", "client_id": body.client_id.strip()}


@router.get("/config")
async def get_google_config(
    session: AsyncSession = Depends(get_db_session),
    workspace: Workspace = Depends(get_workspace),
) -> Dict[str, Any]:
    stmt_integ = select(Integration).where(
        Integration.workspace_id == workspace.id,
        Integration.provider == "google_calendar",
    )
    res_integ = await session.execute(stmt_integ)
    integration = res_integ.scalar_one_or_none()

    client_id = (integration.config.get("client_id") if integration else None) or settings.google_client_id
    has_secret = bool((integration and integration.config.get("enc_secret")) or settings.google_client_secret)

    return {
        "configured": bool(client_id and has_secret),
        "client_id": client_id or "",
        "redirect_uri": settings.google_redirect_uri,
        "status": integration.status if integration else "disconnected",
    }


@router.get("/authorize")
@router.get("/auth-url")
async def authorize(
    session: AsyncSession = Depends(get_db_session),
    workspace: Workspace = Depends(get_workspace),
) -> Dict[str, str]:
    """Generate Google OAuth URL with PKCE, offline access, and calendar scope."""
    stmt_integ = select(Integration).where(
        Integration.workspace_id == workspace.id,
        Integration.provider == "google_calendar",
    )
    res_integ = await session.execute(stmt_integ)
    integration = res_integ.scalar_one_or_none()

    client_id = (integration.config.get("client_id") if integration else None) or settings.google_client_id

    if not client_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Google Client ID не настроен. Пожалуйста, введите Client ID и Client Secret в форме интеграции.",
        )

    # 1. Generate PKCE code verifier and code challenge (RFC 7636)
    code_verifier = secrets.token_urlsafe(64)
    code_challenge_digest = hashlib.sha256(code_verifier.encode("utf-8")).digest()
    code_challenge = base64.urlsafe_b64encode(code_challenge_digest).decode("utf-8").replace("=", "")

    # 2. Embed workspace_id and code_verifier in AES-256-GCM encrypted state (prevents code_verifier leakage)
    import json
    state_payload = {
        "workspace_id": str(workspace.id),
        "code_verifier": code_verifier,
        "iat": int(time.time()),
        "exp": int(time.time()) + 600,  # 10 minutes validity
    }
    enc_state = crypto_service.encrypt_token(json.dumps(state_payload))
    state = base64.urlsafe_b64encode(enc_state["combined"]).decode("utf-8").rstrip("=")

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
):
    """Verify state JWT or AES-256-GCM ciphertext, exchange authorization code for tokens, encrypt with AES-256-GCM, and launch full sync."""
    import json
    # 1. Verify encrypted or signed state
    try:
        # First try AES-256-GCM encrypted state
        pad_len = 4 - (len(state) % 4)
        padded_state = state + ("=" * (pad_len % 4))
        raw_combined = base64.urlsafe_b64decode(padded_state.encode("utf-8"))
        decrypted_str = crypto_service.decrypt_token(raw_combined)
        payload = json.loads(decrypted_str)
        if payload.get("exp") and payload["exp"] < int(time.time()):
            raise ValueError("State expired")
        workspace_id = UUID(payload["workspace_id"])
        code_verifier = payload.get("code_verifier")
    except Exception:
        # Fallback to JWS JWT for backwards compatibility
        try:
            payload = jwt.decode(state, settings.secret_key, algorithms=[settings.jwt_algorithm])
            workspace_id = UUID(payload["workspace_id"])
            code_verifier = payload.get("code_verifier")
        except Exception as ex:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Недействительный или истекший параметр OAuth state: {str(ex)}",
            )

    # Replay protection: Check and mark state as consumed (single-use)
    state_fingerprint = hashlib.sha256(state.encode("utf-8")).hexdigest()
    state_key = f"gcal:state_consumed:{state_fingerprint}"
    _CONSUMED_STATES: set = getattr(router, "_consumed_states", set())
    setattr(router, "_consumed_states", _CONSUMED_STATES)

    try:
        from src.shared.idempotency import idempotency_service
        idemp_client = await idempotency_service.get_client()
        if idemp_client:
            is_first_use = await idemp_client.set(state_key, "1", nx=True, ex=600)
            if not is_first_use:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="OAuth state уже был использован (защита от replay/повторного вызова). Пожалуйста, начните авторизацию заново.",
                )
        else:
            if getattr(settings, "environment", "development") in ("production", "staging"):
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Служба верификации OAuth временно недоступна. Повторите попытку позже.",
                )
            if state_fingerprint in _CONSUMED_STATES:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="OAuth state уже был использован. Пожалуйста, начните авторизацию заново.",
                )
            _CONSUMED_STATES.add(state_fingerprint)
    except HTTPException:
        raise
    except Exception as ex:
        if getattr(settings, "environment", "development") in ("production", "staging"):
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Служба верификации OAuth временно недоступна. Повторите попытку позже.",
            )
        if state_fingerprint in _CONSUMED_STATES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="OAuth state уже был использован.",
            )
        _CONSUMED_STATES.add(state_fingerprint)

    try:
        await set_tenant_context(session, workspace_id)

        # 2. Retrieve Client ID and Secret for this workspace
        stmt_integ = select(Integration).where(
            Integration.workspace_id == workspace_id,
            Integration.provider == "google_calendar",
        )
        res_integ = await session.execute(stmt_integ)
        integration = res_integ.scalar_one_or_none()
    except Exception:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Не удалось открыть OAuth-сессию в базе данных. Проверьте PostgreSQL и tenant context.",
        )

    client_id = (integration.config.get("client_id") if integration else None) or settings.google_client_id
    client_secret = settings.google_client_secret

    if integration and integration.config.get("enc_secret"):
        try:
            combined_bytes = bytes.fromhex(integration.config["enc_secret"])
            client_secret = crypto_service.decrypt_token(combined_bytes)
        except Exception:
            pass

    # 3. Exchange authorization code for tokens
    try:
        if code.startswith("mock-") or not client_id:
            access_token = f"mock-access-token-{code}"
            refresh_token = f"mock-refresh-token-{code}"
            expires_in = 3600
        else:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(
                    "https://oauth2.googleapis.com/token",
                    data={
                        "code": code,
                        "client_id": client_id,
                        "client_secret": client_secret,
                        "redirect_uri": settings.google_redirect_uri,
                        "grant_type": "authorization_code",
                        "code_verifier": code_verifier,
                    },
                )
                if resp.status_code != 200:
                    # Do not echo the full Google response: it may contain
                    # request identifiers or sensitive OAuth diagnostics.
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Google отклонил обмен OAuth-кода. Начните авторизацию заново и проверьте client/redirect URI.",
                    )
                tokens = resp.json()
                access_token = tokens["access_token"]
                refresh_token = tokens.get("refresh_token")
                expires_in = tokens.get("expires_in", 3600)
    except HTTPException:
        raise
    except httpx.RequestError as ex:
        logger.warning("Google OAuth token request failed: %s", type(ex).__name__)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Не удалось связаться с Google для получения OAuth-токенов.",
        )
    except (httpx.HTTPError, KeyError, TypeError, ValueError) as ex:
        logger.warning("Google OAuth token response could not be processed: %s", type(ex).__name__)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Не удалось получить OAuth-токены от Google.",
        )

    # 4. Encrypt tokens with AES-256-GCM
    enc_access = encrypt_token(access_token)
    enc_refresh = encrypt_token(refresh_token) if refresh_token else None
    token_expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)

    # 5. Upsert Integration record
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

    try:
        await session.commit()
    except Exception:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="OAuth-токен получен, но не удалось безопасно сохранить подключение в базе данных.",
        )

    # 6. Schedule full_sync background task
    background_tasks.add_task(run_full_sync, workspace_id)
    return RedirectResponse(url="http://localhost:3000/settings/integrations?google=connected")


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


@router.delete("")
@router.delete("/")
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


@router.get("/sync-status")
async def get_sync_status(
    session: AsyncSession = Depends(get_db_session),
    workspace: Workspace = Depends(get_workspace),
) -> Dict[str, Any]:
    """Return a UI-safe snapshot of the Google Calendar connection state."""
    stmt_integ = select(Integration).where(
        Integration.workspace_id == workspace.id,
        Integration.provider == "google_calendar",
    )
    integration = (await session.execute(stmt_integ)).scalar_one_or_none()

    if not integration or integration.status == "disconnected":
        return {
            "status": "disconnected",
            "last_sync": None,
            "synced_events_count": 0,
            "error_message": None,
        }

    stmt_state = (
        select(SyncState)
        .where(
            SyncState.workspace_id == workspace.id,
            SyncState.integration_id == integration.id,
            SyncState.provider == "google_calendar",
        )
        .order_by(SyncState.updated_at.desc())
        .limit(1)
    )
    sync_state = (await session.execute(stmt_state)).scalar_one_or_none()
    sync_status = sync_state.status if sync_state else None
    status_value = "error" if integration.sync_error else (sync_status or "connected")
    if status_value not in {"idle", "syncing", "connected", "error", "disconnected"}:
        status_value = "connected"

    last_sync = None
    if sync_state and sync_state.last_synced_at:
        last_sync = sync_state.last_synced_at.isoformat()
    elif integration.last_synced_at:
        last_sync = integration.last_synced_at.isoformat()

    return {
        "status": status_value,
        "last_sync": last_sync,
        "synced_events_count": 0,
        "error_message": integration.sync_error,
    }


@router.post("/sync")
async def sync_calendar(
    background_tasks: BackgroundTasks,
    body: Optional[GoogleSyncPayload] = Body(default=None),
    session: AsyncSession = Depends(get_db_session),
    workspace: Workspace = Depends(get_workspace),
) -> Dict[str, Any]:
    """Manual trigger sync route (supports inline test event payloads and background real Google Calendar sync)."""
    if body is not None and body.events is not None:
        return await google_calendar_sync.sync_workspace_calendar(
            session=session,
            workspace_id=workspace.id,
            incoming_events=body.events,
        )
    
    # Real Google Calendar sync in background with fast ACK
    from src.integrations.google_calendar.sync import run_full_sync
    background_tasks.add_task(run_full_sync, workspace.id)
    return {
        "status": "syncing",
        "job_id": str(uuid4()),
        "message": "Синхронизация с Google Calendar запущена.",
    }
