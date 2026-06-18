from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = "postgresql+psycopg2://bedtimebuddy:bedtimebuddy@localhost:5432/bedtimebuddy"
    slack_bot_token: str = ""
    slack_app_token: str = ""
    ollama_base_url: str = "http://ai.homelab.internal:11434"
    ollama_model: str = "qwen3.6:35b"
    web_search_url: str = ""
    souls_dir: str = "souls"

    @property
    def project_root(self) -> Path:
        return Path(__file__).resolve().parent.parent

    @property
    def souls_path(self) -> Path:
        path = Path(self.souls_dir)
        if not path.is_absolute():
            path = self.project_root / path
        return path

    @property
    def slack_configured(self) -> bool:
        return bool(self.slack_bot_token and self.slack_app_token)


@lru_cache
def get_settings() -> Settings:
    return Settings()
