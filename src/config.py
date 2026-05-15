from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field


class Config(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    anthropic_api_key: str
    semantic_scholar_api_key: str | None = None
    contact_email: str | None = None
    claude_model: str = "claude-sonnet-4-5"
    database_path: str = "data/projects.db"


def get_config() -> Config:
    return Config()
