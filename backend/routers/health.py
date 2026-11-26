"""Health check endpoints for API, MSSQL database, and system dependencies."""
import shutil
from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.config import get_settings
from backend.database.connection import check_database_health, get_engine
from backend.database.models import PdfJob
from backend.database.session import get_db
from backend.security.storage import ensure_storage_layout
from backend.services.document_pdf_service import detect_libreoffice
from backend.services.document_sequence_service import detect_ocr_engine
from backend.services.job_service import JOB_FAILED, JOB_PROCESSING, JOB_QUEUED

router = APIRouter(prefix="/health", tags=["Health"])


@router.get("")
def api_health() -> dict[str, str]:
    settings = get_settings()
    return {"status": "ok", "app": settings.APP_NAME, "env": settings.APP_ENV}


@router.get("/db")
def db_health() -> dict:
    return check_database_health()


@router.get("/dependencies")
def dependencies_health() -> dict:
    settings = get_settings()
    lo_path = detect_libreoffice()
    storage_path = ensure_storage_layout(settings.STORAGE_ROOT)
    usage = shutil.disk_usage(storage_path)
    return {
        "libreoffice_installed": bool(lo_path),
        "libreoffice_path": lo_path,
        "storage_root": str(settings.STORAGE_ROOT),
        "storage_ready": storage_path.exists(),
        "disk_free_gb": round(usage.free / (1024 ** 3), 2),
        "disk_total_gb": round(usage.total / (1024 ** 3), 2),
        "ocr_engine": detect_ocr_engine(),
        "oidc_enabled": settings.OIDC_ENABLED,
    }


@router.get("/operations")
def operations_health(db: Session = Depends(get_db)) -> dict:
    """Operational metrics for backlog, failures, disk space, and SQL pool."""
    deps = dependencies_health()
    queued = db.scalar(select(func.count(PdfJob.id)).where(PdfJob.status == JOB_QUEUED)) or 0
    processing = db.scalar(select(func.count(PdfJob.id)).where(PdfJob.status == JOB_PROCESSING)) or 0
    failed = db.scalar(select(func.count(PdfJob.id)).where(PdfJob.status == JOB_FAILED)) or 0
    oldest_queued = db.scalar(
        select(func.min(PdfJob.created_at)).where(PdfJob.status == JOB_QUEUED)
    )
    oldest_age_sec = 0.0
    if oldest_queued is not None:
        now_naive = datetime.now(timezone.utc).replace(tzinfo=None)
        oldest_age_sec = round(max(0.0, (now_naive - oldest_queued).total_seconds()), 1)

    pool_status = {}
    try:
        pool = get_engine().pool
        pool_status = {
            "pool_size": getattr(pool, "size", lambda: 0)(),
            "checked_out": getattr(pool, "checkedout", lambda: 0)(),
            "overflow": getattr(pool, "overflow", lambda: 0)(),
        }
    except Exception:
        pool_status = {"pool_size": 0, "checked_out": 0, "overflow": 0}

    return {
        "queued_jobs": int(queued),
        "processing_jobs": int(processing),
        "failed_jobs": int(failed),
        "oldest_queued_seconds": oldest_age_sec,
        "disk_free_gb": deps["disk_free_gb"],
        "libreoffice_installed": deps["libreoffice_installed"],
        "sql_pool": pool_status,
    }
