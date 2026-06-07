from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/aiclone"
    redis_url: str = "redis://localhost:6379/0"
    secret_key: str = "dev-secret-key"
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 30

    anthropic_api_key: str = ""
    openai_api_key: str = ""
    cohere_api_key: str = ""
    openrouter_api_key: str = ""
    openrouter_base_url: str = "https://openrouter.ai/api/v1"

    upload_dir: str = "uploads"

    ragas_sample_rate: float = 0.10
    max_upload_size_mb: int = 50
    ingestion_concurrency_per_user: int = 2

    algorithm: str = "HS256"


@lru_cache
def get_settings() -> Settings:
    return Settings()
