"""Session management and transactional helpers."""
from collections.abc import Generator
from contextlib import contextmanager
from sqlalchemy.orm import Session, sessionmaker

from backend.database.connection import get_engine


def get_session_factory() -> sessionmaker[Session]:
    return sessionmaker(
        bind=get_engine(),
        autocommit=False,
        autoflush=False,
        expire_on_commit=False,
    )


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency yielding a scoped SQLAlchemy session."""
    session_factory = get_session_factory()
    db = session_factory()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def db_transaction() -> Generator[Session, None, None]:
    """Context manager for explicit transactional blocks in workers/services."""
    session_factory = get_session_factory()
    db = session_factory()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
