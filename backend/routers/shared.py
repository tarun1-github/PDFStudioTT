"""Shared document library endpoints with Team Lead/Admin publishing authorization."""
import shutil
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.config import get_settings
from backend.database.models import GeneratedDocument, SharedDocument
from backend.database.session import get_db
from backend.security.auth import (
    ROLE_ADMIN,
    ROLE_TEAM_LEAD,
    AuthenticatedUser,
    get_current_user,
    require_roles,
)
from backend.security.storage import SHARED_CATEGORIES, resolve_safe_path, sanitize_filename
from backend.services.job_service import log_audit

router = APIRouter(prefix="/api/shared", tags=["Shared Library"])


class PublishRequest(BaseModel):
    doc_uuid: str
    category: str
    title: str
    description: str = ""


@router.get("")
def list_shared_documents(
    category: str | None = None,
    _user: AuthenticatedUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[dict]:
    stmt = select(SharedDocument).where(SharedDocument.is_approved == True)  # noqa: E712
    if category:
        stmt = stmt.where(SharedDocument.category == category)
    rows = db.scalars(stmt.order_by(SharedDocument.published_at.desc())).all()
    return [
        {
            "id": r.id,
            "category": r.category,
            "title": r.title,
            "description": r.description,
            "relative_path": r.relative_path,
            "published_at": r.published_at.isoformat(),
        }
        for r in rows
    ]


@router.post("/publish")
def publish_document(
    req: PublishRequest,
    user: AuthenticatedUser = Depends(require_roles(ROLE_TEAM_LEAD, ROLE_ADMIN)),
    db: Session = Depends(get_db),
) -> dict:
    if req.category not in SHARED_CATEGORIES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Category must be one of: {', '.join(SHARED_CATEGORIES)}",
        )
    doc = db.scalar(select(GeneratedDocument).where(GeneratedDocument.doc_uuid == req.doc_uuid))
    if doc is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found.")

    settings = get_settings()
    storage_root = settings.STORAGE_ROOT.resolve()
    src_path = resolve_safe_path(doc.relative_path, storage_root)
    if not src_path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Source PDF missing.")

    safe_name = sanitize_filename(doc.filename)
    dest_dir = (storage_root / "shared" / req.category).resolve()
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest_path = (dest_dir / f"{doc.doc_uuid[:8]}_{safe_name}").resolve()
    shutil.copy2(src_path, dest_path)

    rel_shared = dest_path.relative_to(storage_root).as_posix()
    shared = SharedDocument(
        document_id=doc.id,
        published_by_user_id=user.id,
        category=req.category,
        title=req.title.strip()[:255] or doc.title,
        description=req.description.strip()[:1000] or None,
        relative_path=rel_shared,
        is_approved=True,
    )
    doc.is_shared = True
    db.add(shared)
    log_audit(db, user.id, "DOCUMENT_PUBLISHED", "shared_document", doc.doc_uuid, f"category={req.category}")
    db.commit()
    db.refresh(shared)
    return {"id": shared.id, "title": shared.title, "category": shared.category}


@router.get("/{shared_id}/download")
def download_shared_document(
    shared_id: int,
    _user: AuthenticatedUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> FileResponse:
    shared = db.get(SharedDocument, shared_id)
    if shared is None or not shared.is_approved:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Shared document not found.")
    settings = get_settings()
    shared_root = (settings.STORAGE_ROOT / "shared").resolve()
    rel = shared.relative_path.removeprefix("shared/")
    file_path = resolve_safe_path(rel, shared_root)
    if not file_path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Shared file missing on disk.")
    return FileResponse(path=str(file_path), filename=file_path.name, media_type="application/pdf")
