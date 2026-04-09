from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Core
    database_url: str = "postgresql+psycopg://postgres:postgres@localhost:5432/intel"
    app_env: str = "dev"
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    log_level: str = "INFO"

    # Observability
    sentry_dsn: str = ""
    prometheus_enabled: bool = True
    prometheus_port: int = 9100

    # Airtable — 5 rps/base, 50 rps per PAT; 429 → wait 30 s
    airtable_pat: str = ""
    airtable_base_id: str = ""
    airtable_tasks_table: str = "Tasks"
    airtable_platforms_table: str = "Platforms"

    # Notion — ~3 rps per integration; 429 → Retry-After
    notion_token: str = ""
    notion_tasks_db_id: str = ""
    notion_platforms_db_id: str = ""

    # Google Sheets — per-minute quota; 429 → exponential backoff
    google_service_account_json: str = ""  # path or inline JSON string
    google_spreadsheet_id: str = ""

    # Telegram Bot (internal operator notifications only — not mass outreach)
    telegram_bot_token: str = ""
    telegram_operator_chat_id: str = ""

    # Collector settings
    discovery_max_pages: int = 5
    trigger_scan_interval_minutes: int = 15
    revalidation_days: int = 14
    request_timeout_seconds: float = 15.0
    max_retries: int = 5

    # VK API
    vk_access_token: str = ""
    vk_api_version: str = "5.199"


settings = Settings()
