from fastapi import FastAPI

from app.db.base import Base, engine
from app.observability.sentry import init_sentry
from app.pipeline import run_discovery

init_sentry()
Base.metadata.create_all(bind=engine)

app = FastAPI(title="StudyAssist Intel System", version="0.1.0")


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/run/discovery")
def run_discovery_endpoint() -> dict:
    return run_discovery()
