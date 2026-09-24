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

    # ── Convenience helpers ──────────────────────────────────────────────

    @property
    def async_database_url(self) -> str:
        """Return the database URL, guaranteed to use the asyncpg driver."""
        url = self.DATABASE_URL
        if url.startswith("postgresql://"):
            url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
        return url


# ── Module-level singleton ───────────────────────────────────────────────
settings = Settings()
