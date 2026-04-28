from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    env: Literal["development", "test", "production"] = "development"
    admin_token: str = Field(min_length=8)

    database_url: str
    database_url_test: str | None = None

    odata_base_url: str
    odata_admin_user: str
    odata_password: str
    odata_timeout_seconds: int = 60

    envelope_bc_prefix: str = ""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
