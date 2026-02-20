"""watchTower settings

Loads configuration from environment variables (.env supported) using pydantic-settings.
"""
from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    # Core
    database_url: str
    qa_database_url: str | None = Field(default=None, alias="QA_DATABASE_URL")
    qa_sql_enabled: bool = Field(default=True, alias="QA_SQL_ENABLED")
    qa_sql_row_limit: int = Field(default=100, alias="QA_SQL_ROW_LIMIT")
    qa_sql_timeout_ms: int = Field(default=3000, alias="QA_SQL_TIMEOUT_MS")
    alpha_vantage_api_key: str | None = None
    sec_user_agent: str
    pharma_openai_api_key: str | None = Field(default=None, alias="PHARMA_OPENAI_API_KEY")
    modeling_openai_api_key: str | None = Field(default=None, alias="MODELING_OPENAI_API_KEY")
    openclaw_api_token: str | None = Field(default=None, alias="OPENCLAW_API_TOKEN")
    openclaw_allowed_ips: str | None = Field(default=None, alias="OPENCLAW_ALLOWED_IPS")
    openclaw_rate_limit: int = Field(60, alias="OPENCLAW_RATE_LIMIT")
    admin_settings_token: str | None = Field(default=None, alias="SETTINGS_ADMIN_TOKEN")

    class Config:
        env_file = ".env"            # <- load from repo root
        env_file_encoding = "utf-8"
    timezone: str = Field("America/New_York", alias="TIMEZONE")

    # External services
    alpha_vantage_api_key: str | None = Field(default=None, alias="ALPHA_VANTAGE_API_KEY")
    sec_user_agent: str = Field(
        "watchTower/0.1 (contact@example.com)", alias="SEC_USER_AGENT"
    )

    # CORS (comma-separated list; '*' allows all - dev only)
    cors_origins: str = Field("*", alias="CORS_ORIGINS")
    log_level: str = Field("INFO", alias="LOG_LEVEL")

    # Universe toggles
    include_banks: bool = Field(False, alias="INCLUDE_BANKS")
    include_reits: bool = Field(False, alias="INCLUDE_REITS")
    include_otc_sec_reporters: bool = Field(True, alias="INCLUDE_OTC_SEC_REPORTERS")
    allow_ifrs: bool = Field(False, alias="ALLOW_IFRS")

    class Config:
        env_file = ".env"
        extra = "allow"
        protected_namespaces = ("model_",)


settings = Settings()
