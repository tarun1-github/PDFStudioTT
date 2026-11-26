"""MSSQL SQLAlchemy engine, pooling, credential-safe connection creator, and health diagnostics."""
import logging
from typing import Any

import pyodbc
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase

from backend.config import get_settings, redact_sensitive

logger = logging.getLogger("pdfstudio.database")


class Base(DeclarativeBase):
    """Declarative base for all pdfstudio schema models."""


_engine: Engine | None = None


def create_pyodbc_connection() -> pyodbc.Connection:
    """Open a pyodbc connection without exposing credentials in SQLAlchemy URLs or tracebacks."""
    settings = get_settings()
    conn_str = settings.build_odbc_connection_string()
    try:
        return pyodbc.connect(conn_str)
    except pyodbc.Error as exc:
        safe_msg = redact_sensitive(str(exc))
        raise pyodbc.OperationalError(exc.args[0] if exc.args else "08001", safe_msg) from None


def get_engine() -> Engine:
    """Return a singleton SQLAlchemy engine configured for MSSQL + pyodbc via safe creator."""
    global _engine
    if _engine is None:
        settings = get_settings()
        logger.info(
            "Initializing MSSQL engine for %s:%s/%s using %s",
            settings.DB_SERVER,
            settings.DB_PORT,
            settings.DB_DATABASE,
            settings.tls_mode_label,
        )
        _engine = create_engine(
            "mssql+pyodbc://",
            creator=create_pyodbc_connection,
            pool_size=10,
            max_overflow=10,
            pool_pre_ping=True,
            pool_recycle=1800,
            fast_executemany=True,
        )
    return _engine


def reset_engine() -> None:
    """Dispose and clear the cached engine (used in tests or config reload)."""
    global _engine
    if _engine is not None:
        _engine.dispose()
        _engine = None


def check_database_health() -> dict[str, Any]:
    """Run live MSSQL connectivity, database, and schema checks with sanitized errors."""
    settings = get_settings()
    result: dict[str, Any] = {
        "connected": False,
        "server": settings.DB_SERVER,
        "port": settings.DB_PORT,
        "database": settings.DB_DATABASE,
        "schema": settings.DB_SCHEMA,
        "tls_mode": settings.tls_mode_label,
        "schema_exists": False,
        "error": None,
    }
    try:
        engine = get_engine()
        with engine.connect() as conn:
            row = conn.execute(
                text("SELECT @@SERVERNAME AS srv, DB_NAME() AS db_name, USER_NAME() AS db_user, GETDATE() AS ts")
            ).fetchone()
            schema_row = conn.execute(
                text("SELECT 1 FROM sys.schemas WHERE name = :schema"),
                {"schema": settings.DB_SCHEMA},
            ).fetchone()
            result["connected"] = True
            result["server_name"] = row[0] if row else None
            result["active_database"] = row[1] if row else None
            result["active_user"] = row[2] if row else None
            result["server_time"] = row[3].isoformat() if row and row[3] else None
            result["schema_exists"] = bool(schema_row)
    except Exception as exc:
        result["error"] = redact_sensitive(f"{type(exc).__name__}: {exc}")
    return result
