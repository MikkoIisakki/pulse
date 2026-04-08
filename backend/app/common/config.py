"""Application configuration — single source of truth for all settings.

All values come from environment variables. No scattered os.environ.get() calls
anywhere else in the codebase. Import Settings and use it.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Database
    database_url: str

    # Application
    log_level: str = "INFO"
    environment: str = "development"

    # Ingest staleness threshold — health check returns degraded if exceeded
    max_ingest_age_hours: int = 25


settings = Settings()
