"""
Application configuration loaded from environment variables / .env file.
"""
from functools import lru_cache
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Storage
    use_azure_storage: bool = False
    azure_storage_connection_string: str = ""
    azure_storage_container_name: str = "discount-ui"
    local_storage_path: str = "./local_storage"

    # Database
    database_url: str = "sqlite+aiosqlite:///./discount.db"

    # Server
    cors_origins: str = "http://localhost:5173"

    # Detector
    detector_confidence: float = 0.2
    detector_epsilon: float = 0.5

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",")]

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache
def get_settings() -> Settings:
    return Settings()
