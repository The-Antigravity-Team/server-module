from pydantic_settings import BaseSettings, SettingsConfigDict


class TossPaymentsSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="TOSS_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    secret_key: str = ""
    client_key: str = ""
    base_url: str = "https://api.tosspayments.com"
    api_version: str = "v1"
    timeout_seconds: int = 30
