from typing import List, Union
from pydantic import Field, field_validator
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
    environment: str = "development"
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
        default="personal-os-dev-super-secret-jwt-key-change-in-production-2026",
        description="HMAC secret key for JWT signing",
    )
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 60 * 24  # 24 hours

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
    google_redirect_uri: str = "http://localhost:8008/v1/integrations/google/callback"
    telegram_bot_token: str = ""
    telegram_webhook_secret: str = ""
    telegram_webhook_base_url: str = ""

    # Outbox relay configuration
    outbox_polling_interval_seconds: float = 2.0
    outbox_batch_size: int = 50


settings = Settings()
