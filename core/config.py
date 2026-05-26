from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # AI APIs
    anthropic_api_key: str
    openai_api_key: str = ""
    google_ai_api_key: str = ""

    # Telegram
    telegram_bot_token: str
    telegram_chat_id: str

    # GitHub
    github_token: str
    github_webhook_secret: str = ""

    # Database
    database_url: str = "sqlite:///./dev.db"

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # Sistema
    secret_key: str = "change-me"
    environment: str = "development"
    log_level: str = "INFO"

    # Agentes
    default_agent: str = "claude-opus-4"
    fast_agent: str = "claude-sonnet-4"
    max_concurrent_agents: int = 3

    # Workspace
    workspace_dir: str = "/workspace/repos"

    @property
    def is_production(self) -> bool:
        return self.environment == "production"

    @property
    def is_sqlite(self) -> bool:
        return self.database_url.startswith("sqlite")


@lru_cache
def get_settings() -> Settings:
    return Settings()
