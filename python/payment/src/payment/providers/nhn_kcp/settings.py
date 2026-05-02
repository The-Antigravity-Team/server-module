from pydantic_settings import BaseSettings, SettingsConfigDict


class NHNKCPSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="KCP_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    site_cd: str = ""           # KCP_SITE_CD  (사이트 코드)
    site_key: str = ""          # KCP_SITE_KEY  (사이트 키)
    base_url: str = "https://api.kcp.co.kr"   # 스테이징: https://stg-api.kcp.co.kr
    api_version: str = "v1"
    timeout_seconds: int = 30
