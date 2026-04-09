from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import settings


class Base(DeclarativeBase):
    pass


_db_url = settings.database_url
_is_sqlite = _db_url.startswith("sqlite")

# SQLite requires check_same_thread=False for multi-threaded FastAPI usage
_connect_args = {"check_same_thread": False} if _is_sqlite else {}

_extra_kwargs: dict = {}
if not _is_sqlite:
    _extra_kwargs = {"pool_size": 5, "max_overflow": 10}

engine = create_engine(_db_url, future=True, connect_args=_connect_args, **_extra_kwargs)


# Enable WAL mode for SQLite — better concurrent read/write performance
if _is_sqlite:
    @event.listens_for(engine, "connect")
    def _set_sqlite_pragmas(dbapi_conn, _):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)
