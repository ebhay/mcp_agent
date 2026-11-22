from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    mongo_uri: str = "mongodb://localhost:27017"
    mongo_db_name: str = "appdb"
    openai_api_key: str = ""
    openai_base_url: str = ""
    openai_model: str = "gpt-4o-mini"
    cors_origins: str = "http://localhost:5173"

    # Coach agent
    app_base_url: str = "http://localhost:8000"
    trainmate_base_url: str = "https://trainmate-o6tv.onrender.com"
    coach_login_id: str = "coach01"
    coach_password: str = ""
    admin_login_id: str = "admin01"
    admin_password: str = ""
    trainer_login_id: str = "trainer01"
    trainer_password: str = ""
    embedding_model: str = "text-embedding-3-small"
    batch_match_threshold: float = 0.35


@lru_cache
def get_settings() -> Settings:
    return Settings()
