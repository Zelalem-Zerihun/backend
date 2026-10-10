"""
Application settings loaded from environment variables via pydantic-settings.

All configuration is centralized here.  Import the singleton ``settings``
object throughout the codebase instead of reading ``os.environ`` directly.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Typed, validated application configuration.

    Values are resolved in this priority (highest → lowest):
    1. Explicit environment variables
    2. ``.env`` file in the project root
    3. Defaults defined below
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # ── Application ──────────────────────────────────────────────────────
    APP_NAME: str = "AccOS E-Learning API"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = False

    # ── Database ─────────────────────────────────────────────────────────
    DATABASE_URL: str = (
        "postgresql+asyncpg://postgres:postgres@localhost:5432/accos_db"
    )

    # ── JWT / Authentication ─────────────────────────────────────────────
    SECRET_KEY: str = "change-me-to-a-real-random-secret-key"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440  # 24 hours

    # ── Google Gemini AI ─────────────────────────────────────────────────
    GEMINI_API_KEY: str = ""
    AI_DAILY_QUOTA: int = 50

    # ── File Storage ─────────────────────────────────────────────────────
    UPLOAD_DIR: str = "uploads"
    UPLOAD_URL_PREFIX: str = "/static/uploads"
    MAX_HTML_FILE_SIZE_MB: int = 10
    MAX_ATTACHMENT_FILE_SIZE_MB: int = 50
    ALLOWED_ATTACHMENT_TYPES: str = (
        "application/pdf,"
        "application/vnd.openxmlformats-officedocument.presentationml.presentation,"
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

    # ── Convenience helpers ──────────────────────────────────────────────

    @property
    def max_html_file_bytes(self) -> int:
        """Maximum HTML upload size in bytes."""
        return self.MAX_HTML_FILE_SIZE_MB * 1024 * 1024

    @property
    def max_attachment_file_bytes(self) -> int:
        """Maximum attachment upload size in bytes."""
        return self.MAX_ATTACHMENT_FILE_SIZE_MB * 1024 * 1024

    @property
    def allowed_attachment_mimes(self) -> set[str]:
        """Parse the comma-separated MIME string into a set."""
        return {m.strip() for m in self.ALLOWED_ATTACHMENT_TYPES.split(",") if m.strip()}

    @property
    def async_database_url(self) -> str:
        """Return the database URL, guaranteed to use the asyncpg driver."""
        url = self.DATABASE_URL
        if url.startswith("postgresql://"):
            url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
        return url


# ── Module-level singleton ───────────────────────────────────────────────
settings = Settings()
