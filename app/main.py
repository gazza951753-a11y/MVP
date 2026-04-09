from fastapi import FastAPI

from app.api import router as api_router
from app.db.base import Base, engine
from app.gui import router as gui_router
from app.observability.sentry import init_sentry

init_sentry()
Base.metadata.create_all(bind=engine)

app = FastAPI(title="StudyAssist Intel System", version="0.2.0")
app.include_router(api_router)
app.include_router(gui_router)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}
