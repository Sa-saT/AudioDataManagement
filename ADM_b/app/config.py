from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(Path(__file__).resolve().parents[1] / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # PostgreSQL
    DB_HOST: str = "localhost"
    DB_PORT: int = 5432
    DB_NAME: str = "adm_dev"
    DB_MIGRATOR_USER: str = "adm_migrator"
    DB_MIGRATOR_PASSWORD: str = ""
    DB_APP_USER: str = "adm_app"
    DB_APP_PASSWORD: str = ""
    DB_SSLMODE: str = "disable"

    # JWT
    JWT_SECRET: str = ""
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 60 * 24 * 7

    # Signed URL
    SIGNED_URL_SECRET: str = ""
    SIGNED_URL_TTL_SECONDS: int = 300

    # License
    LICENSE_SECRET: str = ""

    # Storage
    STORAGE_BACKEND: str = "local"
    STORAGE_DIR: str = "/tmp/adm_storage/sounds"

    # Audio
    PREVIEW_DURATION_SEC: int = 60
    MAX_SAMPLE_RATE: int = 48000
    MAX_BIT_DEPTH: int = 24

    # CORS
    CORS_ORIGINS: str = "http://localhost:3000"

    @property
    def app_database_url(self) -> str:
        return self._build_url(self.DB_APP_USER, self.DB_APP_PASSWORD)

    @property
    def migrator_database_url(self) -> str:
        return self._build_url(self.DB_MIGRATOR_USER, self.DB_MIGRATOR_PASSWORD)

    def _build_url(self, user: str, password: str) -> str:
        return (
            f"postgresql+psycopg2://{user}:{password}"
            f"@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
            f"?sslmode={self.DB_SSLMODE}"
        )

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
