"""Team Document Governance, Version Control, Knowledge Library, Comparison & Analytics API."""
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from backend.config import get_settings
from backend.database.models import (
    DocumentApproval,
    DocumentCategory,
    DocumentTag,
    DocumentTagMapping,
    DocumentVersion,
    GovernedDocument,
    User,
)
from backend.database.session import get_db
from backend.security.auth import ROLE_ADMIN, ROLE_TEAM_LEAD, AuthenticatedUser, get_current_user, require_roles
from backend.security.storage import resolve_safe_path
from backend.services.document_comparison_service import compare_pdf_versions
from backend.services.governance_service import (
    STATUS_ARCHIVED,
    STATUS_PUBLISHED,
    add_document_revision,
    create_governed_document,
    get_governance_analytics,
    record_access_event,
    restore_version_as_revision,
    transition_document_status,
)

router = APIRouter(prefix="/api/governance", tags=["Governance"])


class CreateCategoryRequest(BaseModel):
    name: str
    description: str = ""


class CreateGovernedDocRequest(BaseModel):
    title: str
    description: str = ""
    category: str = "General Technical Documentation"
    technology: str = ""
    tags: list[str] = []
    source_relative_path: str
    review_days: int | None = None


class AddRevisionRequest(BaseModel):
    source_relative_path: str
    bump_type: str = "minor"
    allow_duplicate_hash: bool = False


class TransitionRequest(BaseModel):
    target_status: str
    comments: str = ""


def _resolve_user_file(user: AuthenticatedUser, relative_path: str) -> Path:
    settings = get_settings()
    user_root = (settings.STORAGE_ROOT / "users" / user.storage_folder).resolve()
    rel = relative_path.removeprefix(f"users/{user.storage_folder}/")
    return resolve_safe_path(rel, user_root)


def _get_doc_or_404(db: Session, doc_key: str) -> GovernedDocument:
    doc = db.scalar(select(GovernedDocument).where(GovernedDocument.doc_key == doc_key))
    if doc is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found.")
    return doc


def _can_read_doc(user: AuthenticatedUser, doc: GovernedDocument) -> bool:
    if doc.status == STATUS_PUBLISHED:
        return True
    if doc.owner_user_id == user.id:
        return True
    if user.has_any_role(ROLE_TEAM_LEAD, ROLE_ADMIN):
        return True
    return False


@router.get("/categories")
def list_categories(
    _user: AuthenticatedUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[dict]:
    rows = db.scalars(select(DocumentCategory).order_by(DocumentCategory.name.asc())).all()
    return [{"id": r.id, "name": r.name, "description": r.description} for r in rows]


@router.post("/categories")
def create_category(
    req: CreateCategoryRequest,
    _admin: AuthenticatedUser = Depends(require_roles(ROLE_ADMIN)),
    db: Session = Depends(get_db),
) -> dict:
    existing = db.scalar(select(DocumentCategory).where(DocumentCategory.name == req.name.strip()))
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Category already exists.")
    cat = DocumentCategory(name=req.name.strip()[:100], description=req.description.strip()[:255] or None)
    db.add(cat)
    db.commit()
    db.refresh(cat)
    return {"id": cat.id, "name": cat.name}


@router.get("/documents")
def search_documents(
    q: str = "",
    category: str = "",
    technology: str = "",
    doc_status: str = "",
    version: str = "",
    sort_by: str = Query(default="latest", pattern="^(latest|most_downloaded)$"),
    user: AuthenticatedUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[dict]:
    stmt = select(GovernedDocument)
    if not user.has_any_role(ROLE_TEAM_LEAD, ROLE_ADMIN):
        stmt = stmt.where(
            or_(GovernedDocument.status == STATUS_PUBLISHED, GovernedDocument.owner_user_id == user.id)
        )
    if doc_status:
        stmt = stmt.where(GovernedDocument.status == doc_status)
    if technology:
        stmt = stmt.where(GovernedDocument.technology.ilike(f"%{technology}%"))
    if version:
        stmt = stmt.where(GovernedDocument.current_version == version)
    if category:
        cat_obj = db.scalar(select(DocumentCategory).where(DocumentCategory.name == category))
        if cat_obj:
            stmt = stmt.where(GovernedDocument.category_id == cat_obj.id)
        else:
            return []

    if sort_by == "most_downloaded":
        stmt = stmt.order_by(GovernedDocument.download_count.desc(), GovernedDocument.updated_at.desc())
    else:
        stmt = stmt.order_by(GovernedDocument.updated_at.desc())

    docs = db.scalars(stmt.limit(100)).all()
    q_low = q.strip().lower()
    results: list[dict] = []
    for d in docs:
        tag_names = list(
            db.scalars(
                select(DocumentTag.name)
                .join(DocumentTagMapping, DocumentTagMapping.tag_id == DocumentTag.id)
                .where(DocumentTagMapping.document_id == d.id)
            ).all()
        )
        cat_name = db.scalar(select(DocumentCategory.name).where(DocumentCategory.id == d.category_id)) or ""
        owner_name = db.scalar(select(User.username).where(User.id == d.owner_user_id)) or ""

        if q_low:
            haystack = f"{d.title} {d.description or ''} {' '.join(tag_names)} {cat_name}".lower()
            if q_low not in haystack:
                continue

        results.append(
            {
                "doc_key": d.doc_key,
                "title": d.title,
                "description": d.description,
                "category": cat_name,
                "technology": d.technology,
                "owner": owner_name,
                "current_version": d.current_version,
                "status": d.status,
                "tags": tag_names,
                "view_count": d.view_count,
                "download_count": d.download_count,
                "review_date": d.review_date.isoformat() if d.review_date else None,
                "created_at": d.created_at.isoformat(),
                "updated_at": d.updated_at.isoformat(),
            }
        )
    return results


@router.post("/documents")
def create_document(
    req: CreateGovernedDocRequest,
    user: AuthenticatedUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    src = _resolve_user_file(user, req.source_relative_path)
    doc, ver = create_governed_document(
        db=db,
        user=user,
        title=req.title,
        description=req.description,
        category_name=req.category,
        technology=req.technology,
        tags=req.tags,
        source_path=src,
        original_filename=src.name,
        review_days=req.review_days,
    )
    return {
        "doc_key": doc.doc_key,
        "version_number": ver.version_number,
        "status": doc.status,
        "sha256_hash": ver.sha256_hash,
    }


@router.post("/documents/{doc_key}/versions")
def upload_new_revision(
    doc_key: str,
    req: AddRevisionRequest,
    user: AuthenticatedUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    doc = _get_doc_or_404(db, doc_key)
    src = _resolve_user_file(user, req.source_relative_path)
    ver = add_document_revision(
        db=db,
        user=user,
        doc=doc,
        source_path=src,
        original_filename=src.name,
        bump_type=req.bump_type,
        allow_duplicate_hash=req.allow_duplicate_hash,
    )
    return {
        "version_id": ver.id,
        "version_number": ver.version_number,
        "status": ver.status,
        "sha256_hash": ver.sha256_hash,
    }


@router.get("/documents/{doc_key}/versions")
def list_versions(
    doc_key: str,
    user: AuthenticatedUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[dict]:
    doc = _get_doc_or_404(db, doc_key)
    if not _can_read_doc(user, doc):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied.")
    record_access_event(db, doc, None, user.id, "VIEW")
    rows = db.scalars(
        select(DocumentVersion)
        .where(DocumentVersion.document_id == doc.id)
        .order_by(DocumentVersion.id.desc())
    ).all()
    return [
        {
            "id": r.id,
            "version_number": r.version_number,
            "filename": r.filename,
            "file_size_bytes": r.file_size_bytes,
            "sha256_hash": r.sha256_hash,
            "status": r.status,
            "is_immutable": r.is_immutable,
            "created_at": r.created_at.isoformat(),
        }
        for r in rows
    ]


@router.get("/documents/{doc_key}/versions/{version_id}/download")
def download_version(
    doc_key: str,
    version_id: int,
    user: AuthenticatedUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> FileResponse:
    doc = _get_doc_or_404(db, doc_key)
    if doc.status == STATUS_ARCHIVED and not user.has_any_role(ROLE_TEAM_LEAD, ROLE_ADMIN):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Archived documents are restricted.")
    if not _can_read_doc(user, doc):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied.")

    ver = db.get(DocumentVersion, version_id)
    if ver is None or ver.document_id != doc.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Version not found.")

    root = get_settings().STORAGE_ROOT.resolve()
    file_path = resolve_safe_path(ver.relative_path, root)
    if not file_path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Version file missing on disk.")

    record_access_event(db, doc, ver.id, user.id, "DOWNLOAD")
    return FileResponse(path=str(file_path), filename=ver.filename, media_type="application/pdf")


@router.post("/documents/{doc_key}/versions/{version_id}/restore")
def restore_version(
    doc_key: str,
    version_id: int,
    user: AuthenticatedUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    doc = _get_doc_or_404(db, doc_key)
    ver = db.get(DocumentVersion, version_id)
    if ver is None or ver.document_id != doc.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Version not found.")
    new_ver = restore_version_as_revision(db, user, doc, ver)
    return {"version_id": new_ver.id, "version_number": new_ver.version_number, "status": new_ver.status}


@router.post("/documents/{doc_key}/transition")
def transition_status(
    doc_key: str,
    req: TransitionRequest,
    user: AuthenticatedUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    doc = _get_doc_or_404(db, doc_key)
    updated = transition_document_status(db, user, doc, req.target_status, req.comments)
    return {"doc_key": updated.doc_key, "status": updated.status, "current_version": updated.current_version}


@router.get("/documents/{doc_key}/approvals")
def list_approvals(
    doc_key: str,
    user: AuthenticatedUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[dict]:
    doc = _get_doc_or_404(db, doc_key)
    if not _can_read_doc(user, doc):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied.")
    rows = db.scalars(
        select(DocumentApproval)
        .where(DocumentApproval.document_id == doc.id)
        .order_by(DocumentApproval.created_at.desc())
    ).all()
    return [
        {
            "action": r.action,
            "from_status": r.from_status,
            "to_status": r.to_status,
            "comments": r.comments,
            "created_at": r.created_at.isoformat(),
        }
        for r in rows
    ]


@router.get("/documents/{doc_key}/compare")
def compare_versions(
    doc_key: str,
    old_version_id: int,
    new_version_id: int,
    user: AuthenticatedUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    doc = _get_doc_or_404(db, doc_key)
    if not _can_read_doc(user, doc):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied.")
    v_old = db.get(DocumentVersion, old_version_id)
    v_new = db.get(DocumentVersion, new_version_id)
    if not v_old or not v_new or v_old.document_id != doc.id or v_new.document_id != doc.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Version(s) not found.")
    root = get_settings().STORAGE_ROOT.resolve()
    return compare_pdf_versions(
        resolve_safe_path(v_old.relative_path, root),
        resolve_safe_path(v_new.relative_path, root),
    )


@router.get("/analytics")
def governance_analytics(
    user: AuthenticatedUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    return get_governance_analytics(db, user)
