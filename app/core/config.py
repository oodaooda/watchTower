"""watchTower settings

Loads configuration from environment variables (.env supported) using pydantic-settings.
"""
from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    # Core
    database_url: str
    alpha_vantage_api_key: str | None = None
    sec_user_agent: str

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

    # Universe toggles
    include_banks: bool = Field(False, alias="INCLUDE_BANKS")
    include_reits: bool = Field(False, alias="INCLUDE_REITS")
    include_otc_sec_reporters: bool = Field(True, alias="INCLUDE_OTC_SEC_REPORTERS")
    allow_ifrs: bool = Field(False, alias="ALLOW_IFRS")

    class Config:
        env_file = ".env"
        extra = "allow"


settings = Settings()
