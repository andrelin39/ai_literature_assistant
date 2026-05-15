from contextlib import contextmanager
from pathlib import Path
from typing import Generator

from pydantic import ValidationError
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


try:
    from src.config import settings
    DB_URL = f"sqlite:///{settings.database_path}"
except ValidationError as e:
    import sys
    print(f"⚠️ database.py: settings 載入失敗，使用預設 DB 路徑: {e}", file=sys.stderr)
    DB_URL = "sqlite:///data/projects.db"


engine = create_engine(DB_URL, echo=False)
_configure_sqlite_fk(engine)

SessionLocal = sessionmaker(engine, autoflush=False, autocommit=False)


def init_db() -> None:
    """建立 data/ 目錄（若不存在）並建立所有資料表。"""
    db_path = Path(DB_URL.replace("sqlite:///", "", 1))
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
