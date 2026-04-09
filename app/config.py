from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "sqlite:///./intel.db"
    app_env: str = "dev"
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    log_level: str = "INFO"
    sentry_dsn: str = ""
    prometheus_enabled: bool = True
    prometheus_port: int = 9100

    use_mock_collector: bool = False
    discovery_queries: list[str] = Field(
        default_factory=lambda: [
            "site:vk.com помощь студентам курсовая",
            "site:t.me курсовая срочно",
            "где заказать дипломную работу форум",
            "антиплагиат поднять уникальность помощь",
        ]
    )


settings = Settings()
