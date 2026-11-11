import os
from typing import List, Union

DEV_SECRET_KEY = "personal-os-dev-super-secret-jwt-key-change-in-production-2026"
INSECURE_ENVIRONMENTS = ("development", "test")
from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables and .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_name: str = "Personal OS API"
    app_version: str = "1.0.0"
    # Safe default: dev-only conveniences (passwordless fallback user, auto-provisioned
    # workspace, default secret) are enabled ONLY when ENVIRONMENT=development is set explicitly.
    environment: str = "production"
    debug: bool = False
    api_v1_prefix: str = "/v1"

    # Database & Storage
    database_url: str = Field(
        default="postgresql+asyncpg://postgres:postgrespassword@localhost:5432/personal_os_dev",
        description="Asyncpg PostgreSQL connection URL",
    )
    redis_url: str = Field(
        default="redis://localhost:6379/0",
        description="Redis connection URL for caching and idempotency",
    )

    # Security & Auth
    secret_key: str = Field(
        default=DEV_SECRET_KEY,
        description="HMAC secret key for JWT signing",
    )
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 60 * 24  # 24 hours
    # New accounts (email sign-up and first Google sign-in). A self-hosted single-user
    # install turns this off; the very first account can always be created.
    allow_registration: bool = True

    # AI Providers
    openai_api_key: str = Field(default="", description="OpenAI API key")
    anthropic_api_key: str = Field(default="", description="Anthropic Claude API key")
    ai_default_model: str = "gpt-4o"

    # CORS
    cors_origins: Union[List[str], str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
        "http://localhost:8008",
        "http://127.0.0.1:8008",
    ]

    @field_validator("cors_origins", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> List[str]:
        if isinstance(v, str) and not v.startswith("["):
            return [i.strip() for i in v.split(",") if i.strip()]
        return v

    # Integrations
    google_client_id: str = ""
    google_client_secret: str = ""
    # The local web app uses the host API port 8008. Keep this default aligned
    # with the development environment so OAuth never generates a callback for
    # a different service/port when GOOGLE_REDIRECT_URI is omitted.
    google_redirect_uri: str = Field(
        default_factory=lambda: (
            f"{os.environ['RENDER_EXTERNAL_URL'].rstrip('/')}/v1/integrations/google/callback"
            if os.getenv("RENDER_EXTERNAL_URL")
            else "http://localhost:8008/v1/integrations/google/callback"
        )
    )
    # Where the web app lives (used for redirects back from OAuth flows).
    frontend_url: str = "http://localhost:3000"
    telegram_bot_token: str = ""
    telegram_webhook_secret: str = ""
    # Render sets RENDER_EXTERNAL_URL automatically, so webhooks work without extra config there.
    telegram_webhook_base_url: str = Field(default_factory=lambda: os.getenv("RENDER_EXTERNAL_URL", ""))
    # Telegram Mini App: max age of signed initData accepted by /auth/telegram
    telegram_init_data_max_age_seconds: int = 60 * 60 * 24
    # Public HTTPS URL of the Mini App (e.g. https://app.personal-os.com/tg/).
    # When set, connecting a bot also installs a menu button that opens it.
    telegram_miniapp_url: str = ""

    @model_validator(mode="after")
    def _require_strong_secret(self) -> "Settings":
        if self.environment not in INSECURE_ENVIRONMENTS and (
            self.secret_key == DEV_SECRET_KEY or len(self.secret_key) < 32
        ):
            raise ValueError(
                f"SECRET_KEY must be set to a random value of at least 32 characters "
                f"when ENVIRONMENT={self.environment!r} (e.g. `openssl rand -hex 32`)."
            )
        return self

    @property
    def is_development(self) -> bool:
        return self.environment == "development"

    # Timezone for times typed in the bot ("напомни в 19:00")
    default_timezone: str = "Asia/Tashkent"

    # Cloudflare Quick Tunnel metrics (e.g. http://tunnel:2000/quicktunnel). When set, the API
    # follows the changing *.trycloudflare.com URL and re-points the bots automatically.
    quick_tunnel_metrics_url: str = ""

    # Voice messages in Telegram, recognized locally with faster-whisper (no cloud).
    voice_enabled: bool = True
    voice_model: str = "small"  # tiny/base/small/medium: bigger = better and slower
    voice_model_dir: str = "models"  # relative to WORKDIR; keep it out of /app/data (backups)
    voice_cpu_threads: int = 2
    voice_max_seconds: int = 180
    voice_idle_unload_seconds: float = 1800.0

    # Google Calendar pull for connected workspaces (seconds, 0 = off)
    calendar_sync_interval_seconds: float = 900.0

    # Interactive API docs (/docs, /redoc, /openapi.json); off on public self-hosted installs
    api_docs_enabled: bool = True

    # Telegram reminder delivery loop
    reminder_poll_interval_seconds: float = 60.0

    # Outbox relay configuration
    outbox_polling_interval_seconds: float = 2.0
    outbox_batch_size: int = 50


settings = Settings()
