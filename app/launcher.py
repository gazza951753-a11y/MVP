"""Windows desktop launcher for StudyAssist Intel System.

Startup sequence
----------------
1. Determine data directory (%APPDATA%\\StudyAssist on Windows).
2. Set DATABASE_URL → SQLite in that directory (if not already overridden).
3. Load .env overrides (for power users who want PostgreSQL).
4. Create DB tables via SQLAlchemy metadata.
5. Seed baseline trigger rules if the triggers table is empty.
6. Start FastAPI / uvicorn in a background daemon thread.
7. Wait for the HTTP server to respond (up to 15 s).
8. Open a native desktop window via pywebview (uses Edge WebView2 on Win10/11).

Packaging
---------
Built with PyInstaller — see studyassist.spec and build_exe.bat.
"""
from __future__ import annotations

import logging
import os
import sys
import threading
import time
from pathlib import Path

# --------------------------------------------------------------------------- #
# 1. Data directory & environment setup (MUST happen before any app imports)  #
# --------------------------------------------------------------------------- #

def _app_data_dir() -> Path:
    if sys.platform == "win32":
        base = os.environ.get("APPDATA", str(Path.home() / "AppData" / "Roaming"))
    else:
        base = str(Path.home() / ".config")
    d = Path(base) / "StudyAssist"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _setup_environment() -> Path:
    data_dir = _app_data_dir()

    # SQLite database in the user's app-data dir
    db_path = data_dir / "studyassist.db"
    os.environ.setdefault("DATABASE_URL", f"sqlite:///{db_path}")
    os.environ.setdefault("APP_ENV", "desktop")
    os.environ.setdefault("LOG_LEVEL", "WARNING")
    os.environ.setdefault("PROMETHEUS_ENABLED", "false")

    # Load .env from the data dir (power-user override)
    env_file = data_dir / ".env"
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                os.environ.setdefault(k.strip(), v.strip())

    return data_dir


DATA_DIR = _setup_environment()

# --------------------------------------------------------------------------- #
# 2. Logging                                                                   #
# --------------------------------------------------------------------------- #

logging.basicConfig(
    level=logging.WARNING,
    format="%(asctime)s %(levelname)-8s %(name)s %(message)s",
    handlers=[
        logging.FileHandler(DATA_DIR / "studyassist.log", encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger("launcher")

# --------------------------------------------------------------------------- #
# 3. DB initialisation & seed (after env is set, before server starts)        #
# --------------------------------------------------------------------------- #

_PORT = 8765
_BASE_URL = f"http://127.0.0.1:{_PORT}"


def _init_db() -> None:
    """Create tables and seed triggers if this is a first run."""
    from app.db.base import Base, engine
    from app.db.models import Trigger
    from app.processing.classify_rules import BASELINE_TRIGGERS
    from sqlalchemy import select
    from sqlalchemy.orm import Session

    logger.info("Creating DB tables at %s", engine.url)
    Base.metadata.create_all(bind=engine)

    with Session(engine) as session:
        existing = session.execute(select(Trigger)).first()
        if existing:
            return  # already seeded

        logger.info("Seeding %d baseline triggers", len(BASELINE_TRIGGERS))
        for t in BASELINE_TRIGGERS:
            trigger = Trigger(
                code=t["code"],
                description=t["description"],
                regex_patterns=t.get("regex_patterns", []),
                keywords=t.get("keywords", []),
                negative_keywords=t.get("negative_keywords", []),
                weight=t.get("weight", 1.0),
                enabled=True,
            )
            session.add(trigger)
        session.commit()

    # Invalidate classify_rules cache so it picks up the fresh DB triggers
    from app.processing.classify_rules import invalidate_cache
    invalidate_cache()


# --------------------------------------------------------------------------- #
# 4. FastAPI server in background thread                                       #
# --------------------------------------------------------------------------- #

def _start_server() -> None:
    import uvicorn
    from app.main import app as fastapi_app

    uvicorn.run(
        fastapi_app,
        host="127.0.0.1",
        port=_PORT,
        log_level="warning",
        access_log=False,
    )


def _wait_for_server(timeout: float = 15.0) -> bool:
    import httpx

    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            httpx.get(f"{_BASE_URL}/health", timeout=1.0)
            return True
        except Exception:
            time.sleep(0.25)
    return False


# --------------------------------------------------------------------------- #
# 5. pywebview window                                                          #
# --------------------------------------------------------------------------- #

def _show_error(msg: str) -> None:
    """Fallback error dialog using tkinter (always available on Windows)."""
    try:
        import tkinter as tk
        from tkinter import messagebox

        root = tk.Tk()
        root.withdraw()
        messagebox.showerror("StudyAssist Intel — Ошибка запуска", msg)
        root.destroy()
    except Exception:
        print("ERROR:", msg, file=sys.stderr)


def main() -> None:
    logger.info("StudyAssist desktop launcher starting")

    # Initialise DB before starting server
    try:
        _init_db()
    except Exception as exc:
        _show_error(f"Не удалось инициализировать базу данных:\n{exc}")
        sys.exit(1)

    # Start FastAPI in background
    server_thread = threading.Thread(target=_start_server, daemon=True)
    server_thread.start()

    if not _wait_for_server():
        _show_error(
            "Сервер не запустился в течение 15 секунд.\n"
            f"Проверьте логи: {DATA_DIR / 'studyassist.log'}"
        )
        sys.exit(1)

    logger.info("Server ready at %s", _BASE_URL)

    # Open the native window
    try:
        import webview  # pywebview

        window = webview.create_window(
            title="StudyAssist Intel System",
            url=_BASE_URL,
            width=1400,
            height=900,
            min_size=(1024, 700),
            text_select=True,
            confirm_close=True,
        )
        webview.start(debug=False)
    except ImportError:
        # pywebview not available — open in default browser instead
        import webbrowser

        logger.warning("pywebview not available; opening browser")
        webbrowser.open(_BASE_URL)
        # Keep alive until Ctrl+C
        try:
            while server_thread.is_alive():
                time.sleep(1)
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    main()
