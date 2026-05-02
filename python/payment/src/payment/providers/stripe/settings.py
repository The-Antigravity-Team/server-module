from pydantic_settings import BaseSettings, SettingsConfigDict


class StripeSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="STRIPE_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    secret_key: str = ""                    # STRIPE_SECRET_KEY (sk_test_... or sk_live_...)
    api_version: str = "2024-06-20"         # STRIPE_API_VERSION
    currency: str = "krw"                   # STRIPE_CURRENCY (기본 통화)
    timeout_seconds: int = 30
