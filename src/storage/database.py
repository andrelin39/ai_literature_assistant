from contextlib import contextmanager
from pathlib import Path
from typing import Generator

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker


class Base(DeclarativeBase):
    pass


def _configure_sqlite_fk(engine) -> None:
    @event.listens_for(engine, "connect")
    def set_fk_pragma(dbapi_conn, _):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


def _default_url() -> str:
    try:
        from src.config import get_config
        return f"sqlite:///{get_config().database_path}"
    except Exception:
        return "sqlite:///data/projects.db"


engine = create_engine(_default_url(), echo=False)
_configure_sqlite_fk(engine)

SessionLocal = sessionmaker(engine, autoflush=False, autocommit=False)


def init_db() -> None:
    """建立 data/ 目錄（若不存在）並建立所有資料表。"""
    from src.config import get_config
    db_path = Path(get_config().database_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    Base.metadata.create_all(engine)


@contextmanager
def get_session() -> Generator[Session, None, None]:
    """Context manager，自動 close session。"""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
