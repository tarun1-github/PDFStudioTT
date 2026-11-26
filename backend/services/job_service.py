"""MSSQL-backed job queue, claiming with SQL Server row locks, and audit logging."""
import json
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from backend.config import get_settings
from backend.database.models import AuditLog, GeneratedDocument, PdfJob

JOB_QUEUED = "QUEUED"
JOB_PROCESSING = "PROCESSING"
JOB_COMPLETED = "COMPLETED"
JOB_FAILED = "FAILED"
JOB_CANCELLED = "CANCELLED"


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def log_audit(
    db: Session,
    user_id: int | None,
    action: str,
    resource_type: str,
    resource_id: str | None = None,
    details: str | None = None,
    ip_address: str | None = None,
) -> None:
    db.add(
        AuditLog(
            user_id=user_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            details=details[:2000] if details else None,
            ip_address=ip_address,
        )
    )


def submit_job(
    db: Session,
    user_id: int,
    job_type: str,
    payload: dict[str, Any],
) -> PdfJob:
    settings = get_settings()
    job = PdfJob(
        job_uuid=uuid.uuid4().hex,
        user_id=user_id,
        job_type=job_type,
        status=JOB_QUEUED,
        progress_pct=0,
        payload_json=json.dumps(payload),
        max_retries=settings.JOB_MAX_RETRIES,
    )
    db.add(job)
    db.flush()
    log_audit(db, user_id, "JOB_SUBMITTED", "pdf_job", job.job_uuid, f"type={job_type}")
    db.commit()
    db.refresh(job)
    return job


def claim_next_job(db: Session, worker_id: str) -> PdfJob | None:
    """Atomically claim one QUEUED job using SQL Server UPDLOCK + READPAST."""
    dialect_name = db.bind.dialect.name if db.bind else ""
    if dialect_name == "mssql":
        row = db.execute(
            text(
                """
                SELECT TOP 1 id
                FROM pdfstudio.pdf_jobs WITH (UPDLOCK, READPAST, ROWLOCK)
                WHERE status = :queued
                ORDER BY created_at ASC, id ASC
                """
            ),
            {"queued": JOB_QUEUED},
        ).fetchone()
        job = db.get(PdfJob, row[0]) if row else None
    else:
        job = db.scalar(
            select(PdfJob)
            .where(PdfJob.status == JOB_QUEUED)
            .order_by(PdfJob.created_at.asc(), PdfJob.id.asc())
            .limit(1)
        )

    if job is None:
        return None

    job.status = JOB_PROCESSING
    job.worker_id = worker_id
    job.started_at = utcnow()
    job.progress_pct = 10
    db.commit()
    db.refresh(job)
    return job


def mark_job_completed(
    db: Session,
    job: PdfJob,
    doc_title: str,
    filename: str,
    relative_path: str,
    operation_type: str,
    page_count: int,
    file_size_bytes: int,
) -> GeneratedDocument:
    doc = GeneratedDocument(
        doc_uuid=uuid.uuid4().hex,
        user_id=job.user_id,
        job_id=job.id,
        title=doc_title[:255],
        filename=filename[:255],
        relative_path=relative_path[:500],
        operation_type=operation_type,
        page_count=page_count,
        file_size_bytes=file_size_bytes,
        is_shared=False,
    )
    db.add(doc)
    db.flush()

    job.status = JOB_COMPLETED
    job.progress_pct = 100
    job.result_document_id = doc.id
    job.completed_at = utcnow()
    job.error_message = None
    log_audit(db, job.user_id, "JOB_COMPLETED", "pdf_job", job.job_uuid, f"doc={doc.doc_uuid}")
    db.commit()
    db.refresh(doc)
    return doc


def mark_job_failed(db: Session, job: PdfJob, error_message: str) -> None:
    job.retry_count += 1
    if job.retry_count <= job.max_retries:
        job.status = JOB_QUEUED
        job.progress_pct = 0
        job.error_message = f"Retry {job.retry_count}/{job.max_retries}: {error_message[:1800]}"
    else:
        job.status = JOB_FAILED
        job.completed_at = utcnow()
        job.error_message = error_message[:2000]
        log_audit(db, job.user_id, "JOB_FAILED", "pdf_job", job.job_uuid, error_message[:500])
    db.commit()
