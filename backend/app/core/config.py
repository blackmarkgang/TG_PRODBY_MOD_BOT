from functools import cached_property

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: str = "local"
    app_name: str = "Prod.by Bot"
    bot_token: str = "replace_me"
    telegram_group_id: str | None = None
    database_url: str = "postgresql+asyncpg://prodby:prodby@localhost:5432/prodby"
    sync_database_url: str = "postgresql+psycopg://prodby:prodby@localhost:5432/prodby"
    admin_ids_raw: str = Field(default="", alias="ADMIN_IDS")
    dev_admin_id: int | None = None
    cors_origins_raw: str = Field(default="http://localhost:5173", alias="CORS_ORIGINS")
    public_webapp_url: str = "http://localhost:5173"
    api_base_url: str = "http://localhost:8000"

    @cached_property
    def admin_ids(self) -> set[int]:
        return {int(item.strip()) for item in self.admin_ids_raw.split(",") if item.strip()}

    @cached_property
    def cors_origins(self) -> list[str]:
        return [item.strip() for item in self.cors_origins_raw.split(",") if item.strip()]


settings = Settings()
