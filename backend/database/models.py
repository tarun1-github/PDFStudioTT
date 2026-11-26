"""SQL Server models inside the dedicated `pdfstudio` schema."""
from datetime import datetime, timezone
from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    MetaData,
    NVARCHAR,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.database.connection import Base

SCHEMA_NAME = "pdfstudio"
Base.metadata = MetaData(schema=SCHEMA_NAME)


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        UniqueConstraint("username", name="uq_users_username"),
        UniqueConstraint("email", name="uq_users_email"),
        {"schema": SCHEMA_NAME},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(NVARCHAR(100), nullable=False)
    display_name: Mapped[str] = mapped_column(NVARCHAR(150), nullable=False)
    email: Mapped[str] = mapped_column(NVARCHAR(255), nullable=False)
    storage_folder: Mapped[str] = mapped_column(NVARCHAR(100), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    auth_provider: Mapped[str] = mapped_column(NVARCHAR(50), default="local_dev", nullable=False)
    external_subject: Mapped[str | None] = mapped_column(NVARCHAR(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)

    roles: Mapped[list["UserRole"]] = relationship(back_populates="user", cascade="all, delete-orphan")


class Role(Base):
    __tablename__ = "roles"
    __table_args__ = (
        UniqueConstraint("name", name="uq_roles_name"),
        {"schema": SCHEMA_NAME},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(NVARCHAR(50), nullable=False)  # Engineer, Team Lead, Admin
    description: Mapped[str | None] = mapped_column(NVARCHAR(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)


class UserRole(Base):
    __tablename__ = "user_roles"
    __table_args__ = (
        UniqueConstraint("user_id", "role_id", name="uq_user_roles_pair"),
        {"schema": SCHEMA_NAME},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey(f"{SCHEMA_NAME}.users.id", ondelete="CASCADE"), nullable=False)
    role_id: Mapped[int] = mapped_column(ForeignKey(f"{SCHEMA_NAME}.roles.id", ondelete="CASCADE"), nullable=False)
    assigned_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)

    user: Mapped["User"] = relationship(back_populates="roles")
    role: Mapped["Role"] = relationship()


class PdfJob(Base):
    __tablename__ = "pdf_jobs"
    __table_args__ = (
        Index("ix_pdf_jobs_status_created", "status", "created_at"),
        Index("ix_pdf_jobs_user_id", "user_id"),
        {"schema": SCHEMA_NAME},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    job_uuid: Mapped[str] = mapped_column(NVARCHAR(64), unique=True, nullable=False)
    user_id: Mapped[int] = mapped_column(ForeignKey(f"{SCHEMA_NAME}.users.id"), nullable=False)
    job_type: Mapped[str] = mapped_column(NVARCHAR(64), nullable=False)
    status: Mapped[str] = mapped_column(NVARCHAR(32), default="QUEUED", nullable=False)
    progress_pct: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    payload_json: Mapped[str] = mapped_column(NVARCHAR(None), nullable=False)  # NVARCHAR(MAX)
    result_document_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_message: Mapped[str | None] = mapped_column(NVARCHAR(2000), nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    max_retries: Mapped[int] = mapped_column(Integer, default=2, nullable=False)
    worker_id: Mapped[str | None] = mapped_column(NVARCHAR(100), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)


class UploadedFile(Base):
    __tablename__ = "uploaded_files"
    __table_args__ = (
        Index("ix_uploaded_files_user_id", "user_id"),
        {"schema": SCHEMA_NAME},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    file_uuid: Mapped[str] = mapped_column(NVARCHAR(64), unique=True, nullable=False)
    user_id: Mapped[int] = mapped_column(ForeignKey(f"{SCHEMA_NAME}.users.id"), nullable=False)
    original_filename: Mapped[str] = mapped_column(NVARCHAR(255), nullable=False)
    stored_filename: Mapped[str] = mapped_column(NVARCHAR(255), nullable=False)
    relative_path: Mapped[str] = mapped_column(NVARCHAR(500), nullable=False)
    mime_type: Mapped[str] = mapped_column(NVARCHAR(128), nullable=False)
    file_ext: Mapped[str] = mapped_column(NVARCHAR(20), nullable=False)
    file_size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    sha256_hash: Mapped[str] = mapped_column(NVARCHAR(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)


class GeneratedDocument(Base):
    __tablename__ = "generated_documents"
    __table_args__ = (
        Index("ix_generated_docs_user_id", "user_id"),
        {"schema": SCHEMA_NAME},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    doc_uuid: Mapped[str] = mapped_column(NVARCHAR(64), unique=True, nullable=False)
    user_id: Mapped[int] = mapped_column(ForeignKey(f"{SCHEMA_NAME}.users.id"), nullable=False)
    job_id: Mapped[int | None] = mapped_column(ForeignKey(f"{SCHEMA_NAME}.pdf_jobs.id"), nullable=True)
    title: Mapped[str] = mapped_column(NVARCHAR(255), nullable=False)
    filename: Mapped[str] = mapped_column(NVARCHAR(255), nullable=False)
    relative_path: Mapped[str] = mapped_column(NVARCHAR(500), nullable=False)
    operation_type: Mapped[str] = mapped_column(NVARCHAR(64), nullable=False)
    page_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    file_size_bytes: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    is_shared: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)


class SharedDocument(Base):
    __tablename__ = "shared_documents"
    __table_args__ = (
        Index("ix_shared_docs_category", "category"),
        {"schema": SCHEMA_NAME},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    document_id: Mapped[int] = mapped_column(
        ForeignKey(f"{SCHEMA_NAME}.generated_documents.id"), nullable=False
    )
    published_by_user_id: Mapped[int] = mapped_column(
        ForeignKey(f"{SCHEMA_NAME}.users.id"), nullable=False
    )
    category: Mapped[str] = mapped_column(NVARCHAR(64), nullable=False)
    title: Mapped[str] = mapped_column(NVARCHAR(255), nullable=False)
    description: Mapped[str | None] = mapped_column(NVARCHAR(1000), nullable=True)
    relative_path: Mapped[str] = mapped_column(NVARCHAR(500), nullable=False)
    is_approved: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    published_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)


class AuditLog(Base):
    __tablename__ = "audit_logs"
    __table_args__ = (
        Index("ix_audit_logs_created_at", "created_at"),
        Index("ix_audit_logs_user_id", "user_id"),
        {"schema": SCHEMA_NAME},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey(f"{SCHEMA_NAME}.users.id"), nullable=True)
    action: Mapped[str] = mapped_column(NVARCHAR(100), nullable=False)
    resource_type: Mapped[str] = mapped_column(NVARCHAR(64), nullable=False)
    resource_id: Mapped[str | None] = mapped_column(NVARCHAR(100), nullable=True)
    details: Mapped[str | None] = mapped_column(NVARCHAR(2000), nullable=True)
    ip_address: Mapped[str | None] = mapped_column(NVARCHAR(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)


class ApplicationSetting(Base):
    __tablename__ = "application_settings"
    __table_args__ = (
        UniqueConstraint("setting_key", name="uq_app_settings_key"),
        {"schema": SCHEMA_NAME},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    setting_key: Mapped[str] = mapped_column(NVARCHAR(100), nullable=False)
    setting_value: Mapped[str] = mapped_column(NVARCHAR(2000), nullable=False)
    description: Mapped[str | None] = mapped_column(NVARCHAR(500), nullable=True)
    updated_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey(f"{SCHEMA_NAME}.users.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)


class DocumentCategory(Base):
    __tablename__ = "document_categories"
    __table_args__ = (
        UniqueConstraint("name", name="uq_doc_categories_name"),
        {"schema": SCHEMA_NAME},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(NVARCHAR(100), nullable=False)
    description: Mapped[str | None] = mapped_column(NVARCHAR(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)


class DocumentTag(Base):
    __tablename__ = "document_tags"
    __table_args__ = (
        UniqueConstraint("name", name="uq_doc_tags_name"),
        {"schema": SCHEMA_NAME},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(NVARCHAR(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)


class GovernedDocument(Base):
    __tablename__ = "documents"
    __table_args__ = (
        UniqueConstraint("doc_key", name="uq_documents_doc_key"),
        Index("ix_documents_status", "status"),
        Index("ix_documents_owner", "owner_user_id"),
        {"schema": SCHEMA_NAME},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    doc_key: Mapped[str] = mapped_column(NVARCHAR(64), nullable=False)
    title: Mapped[str] = mapped_column(NVARCHAR(255), nullable=False)
    description: Mapped[str | None] = mapped_column(NVARCHAR(2000), nullable=True)
    owner_user_id: Mapped[int] = mapped_column(ForeignKey(f"{SCHEMA_NAME}.users.id"), nullable=False)
    category_id: Mapped[int | None] = mapped_column(
        ForeignKey(f"{SCHEMA_NAME}.document_categories.id"), nullable=True
    )
    technology: Mapped[str | None] = mapped_column(NVARCHAR(100), nullable=True)
    current_version: Mapped[str] = mapped_column(NVARCHAR(32), default="1.0", nullable=False)
    status: Mapped[str] = mapped_column(NVARCHAR(32), default="DRAFT", nullable=False)
    review_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    archive_reason: Mapped[str | None] = mapped_column(NVARCHAR(500), nullable=True)
    archived_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey(f"{SCHEMA_NAME}.users.id"), nullable=True
    )
    archived_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    view_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    download_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)


class DocumentVersion(Base):
    __tablename__ = "document_versions"
    __table_args__ = (
        UniqueConstraint("document_id", "version_number", name="uq_doc_version_pair"),
        Index("ix_doc_versions_doc_id", "document_id"),
        {"schema": SCHEMA_NAME},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    document_id: Mapped[int] = mapped_column(
        ForeignKey(f"{SCHEMA_NAME}.documents.id", ondelete="CASCADE"), nullable=False
    )
    version_number: Mapped[str] = mapped_column(NVARCHAR(32), nullable=False)
    filename: Mapped[str] = mapped_column(NVARCHAR(255), nullable=False)
    relative_path: Mapped[str] = mapped_column(NVARCHAR(500), nullable=False)
    file_size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    sha256_hash: Mapped[str] = mapped_column(NVARCHAR(64), nullable=False)
    uploaded_by_user_id: Mapped[int] = mapped_column(ForeignKey(f"{SCHEMA_NAME}.users.id"), nullable=False)
    status: Mapped[str] = mapped_column(NVARCHAR(32), default="DRAFT", nullable=False)
    is_immutable: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    restored_from_version_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)


class DocumentTagMapping(Base):
    __tablename__ = "document_tag_mapping"
    __table_args__ = (
        UniqueConstraint("document_id", "tag_id", name="uq_doc_tag_pair"),
        {"schema": SCHEMA_NAME},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    document_id: Mapped[int] = mapped_column(
        ForeignKey(f"{SCHEMA_NAME}.documents.id", ondelete="CASCADE"), nullable=False
    )
    tag_id: Mapped[int] = mapped_column(
        ForeignKey(f"{SCHEMA_NAME}.document_tags.id", ondelete="CASCADE"), nullable=False
    )


class DocumentApproval(Base):
    __tablename__ = "document_approvals"
    __table_args__ = (
        Index("ix_doc_approvals_doc_id", "document_id"),
        {"schema": SCHEMA_NAME},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    document_id: Mapped[int] = mapped_column(
        ForeignKey(f"{SCHEMA_NAME}.documents.id", ondelete="CASCADE"), nullable=False
    )
    version_id: Mapped[int] = mapped_column(
        ForeignKey(f"{SCHEMA_NAME}.document_versions.id"), nullable=False
    )
    reviewer_user_id: Mapped[int] = mapped_column(ForeignKey(f"{SCHEMA_NAME}.users.id"), nullable=False)
    action: Mapped[str] = mapped_column(NVARCHAR(50), nullable=False)
    from_status: Mapped[str] = mapped_column(NVARCHAR(32), nullable=False)
    to_status: Mapped[str] = mapped_column(NVARCHAR(32), nullable=False)
    comments: Mapped[str | None] = mapped_column(NVARCHAR(2000), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)


class DocumentAccessEvent(Base):
    __tablename__ = "document_access_events"
    __table_args__ = (
        Index("ix_doc_access_doc_id", "document_id"),
        {"schema": SCHEMA_NAME},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    document_id: Mapped[int] = mapped_column(
        ForeignKey(f"{SCHEMA_NAME}.documents.id", ondelete="CASCADE"), nullable=False
    )
    version_id: Mapped[int | None] = mapped_column(
        ForeignKey(f"{SCHEMA_NAME}.document_versions.id"), nullable=True
    )
    user_id: Mapped[int] = mapped_column(ForeignKey(f"{SCHEMA_NAME}.users.id"), nullable=False)
    event_type: Mapped[str] = mapped_column(NVARCHAR(32), nullable=False)  # VIEW, DOWNLOAD
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
