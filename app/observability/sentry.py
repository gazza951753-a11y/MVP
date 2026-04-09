import sentry_sdk

from app.config import settings


def init_sentry() -> None:
    if settings.sentry_dsn:
        sentry_sdk.init(dsn=settings.sentry_dsn, traces_sample_rate=0.1, environment=settings.app_env)
