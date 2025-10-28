# backend/core/config.py

from pydantic_settings import BaseSettings
from functools import lru_cache

class Settings(BaseSettings):
    # === Project Metadata ===
    PROJECT_NAME: str = "PriceWise AI"
    VERSION: str = "1.0.0"
    API_PREFIX: str = "/api"

    # === Environment ===
    ENVIRONMENT: str = "development"  # or "production", "staging"
    DEBUG: bool = True

    # === Backend Configuration ===
    BACKEND_CORS_ORIGINS: list[str] = [
        "http://localhost:3000",   # local frontend
        "https://pricewise-ai.com",  # production domain
    ]

    # === Database ===
    DATABASE_URL: str = "postgresql+psycopg2://user:password@localhost:5432/pricewise_db"

    # === Security ===
    SECRET_KEY: str = "CHANGE_ME_TO_A_RANDOM_SECRET"  # load from .env in production
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 1 day

    # === External APIs ===
    OPENAI_API_KEY: str | None = None
    DISCOUNT_API_URL: str | None = None  # e.g. Bank/Credit card API endpoint

    # === Logging ===
    LOG_LEVEL: str = "INFO"
    LOG_FILE_PATH: str = "logs/app.log"

    class Config:
        env_file = ".env"
        case_sensitive = True


@lru_cache()
def get_settings() -> Settings:
    """Cache settings instance so it's only loaded once."""
    return Settings()
