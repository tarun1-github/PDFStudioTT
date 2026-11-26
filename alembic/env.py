"""Alembic environment configured for MSSQL `pdfstudio` schema without exposing credentials."""
from logging.config import fileConfig
from alembic import context
from sqlalchemy import create_engine, pool, text

from backend.database.connection import Base, create_pyodbc_connection
import backend.database.models  # noqa: F401 - register models

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def include_object(object_, name, type_, reflected, compare_to):
    if type_ == "table":
        return object_.schema == "pdfstudio"
    return True


def run_migrations_offline() -> None:
    context.configure(
        url="mssql+pyodbc://",
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        version_table_schema="pdfstudio",
        include_schemas=True,
        include_object=include_object,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = create_engine(
        "mssql+pyodbc://",
        creator=create_pyodbc_connection,
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        connection.execute(
            text(
                "IF NOT EXISTS (SELECT 1 FROM sys.schemas WHERE name = 'pdfstudio') "
                "BEGIN EXEC('CREATE SCHEMA pdfstudio') END"
            )
        )
        connection.commit()

        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            version_table_schema="pdfstudio",
            include_schemas=True,
            include_object=include_object,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
