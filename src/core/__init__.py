"""Core module for cross-cutting infrastructure concerns.

Structure:
- `core/infrastructure/` - Pure infrastructure (config, database, security,
  limiter, dependencies)
- `core/services/` - Infrastructure services for external systems (email, storage)
"""

# Re-export infrastructure modules for backward compatibility
from src.core.infrastructure.config import (
    Settings,
    get_jwt_secret_key,
    settings,
    validate_settings,
)
from src.core.infrastructure.database import (
    DATABASE_URL,
    async_session,
    engine,
    get_session,
    init_db,
)
from src.core.infrastructure.dependencies import get_current_admin, get_current_user
from src.core.infrastructure.limiter import get_limiter
from src.core.infrastructure.security import (
    create_access_token,
    decode_access_token,
    get_password_hash,
    is_password_valid,
)

# Re-export infrastructure services
from src.core.services.email import (
    EmailProvider,
    SESEmailProvider,
    SMTPEmailProvider,
    get_email_provider,
)
from src.core.services.storage import StorageProvider, get_storage_provider
from src.core.services.storage_local import LocalStorageProvider
from src.core.services.storage_s3 import S3StorageProvider

__all__ = [
    # Config
    "Settings",
    "settings",
    "get_jwt_secret_key",
    "validate_settings",
    # Database
    "DATABASE_URL",
    "engine",
    "async_session",
    "get_session",
    "init_db",
    # Dependencies
    "get_current_user",
    "get_current_admin",
    # Limiter
    "get_limiter",
    # Security
    "create_access_token",
    "decode_access_token",
    "get_password_hash",
    "is_password_valid",
    # Email
    "EmailProvider",
    "SESEmailProvider",
    "SMTPEmailProvider",
    "get_email_provider",
    # Storage
    "StorageProvider",
    "LocalStorageProvider",
    "S3StorageProvider",
    "get_storage_provider",
]
