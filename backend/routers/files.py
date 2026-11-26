"""File upload, listing, and isolated download endpoints."""
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.config import get_settings
from backend.database.models import GeneratedDocument, UploadedFile
from backend.database.session import get_db
from backend.security.auth import AuthenticatedUser, get_current_user
from backend.security.storage import (
    ALL_ALLOWED_EXTENSIONS,
    resolve_safe_path,
    save_user_upload,
)
from backend.services.job_service import log_audit

router = APIRouter(prefix="/api/files", tags=["Files"])


@router.post("/upload")
async def upload_file(
    file: UploadFile = File(...),
    user: AuthenticatedUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    if not file.filename:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Filename missing.")
    content = await file.read()
    saved = save_user_upload(
        storage_folder=user.storage_folder,
        original_filename=file.filename,
        content=content,
        allowed_extensions=ALL_ALLOWED_EXTENSIONS,
    )
    record = UploadedFile(
        file_uuid=str(saved["file_uuid"]),
        user_id=user.id,
        original_filename=str(saved["original_filename"]),
        stored_filename=str(saved["stored_filename"]),
        relative_path=str(saved["relative_path"]),
        mime_type=file.content_type or "application/octet-stream",
        file_ext=str(saved["file_ext"]),
        file_size_bytes=int(saved["file_size_bytes"]),
        sha256_hash=str(saved["sha256_hash"]),
    )
    db.add(record)
    log_audit(db, user.id, "FILE_UPLOADED", "uploaded_file", record.file_uuid, record.original_filename)
    db.commit()
    return {
        "file_uuid": record.file_uuid,
        "original_filename": record.original_filename,
        "relative_path": record.relative_path,
        "file_ext": record.file_ext,
        "file_size_bytes": record.file_size_bytes,
    }


@router.get("/uploads")
def list_my_uploads(
    user: AuthenticatedUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[dict]:
    rows = db.scalars(
        select(UploadedFile)
        .where(UploadedFile.user_id == user.id)
        .order_by(UploadedFile.created_at.desc())
        .limit(100)
    ).all()
    return [
        {
            "file_uuid": r.file_uuid,
            "original_filename": r.original_filename,
            "relative_path": r.relative_path,
            "file_ext": r.file_ext,
            "file_size_bytes": r.file_size_bytes,
            "created_at": r.created_at.isoformat(),
        }
        for r in rows
    ]


@router.get("/documents")
def list_my_documents(
    user: AuthenticatedUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[dict]:
    rows = db.scalars(
        select(GeneratedDocument)
        .where(GeneratedDocument.user_id == user.id)
        .order_by(GeneratedDocument.created_at.desc())
        .limit(100)
    ).all()
    return [
        {
            "id": r.id,
            "doc_uuid": r.doc_uuid,
            "title": r.title,
            "filename": r.filename,
            "operation_type": r.operation_type,
            "page_count": r.page_count,
            "file_size_bytes": r.file_size_bytes,
            "is_shared": r.is_shared,
            "created_at": r.created_at.isoformat(),
        }
        for r in rows
    ]


@router.get("/documents/{doc_uuid}/download")
def download_my_document(
    doc_uuid: str,
    user: AuthenticatedUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> FileResponse:
    doc = db.scalar(select(GeneratedDocument).where(GeneratedDocument.doc_uuid == doc_uuid))
    if doc is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found.")
    if doc.user_id != user.id and not user.has_any_role("Admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: you do not own this document.",
        )
    settings = get_settings()
    user_root = (settings.STORAGE_ROOT / "users" / user.storage_folder).resolve()
    if user.has_any_role("Admin"):
        allowed_root = settings.STORAGE_ROOT.resolve()
    else:
        allowed_root = user_root

    file_path = resolve_safe_path(
        doc.relative_path if allowed_root == settings.STORAGE_ROOT.resolve()
        else doc.relative_path.removeprefix(f"users/{user.storage_folder}/"),
        allowed_root,
    )
    if not file_path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="PDF file missing on disk.")
    return FileResponse(path=str(file_path), filename=doc.filename, media_type="application/pdf")
