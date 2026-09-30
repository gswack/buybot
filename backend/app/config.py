from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # SerpAPI key — get one at https://serpapi.com
    serpapi_key: str

    # Apify API token — get one at https://console.apify.com/settings/integrations
    # Used for the ASOS scraper (ASOS blocks direct server-to-server requests)
    apify_api_token: str = ""

    # How many results to return
    top_k: int = 10

    class Config:
        env_file = ".env"
        extra = "ignore"  # ignore leftover fields from old .env


settings = Settings()