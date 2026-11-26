"""Add team document governance, version control, approvals, categories, tags, and analytics tables.

Revision ID: 0002_governance
Revises: 0001_initial
Create Date: 2026-11-26
"""
from typing import Sequence, Union
from alembic import op
from sqlalchemy import inspect

from backend.database.models import (
    DocumentAccessEvent,
    DocumentApproval,
    DocumentCategory,
    DocumentTag,
    DocumentTagMapping,
    DocumentVersion,
    GovernedDocument,
)

revision: str = "0002_governance"
down_revision: Union[str, None] = "0001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

SCHEMA = "pdfstudio"

GOVERNANCE_TABLES = [
    DocumentCategory.__table__,
    DocumentTag.__table__,
    GovernedDocument.__table__,
    DocumentVersion.__table__,
    DocumentTagMapping.__table__,
    DocumentApproval.__table__,
    DocumentAccessEvent.__table__,
]


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    existing = set(inspector.get_table_names(schema=SCHEMA))
    for tbl in GOVERNANCE_TABLES:
        if tbl.name not in existing:
            tbl.create(bind=bind, checkfirst=True)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    existing = set(inspector.get_table_names(schema=SCHEMA))
    for tbl in reversed(GOVERNANCE_TABLES):
        if tbl.name in existing:
            tbl.drop(bind=bind, checkfirst=True)
