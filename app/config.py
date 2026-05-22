from datetime import date
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    env: Literal["development", "test", "production"] = "development"
    admin_token: str = Field(default="")

    database_url: str
    database_url_test: str | None = None

    odata_base_url: str
    odata_admin_user: str
    odata_password: str
    odata_timeout_seconds: int = 60

    envelope_bc_prefix: str = ""
    admin_login: str = Field(
        default="",
        validation_alias=AliasChoices("ADMIN_LOGIN", "BOOTSTRAP_ADMIN"),
    )
    admin_password: str = Field(
        default="0000",
        validation_alias=AliasChoices("ADMIN_PASSWORD", "BOOTSTRAP_ADMIN_PASSWORD"),
    )
    auth_cookie_max_age_seconds: int = 28800
    printers_json: str = "[]"
    enable_1c_timestamps: bool = True
    print_server_host: str = "10.60.6.11"
    sumatra_exe_path: str = str(Path("tools") / "SumatraPDF-3.6.1-64.exe")
    print_temp_dir: str = str(Path("tools") / "temp")
    sumatra_timeout_seconds: int = 90
    qr_base_url: str = ""
    paperless_webhook_api_key: str = ""
    paperless_api_url: str = ""
    paperless_api_token: str = ""
    paperless_mark_tag_id: int = 52
    paperless_error_tag_id: int = 53
    paperless_onec_originals_unc_root: str = ""
    paperless_onec_archive_unc_root: str = ""
    paperless_poll_interval_minutes: int = 0
    paperless_poll_batch_size: int = 50
    sync_initial_from_date: date = date(2023, 1, 1)
    sync_schedule_hours: int = 4

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
