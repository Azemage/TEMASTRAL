from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "sqlite:///./astro.db"
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-sonnet-5"
    session_cookie_name: str = "astro_session"
    session_ttl_days: int = 365
    cors_origins: str = "*"


@lru_cache
def get_settings() -> Settings:
    return Settings()
