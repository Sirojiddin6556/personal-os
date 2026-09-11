"""FastAPI application factory, lifecycle events, middlewares and router registrations."""

import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Dict

from fastapi import FastAPI, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from src.config import settings
from src.db.session import engine
from src.domains.ai_advisor.router import router as ai_advisor_router
from src.domains.calendar.router import router as calendar_router
from src.domains.dashboard.router import router as dashboard_router
from src.domains.finance.router import router as finance_router
from src.domains.identity.router import router as identity_router
from src.domains.knowledge.router import router as knowledge_router
from src.domains.notifications.router import router as notifications_router
from src.domains.projects.router import (
    goals_router,
    milestones_router,
    router as projects_router,
)
from src.domains.tasks.router import kanban_router, router as tasks_router
from src.integrations.google_calendar.router import router as google_router
from src.integrations.telegram.router import router as telegram_router
from src.shared.exceptions import DomainError, domain_error_handler
from src.shared.outbox import outbox_relay
from src.ws.router import router as ws_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("personal_os.api")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application startup and graceful shutdown lifecycle."""
    logger.info("Starting up Personal OS API [%s]...", settings.environment)

    # 1. Check Database connection readiness
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        logger.info("Database connection verified successfully.")
    except Exception as ex:
        logger.warning("Database connection check failed during startup (offline/test mode?): %s", ex)

    # 2. Start background Outbox Relay worker
    try:
        await outbox_relay.start()
    except Exception as ex:
        logger.warning("Failed to start outbox relay: %s", ex)

    yield

    # Shutdown sequence
    logger.info("Shutting down Personal OS API...")
    try:
        await outbox_relay.stop()
    except Exception as ex:
        logger.warning("Error stopping outbox relay: %s", ex)

    await engine.dispose()
    logger.info("Cleanup completed. Engine disposed.")


def create_app() -> FastAPI:
    """Build and configure the FastAPI application instance."""
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description="Modular monolith REST and WebSocket API for Personal OS",
        lifespan=lifespan,
    )

    # 1. CORS Middleware
    origins = (
        settings.cors_origins
        if isinstance(settings.cors_origins, list)
        else [settings.cors_origins]
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["ETag", "Idempotency-Key", "X-Workspace-Id"],
    )

    # 2. RFC 9457 Problem Details Exception Handler
    app.add_exception_handler(DomainError, domain_error_handler)

    # 3. Health check route
    @app.get("/health", tags=["system"], status_code=status.HTTP_200_OK)
    async def health_check() -> Dict[str, str]:
        return {
            "status": "healthy",
            "app": settings.app_name,
            "version": settings.app_version,
            "environment": settings.environment,
        }

    # 4. Include Domain Routers with /v1 Prefix
    v1_prefix = settings.api_v1_prefix  # "/v1"

    app.include_router(identity_router, prefix=v1_prefix)
    app.include_router(tasks_router, prefix=v1_prefix)
    app.include_router(kanban_router, prefix=v1_prefix)
    app.include_router(projects_router, prefix=v1_prefix)
    app.include_router(goals_router, prefix=v1_prefix)
    app.include_router(milestones_router, prefix=v1_prefix)
    app.include_router(calendar_router, prefix=v1_prefix)
    app.include_router(finance_router, prefix=v1_prefix)
    app.include_router(knowledge_router, prefix=v1_prefix)
    app.include_router(notifications_router, prefix=v1_prefix)
    app.include_router(ai_advisor_router, prefix=v1_prefix)
    app.include_router(dashboard_router, prefix=v1_prefix)
    app.include_router(google_router, prefix=v1_prefix)
    app.include_router(telegram_router, prefix=v1_prefix)
    app.include_router(ws_router, prefix=v1_prefix)

    return app


app = create_app()
