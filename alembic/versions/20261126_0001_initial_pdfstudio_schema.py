"""Initial pdfstudio schema and 9 core tables.

Revision ID: 0001_initial
Revises:
Create Date: 2026-11-26
"""
from typing import Sequence, Union
from alembic import op
from sqlalchemy import inspect

from backend.database.connection import Base
import backend.database.models  # noqa: F401

revision: str = "0001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

SCHEMA = "pdfstudio"


def upgrade() -> None:
    bind = op.get_bind()
    op.execute(
        "IF NOT EXISTS (SELECT 1 FROM sys.schemas WHERE name = 'pdfstudio') "
        "BEGIN EXEC('CREATE SCHEMA pdfstudio') END"
    )
    inspector = inspect(bind)
    existing = set(inspector.get_table_names(schema=SCHEMA))
    for table in Base.metadata.sorted_tables:
        if table.name not in existing:
            table.create(bind=bind, checkfirst=True)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    existing = set(inspector.get_table_names(schema=SCHEMA))
    for table in reversed(Base.metadata.sorted_tables):
        if table.name in existing:
            table.drop(bind=bind, checkfirst=True)
