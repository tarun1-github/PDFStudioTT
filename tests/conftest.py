"""Shared pytest fixtures for unit, API, and security tests."""
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.config import get_settings
from backend.database.connection import Base
from backend.database.init_db import seed_database
from backend.database.session import get_db
from backend.main import create_app


@pytest.fixture()
def isolated_env(tmp_path: Path, monkeypatch):
    """Provide isolated storage root and test SQLite engine (schema translated to None)."""
    storage = tmp_path / "data"
    storage.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("STORAGE_ROOT", str(storage))
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("MAX_UPLOAD_MB", "5")
    get_settings.cache_clear()

    db_file = tmp_path / "test_pdfstudio.db"
    engine = create_engine(
        f"sqlite:///{db_file}",
        connect_args={"check_same_thread": False},
        execution_options={"schema_translate_map": {"pdfstudio": None}},
    )
    Base.metadata.create_all(bind=engine)
    TestingSession = sessionmaker(bind=engine, autocommit=False, autoflush=False, expire_on_commit=False)

    with TestingSession() as db:
        seed_database(db)

    def override_get_db():
        db = TestingSession()
        try:
            yield db
        finally:
            db.close()

    app = create_app()
    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)

    yield {"client": client, "storage": storage, "session_factory": TestingSession}

    engine.dispose()
    get_settings.cache_clear()
