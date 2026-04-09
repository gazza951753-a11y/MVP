"""FastAPI application entry point.

Exposes:
- REST API (prefix /api)
- Operator HTML GUI (prefix /)
- GET /health — readiness probe
- GET /metrics — Prometheus text exposition format
"""
from __future__ import annotations

import logging
import logging.config

from fastapi import FastAPI, Response
from prometheus_client import CONTENT_TYPE_LATEST, CollectorRegistry, generate_latest, multiprocess
from prometheus_client import REGISTRY as DEFAULT_REGISTRY

from app.api import router as api_router
from app.config import settings
from app.db.base import Base, engine
from app.gui import router as gui_router
from app.observability.sentry import init_sentry

# --------------------------------------------------------------------------- #
# Logging                                                                      #
# --------------------------------------------------------------------------- #

logging.config.dictConfig(
    {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "default": {
                "format": "%(asctime)s %(levelname)-8s %(name)s %(message)s",
                "datefmt": "%Y-%m-%dT%H:%M:%S",
            }
        },
        "handlers": {
            "console": {"class": "logging.StreamHandler", "formatter": "default"},
        },
        "root": {"handlers": ["console"], "level": settings.log_level.upper()},
    }
)

logger = logging.getLogger(__name__)

# --------------------------------------------------------------------------- #
# Startup                                                                      #
# --------------------------------------------------------------------------- #

init_sentry()

try:
    Base.metadata.create_all(bind=engine)
    logger.info("Database tables ensured")
except Exception as exc:
    logger.warning("Could not create tables on startup: %s", exc)

# --------------------------------------------------------------------------- #
# Application                                                                  #
# --------------------------------------------------------------------------- #

app = FastAPI(
    title="StudyAssist Intel System",
    version="0.3.0",
    description="Automated competitor/platform intelligence pipeline for StudyAssist",
)

app.include_router(api_router)
app.include_router(gui_router)


@app.get("/health", tags=["ops"])
def health() -> dict:
    """Kubernetes / Docker readiness probe."""
    return {"status": "ok", "version": app.version}


@app.get("/metrics", tags=["ops"], response_class=Response)
def metrics() -> Response:
    """Prometheus text-format metrics exposition endpoint."""
    if settings.prometheus_enabled:
        try:
            # Support prometheus_client multiprocess mode
            registry = CollectorRegistry()
            multiprocess.MultiProcessCollector(registry)
            data = generate_latest(registry)
        except ValueError:
            # Not in multiprocess mode — use the default registry
            data = generate_latest(DEFAULT_REGISTRY)
    else:
        data = b""
    return Response(content=data, media_type=CONTENT_TYPE_LATEST)
