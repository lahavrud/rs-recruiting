"""Application configuration."""

import os
from typing import Any, Literal, Optional

import boto3
from botocore.exceptions import BotoCoreError, ClientError
from pydantic import Field, field_validator
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
)


class SsmSettingsSource(PydanticBaseSettingsSource):
    """Load settings from AWS SSM Parameter Store.

    Fetches all parameters under the given path prefix at construction time.
    Parameter names are lowercased and matched to Settings field names.
    Used in production so secrets are never written to disk.

    Naming convention: SSM parameter names are UPPERCASE (e.g.
    `/rs-recruiting/prod/DATABASE_URL`); they map to snake_case Settings
    fields by lowercasing here. The lowercasing is a case-insensitive
    matching layer — *not* a license to store SSM names in mixed case.
    Keep new SSM params UPPERCASE so the AWS console listing stays
    operator-friendly.
    """

    def __init__(self, settings_cls: type, path_prefix: str) -> None:
        super().__init__(settings_cls)
        self._params: dict[str, str] = {}
        try:
            region = os.environ.get("AWS_DEFAULT_REGION") or os.environ.get(
                "AWS_REGION", "us-east-1"
            )
            client = boto3.client("ssm", region_name=region)
            paginator = client.get_paginator("get_parameters_by_path")
            for page in paginator.paginate(Path=path_prefix, WithDecryption=True):
                for param in page["Parameters"]:
                    key = param["Name"].removeprefix(path_prefix).lower()
                    self._params[key] = param["Value"]
        except (BotoCoreError, ClientError) as exc:
            raise RuntimeError(
                f"Failed to load settings from SSM path {path_prefix!r}: {exc}"
            ) from exc

    def get_field_value(
        self, field_name: str, field_info: Any
    ) -> tuple[Any, str, bool]:
        return self._params.get(field_name.lower()), field_name, False

    def __call__(self) -> dict[str, Any]:
        return dict(self._params)


def _ssm_path_prefix() -> str:
    # Map ENVIRONMENT value to the SSM path segment (production → prod)
    env = os.environ.get("ENVIRONMENT", "development")
    segment = {"production": "prod"}.get(env, env)
    return f"/rs-recruiting/{segment}/"


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # JWT Configuration
    jwt_secret_key: Optional[str] = None  # Must be set via environment variable
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 10
    jwt_refresh_token_expire_days: int = 7

    # CORS Configuration (infra8 requirement)
    # Can be set via ALLOWED_ORIGINS env var as comma-separated list
    # Example: ALLOWED_ORIGINS=http://localhost:3000,http://localhost:3001
    allowed_origins: str = Field(default="http://localhost:3000")

    # Database
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/rs_recruitment"  # pragma: allowlist secret  # noqa: E501
    database_echo: bool = False  # Enable SQL query logging (for debugging only)
    # Connection pool — SQLAlchemy defaults (5+10) saturate quickly on the
    # production t3.micro target. Sized for modest concurrency; tune
    # via env vars (DB_POOL_SIZE, DB_MAX_OVERFLOW, etc.) per environment.
    # ⚠ pool_size + max_overflow = 35 per process. The production deployment
    # runs a single uvicorn worker (no --workers / WEB_CONCURRENCY), so the
    # ceiling is 35 connections. Adding a second worker doubles that — review
    # pool sizing before scaling to multiple workers on the same RDS instance.
    db_pool_size: int = 15
    db_max_overflow: int = 20
    db_pool_recycle: int = 1800  # 30 min — keepalives handle NAT; recycle last resort
    db_pool_pre_ping: bool = True  # SELECT 1 before checkout — catches any dead conn

    # SQS task queue — empty string means tasks run inline (local dev)
    sqs_queue_url: str = ""

    # AWS Configuration
    aws_access_key_id: Optional[str] = None
    aws_secret_access_key: Optional[str] = None
    aws_region: str = "us-east-1"

    # Storage Configuration
    storage_provider: Literal["s3", "local"] = "local"
    aws_s3_bucket_name: Optional[str] = None
    aws_s3_endpoint_url: Optional[str] = None  # For MinIO or S3-compatible services
    local_storage_path: str = "./data/storage"  # Use data directory

    # Email Configuration
    email_provider: Literal["ses", "smtp"] = "smtp"
    aws_ses_from_email: Optional[str] = None
    smtp_host: str = "localhost"
    smtp_port: int = 587
    smtp_user: Optional[str] = None
    smtp_password: Optional[str] = None
    smtp_use_tls: bool = True
    smtp_from_email: Optional[str] = None
    # Optional single recipient for new-application notifications. When set,
    # admin notifications go to this address only; when unset, every active
    # admin receives the notification (legacy fallback).
    admin_notification_email: Optional[str] = None
    # Email quota — free-tier defaults (100/day, 3 000/month).
    # Override via SSM/env when on a paid Resend plan.
    email_daily_limit: int = 100
    email_monthly_limit: int = 3000
    # Minimum seconds between consecutive email sends in the worker.
    # 0.25 s ≈ 4/s — safely under Resend SMTP's implied 5 req/s ceiling.
    email_send_delay_seconds: float = 0.25

    # Resume-matching embeddings.
    # A hosted multilingual model is required — CVs and jobs are Hebrew, English,
    # or mixed, and the model must align all of them in one cross-lingual vector
    # space (see src/core/services/embeddings.py). The API key is a third-party
    # key stored in SSM (/rs-recruiting/embedding-api-key), never an AWS key.
    # ``embedding_dim`` MUST match the model's output dimension and the Vector
    # column width set by the migration — changing it later needs a new migration.
    embedding_provider: Literal["cohere", "fake"] = "fake"
    embedding_model: str = "embed-multilingual-v3.0"
    embedding_api_key: Optional[str] = None
    embedding_dim: int = 1024
    # How many top jobs to persist per candidate match run.
    embedding_top_matches: int = 20

    # Frontend
    frontend_base_url: str = "http://localhost:3000"
    # public PNG URL for email logo; empty = use inline SVG (dev)
    logo_public_url: str = ""
    # Support email shown in email footer
    support_email: str = "support@rs-recruiting.com"

    # RS assets in S3 (contract template + agency signature)
    rs_contract_template_s3_key: str = "assets/rs-contract.pdf"
    rs_signature_s3_key: str = "assets/rs-signature.png"

    # Observability
    sentry_dsn: str = ""  # Empty = Sentry disabled (dev/test)
    log_level: str = "INFO"  # Runtime log level; override via LOG_LEVEL env / SSM
    # Frontend Sentry DSN — used by the /api/sentry-tunnel endpoint to validate
    # that incoming envelopes belong to our project (prevents open-proxy abuse).
    # Must match the VITE_SENTRY_DSN build arg used for the frontend image.
    frontend_sentry_dsn: str = ""  # Empty = tunnel rejects all envelopes

    # GA4 server-side tunnel — forwards custom events via Measurement Protocol
    # so ad-blocked browsers still contribute conversion data.
    # GA4_API_SECRET: GA4 Admin → Data Streams → Measurement Protocol API secrets
    ga4_measurement_id: str = ""  # e.g. G-XXXXXXXXXX; empty = tunnel disabled
    ga4_api_secret: str = ""  # Measurement Protocol API secret

    # Environment
    # "staging" is the ephemeral RC-validation environment (separate AWS
    # account, HTTP-only). It behaves like production — loads config from SSM,
    # enforces rate limiting and the FRONTEND_BASE_URL check — except where its
    # plain-HTTP ingress forces a difference (see _is_refresh_cookie_secure).
    environment: Literal["development", "staging", "production"] = "development"

    # Trusted reverse-proxy IPs/CIDRs.
    # Comma-separated list of IP addresses or CIDR ranges whose X-Forwarded-For
    # headers are accepted as authoritative.  Empty = no proxy trust (dev/test);
    # in production set to the load-balancer's private CIDR (e.g. "10.0.0.0/8").
    trusted_proxy_ips: str = ""

    # Testing Configuration
    testing: bool = False  # Set to True in test environment to disable rate limiting

    @field_validator("allowed_origins")
    @classmethod
    def parse_allowed_origins(cls, v: str) -> list[str]:
        """Parse allowed_origins from comma-separated string.

        Handles:
        - Comma-separated string from environment variable
        - Empty string (falls back to default)
        """
        if not v or not v.strip():
            # Use default if not provided
            return ["http://localhost:3000"]
        # Split by comma and strip whitespace, filter empty strings
        origins = [origin.strip() for origin in v.split(",") if origin.strip()]
        return origins if origins else ["http://localhost:3000"]

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type,
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        if os.environ.get("ENVIRONMENT") in ("production", "staging"):
            return (
                init_settings,
                SsmSettingsSource(settings_cls, _ssm_path_prefix()),
                env_settings,
            )
        return (init_settings, env_settings, dotenv_settings)

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",  # tolerate REDIS_URL and other stale env vars during rollout
    )


settings = Settings()


def validate_settings() -> None:
    """Validate critical settings at startup.

    Raises:
        ValueError: If critical settings are invalid
    """
    # Skip validation in test environment
    if settings.testing:
        return

    # Validate JWT secret key
    if (
        not settings.jwt_secret_key
        or settings.jwt_secret_key
        == "your-secret-key-change-in-production"  # pragma: allowlist secret
    ):
        raise ValueError(
            "JWT_SECRET_KEY must be set to a secure value via environment variable. "
            "Generate one with: python -c 'import secrets; "
            "print(secrets.token_urlsafe(32))'"
        )
    if len(settings.jwt_secret_key) < 32:
        raise ValueError(
            f"JWT_SECRET_KEY must be at least 32 characters long for security "
            f"(current length: {len(settings.jwt_secret_key)})"
        )

    # Validate email provider config
    if settings.email_provider == "ses" and not settings.aws_ses_from_email:
        raise ValueError("AWS_SES_FROM_EMAIL must be set when EMAIL_PROVIDER=ses")

    # Validate frontend base URL in deployed environments
    if settings.environment in ("production", "staging") and (
        "localhost" in settings.frontend_base_url
        or "127.0.0.1" in settings.frontend_base_url
    ):
        raise ValueError(
            "FRONTEND_BASE_URL must be set to the real domain in "
            f"{settings.environment} (current value: {settings.frontend_base_url})"
        )


def get_jwt_secret_key() -> str:
    """Get JWT secret key (validated, guaranteed non-None).

    Should only be called after validate_settings().
    """
    # After validate_settings(), jwt_secret_key is guaranteed to be set
    assert settings.jwt_secret_key is not None, "JWT_SECRET_KEY must be set"
    return settings.jwt_secret_key
