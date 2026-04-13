"""
Application configuration loaded from environment variables / .env file.
"""
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# Resolve paths relative to this file so the app works regardless of which
# directory it is launched from.
_BACKEND_DIR = Path(__file__).parent.parent  # …/backend/


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        # Always look for .env next to run.py, not relative to CWD
        env_file=str(_BACKEND_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Storage
    use_azure_storage: bool = False
    azure_storage_connection_string: str = ""
    azure_storage_container_name: str = "discount-ui"
    # Default to an absolute path so local storage lands in backend/local_storage/
    local_storage_path: str = str(_BACKEND_DIR / "local_storage")

    # Database — absolute path avoids CWD-dependent SQLite file location
    database_url: str = f"sqlite+aiosqlite:///{_BACKEND_DIR / 'discount.db'}"

    # Server
    cors_origins: str = "http://localhost:5173"

    # Detector
    detector_confidence: float = 0.2
    detector_epsilon: float = 0.5

    # Auth — change this to a long random string in production
    secret_key: str = "change-me-in-production-use-a-long-random-string"

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",")]


@lru_cache
def get_settings() -> Settings:
    return Settings()
