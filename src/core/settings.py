"""全域設定，走 pydantic-settings 從 .env 讀入。

docs/spec/deployment.md §6：v1 沒有平台原生 secret 機制，統一走 `.env`。
docs/spec/analysis-dimensions.md §11–§12：權重、切點、Coverage 門檻皆為設定值，不寫死。
"""

from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = Field(
        default="postgresql+psycopg://stockapp:stockapp@localhost:5432/stockapp",
        description="必須是 direct connection，不得走 pooled endpoint（realtime-quotes.md §3）",
    )

    session_cookie_name: str = "session_id"
    session_ttl_days: int = 30

    google_client_id: str = ""
    google_client_secret: str = ""
    github_client_id: str = ""
    github_client_secret: str = ""

    discord_webhook_url: str = ""
    healthchecks_ping_url: str = ""

    quote_provider: str = Field(
        default="fake",
        description="dev 預設 fake（realtime-quotes.md §7.1：Fugle 免費層 1 連線是帳號級）",
    )
    fugle_api_key: str = ""

    tz_display: str = "Asia/Taipei"


settings = Settings()
