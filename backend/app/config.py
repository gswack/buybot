from pydantic_settings import BaseSettings
import secrets


class Settings(BaseSettings):
    # SerpAPI key — get one at https://serpapi.com
    serpapi_key: str

    # Apify API token — get one at https://console.apify.com/settings/integrations
    apify_api_token: str = ""

    # PostgreSQL connection — used for user profiles
    database_url: str = "postgresql://postgres:postgres@localhost:5432/priceapp"

    # JWT secret — generate a strong random value for production
    jwt_secret: str = secrets.token_hex(32)
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60 * 24 * 7  # 7 days

    # How many results to return
    top_k: int = 10

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()