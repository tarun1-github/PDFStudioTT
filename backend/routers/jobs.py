"""Job queue and dashboard KPI endpoints."""
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.database.models import GeneratedDocument, PdfJob, UploadedFile, User
from backend.database.session import get_db
from backend.security.auth import AuthenticatedUser, get_current_user
from backend.services.job_service import (
    JOB_CANCELLED,
    JOB_COMPLETED,
    JOB_FAILED,
    JOB_QUEUED,
    submit_job,
)

router = APIRouter(prefix="/api/jobs", tags=["Jobs"])


class SubmitJobRequest(BaseModel):
    job_type: str
    payload: dict


@router.post("")
def create_job(
    req: SubmitJobRequest,
    user: AuthenticatedUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    job = submit_job(db, user.id, req.job_type, req.payload)
    return {
        "id": job.id,
        "job_uuid": job.job_uuid,
        "job_type": job.job_type,
        "status": job.status,
        "created_at": job.created_at.isoformat(),
    }


@router.get("")
def list_jobs(
    user: AuthenticatedUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[dict]:
    stmt = select(PdfJob).order_by(PdfJob.created_at.desc()).limit(100)
    if not user.has_any_role("Team Lead", "Admin"):
        stmt = stmt.where(PdfJob.user_id == user.id)
    rows = db.scalars(stmt).all()
    return [
        {
            "job_uuid": j.job_uuid,
            "user_id": j.user_id,
            "job_type": j.job_type,
            "status": j.status,
            "progress_pct": j.progress_pct,
            "error_message": j.error_message,
            "created_at": j.created_at.isoformat(),
            "completed_at": j.completed_at.isoformat() if j.completed_at else None,
        }
        for j in rows
    ]


@router.get("/{job_uuid}")
def get_job(
    job_uuid: str,
    user: AuthenticatedUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    job = db.scalar(select(PdfJob).where(PdfJob.job_uuid == job_uuid))
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found.")
    if job.user_id != user.id and not user.has_any_role("Team Lead", "Admin"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied.")
    return {
        "job_uuid": job.job_uuid,
        "job_type": job.job_type,
        "status": job.status,
        "progress_pct": job.progress_pct,
        "result_document_id": job.result_document_id,
        "error_message": job.error_message,
        "created_at": job.created_at.isoformat(),
    }


@router.post("/{job_uuid}/cancel")
def cancel_job(
    job_uuid: str,
    user: AuthenticatedUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    job = db.scalar(select(PdfJob).where(PdfJob.job_uuid == job_uuid))
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found.")
    if job.user_id != user.id and not user.has_any_role("Admin"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied.")
    if job.status != JOB_QUEUED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Only QUEUED jobs can be cancelled (current: {job.status}).",
        )
    job.status = JOB_CANCELLED
    db.commit()
    return {"job_uuid": job.job_uuid, "status": job.status}


@router.get("/stats/kpis")
def dashboard_kpis(
    _user: AuthenticatedUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    total_docs_processed = db.scalar(select(func.count(UploadedFile.id))) or 0
    pdfs_generated = db.scalar(select(func.count(GeneratedDocument.id))) or 0
    total_storage_bytes = db.scalar(select(func.coalesce(func.sum(GeneratedDocument.file_size_bytes), 0))) or 0
    successful_jobs = db.scalar(
        select(func.count(PdfJob.id)).where(PdfJob.status == JOB_COMPLETED)
    ) or 0
    failed_jobs = db.scalar(
        select(func.count(PdfJob.id)).where(PdfJob.status == JOB_FAILED)
    ) or 0
    active_users = db.scalar(
        select(func.count(User.id)).where(User.is_active == True)  # noqa: E712
    ) or 0
    return {
        "total_documents_processed": int(total_docs_processed),
        "pdfs_generated": int(pdfs_generated),
        "total_storage_bytes": int(total_storage_bytes),
        "successful_jobs": int(successful_jobs),
        "failed_jobs": int(failed_jobs),
        "active_users": int(active_users),
    }
