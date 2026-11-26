"""Team Document Governance, Version Control, Approval Workflow & Analytics Service."""
import hashlib
import shutil
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from backend.config import get_settings
from backend.database.models import (
    DocumentAccessEvent,
    DocumentApproval,
    DocumentCategory,
    DocumentTag,
    DocumentTagMapping,
    DocumentVersion,
    GovernedDocument,
)
from backend.security.auth import ROLE_ADMIN, ROLE_TEAM_LEAD, AuthenticatedUser
from backend.security.storage import ensure_storage_layout, resolve_safe_path, sanitize_filename
from backend.services.job_service import log_audit

STATUS_DRAFT = "DRAFT"
STATUS_SUBMITTED = "SUBMITTED"
STATUS_UNDER_REVIEW = "UNDER_REVIEW"
STATUS_CHANGES_REQUESTED = "CHANGES_REQUESTED"
STATUS_APPROVED = "APPROVED"
STATUS_PUBLISHED = "PUBLISHED"
STATUS_REJECTED = "REJECTED"
STATUS_ARCHIVED = "ARCHIVED"

VALID_STATUSES = {
    STATUS_DRAFT,
    STATUS_SUBMITTED,
    STATUS_UNDER_REVIEW,
    STATUS_CHANGES_REQUESTED,
    STATUS_APPROVED,
    STATUS_PUBLISHED,
    STATUS_REJECTED,
    STATUS_ARCHIVED,
}

ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    STATUS_DRAFT: {STATUS_SUBMITTED},
    STATUS_SUBMITTED: {STATUS_UNDER_REVIEW, STATUS_CHANGES_REQUESTED, STATUS_APPROVED, STATUS_REJECTED},
    STATUS_UNDER_REVIEW: {STATUS_CHANGES_REQUESTED, STATUS_APPROVED, STATUS_REJECTED},
    STATUS_CHANGES_REQUESTED: {STATUS_SUBMITTED},
    STATUS_APPROVED: {STATUS_PUBLISHED, STATUS_ARCHIVED},
    STATUS_PUBLISHED: {STATUS_ARCHIVED},
    STATUS_REJECTED: {STATUS_DRAFT, STATUS_SUBMITTED},
    STATUS_ARCHIVED: set(),
}


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def bump_version(current: str, bump_type: str = "minor") -> str:
    parts = [int(p) for p in current.split(".") if p.isdigit()]
    major = parts[0] if len(parts) >= 1 else 1
    minor = parts[1] if len(parts) >= 2 else 0
    if bump_type.lower() == "major":
        return f"{major + 1}.0"
    return f"{major}.{minor + 1}"


def _governed_storage_dir(doc_key: str, version_number: str) -> Path:
    root = ensure_storage_layout(get_settings().STORAGE_ROOT)
    d = (root / "shared" / "governed" / doc_key / f"v{version_number}").resolve()
    if not d.is_relative_to(root / "shared"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid governed storage path.")
    d.mkdir(parents=True, exist_ok=True)
    return d


def _sync_tags(db: Session, document_id: int, tags: list[str]) -> None:
    existing_links = db.scalars(
        select(DocumentTagMapping).where(DocumentTagMapping.document_id == document_id)
    ).all()
    for link in existing_links:
        db.delete(link)
    db.flush()

    seen: set[str] = set()
    for raw in tags:
        name = raw.strip().lower()[:64]
        if not name or name in seen:
            continue
        seen.add(name)
        tag = db.scalar(select(DocumentTag).where(DocumentTag.name == name))
        if tag is None:
            tag = DocumentTag(name=name)
            db.add(tag)
            db.flush()
        db.add(DocumentTagMapping(document_id=document_id, tag_id=tag.id))


def create_governed_document(
    db: Session,
    user: AuthenticatedUser,
    title: str,
    description: str,
    category_name: str,
    technology: str,
    tags: list[str],
    source_path: Path,
    original_filename: str,
    review_days: int | None = None,
) -> tuple[GovernedDocument, DocumentVersion]:
    if not source_path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Source file not found.")

    cat = db.scalar(select(DocumentCategory).where(DocumentCategory.name == category_name))
    if cat is None:
        cat = DocumentCategory(name=category_name.strip()[:100], is_active=True)
        db.add(cat)
        db.flush()

    doc_key = uuid.uuid4().hex
    version_num = "1.0"
    dest_dir = _governed_storage_dir(doc_key, version_num)
    safe_name = sanitize_filename(original_filename)
    dest_file = (dest_dir / safe_name).resolve()
    shutil.copy2(source_path, dest_file)

    data = dest_file.read_bytes()
    sha = hashlib.sha256(data).hexdigest()
    root = get_settings().STORAGE_ROOT.resolve()
    rel_path = dest_file.relative_to(root).as_posix()

    rev_dt = (utcnow() + timedelta(days=review_days)) if review_days else None
    doc = GovernedDocument(
        doc_key=doc_key,
        title=title.strip()[:255],
        description=description.strip()[:2000] or None,
        owner_user_id=user.id,
        category_id=cat.id,
        technology=technology.strip()[:100] or None,
        current_version=version_num,
        status=STATUS_DRAFT,
        review_date=rev_dt,
    )
    db.add(doc)
    db.flush()

    ver = DocumentVersion(
        document_id=doc.id,
        version_number=version_num,
        filename=safe_name,
        relative_path=rel_path,
        file_size_bytes=len(data),
        sha256_hash=sha,
        uploaded_by_user_id=user.id,
        status=STATUS_DRAFT,
        is_immutable=False,
    )
    db.add(ver)
    db.flush()
    _sync_tags(db, doc.id, tags)
    log_audit(db, user.id, "GOV_DOC_CREATED", "document", doc.doc_key, f"v={version_num}")
    db.commit()
    db.refresh(doc)
    db.refresh(ver)
    return doc, ver


def add_document_revision(
    db: Session,
    user: AuthenticatedUser,
    doc: GovernedDocument,
    source_path: Path,
    original_filename: str,
    bump_type: str = "minor",
    allow_duplicate_hash: bool = False,
) -> DocumentVersion:
    if doc.owner_user_id != user.id and not user.has_any_role(ROLE_ADMIN):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only owner or Admin can add revisions.")
    if doc.status == STATUS_ARCHIVED:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Archived documents cannot accept new revisions.")

    data = source_path.read_bytes()
    sha = hashlib.sha256(data).hexdigest()
    if not allow_duplicate_hash:
        dup = db.scalar(
            select(DocumentVersion).where(
                DocumentVersion.document_id == doc.id,
                DocumentVersion.sha256_hash == sha,
            )
        )
        if dup is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Identical content (SHA-256) already exists in version {dup.version_number}.",
            )

    new_ver_num = bump_version(doc.current_version, bump_type)
    dest_dir = _governed_storage_dir(doc.doc_key, new_ver_num)
    safe_name = sanitize_filename(original_filename)
    dest_file = (dest_dir / safe_name).resolve()
    shutil.copy2(source_path, dest_file)
    root = get_settings().STORAGE_ROOT.resolve()
    rel_path = dest_file.relative_to(root).as_posix()

    ver = DocumentVersion(
        document_id=doc.id,
        version_number=new_ver_num,
        filename=safe_name,
        relative_path=rel_path,
        file_size_bytes=len(data),
        sha256_hash=sha,
        uploaded_by_user_id=user.id,
        status=STATUS_DRAFT,
        is_immutable=False,
    )
    doc.current_version = new_ver_num
    doc.status = STATUS_DRAFT
    db.add(ver)
    log_audit(db, user.id, "GOV_VERSION_ADDED", "document", doc.doc_key, f"v={new_ver_num}")
    db.commit()
    db.refresh(ver)
    return ver


def restore_version_as_revision(
    db: Session,
    user: AuthenticatedUser,
    doc: GovernedDocument,
    source_ver: DocumentVersion,
) -> DocumentVersion:
    root = get_settings().STORAGE_ROOT.resolve()
    src_path = resolve_safe_path(source_ver.relative_path, root)
    ver = add_document_revision(
        db=db,
        user=user,
        doc=doc,
        source_path=src_path,
        original_filename=source_ver.filename,
        bump_type="minor",
        allow_duplicate_hash=True,
    )
    ver.restored_from_version_id = source_ver.id
    log_audit(
        db,
        user.id,
        "GOV_VERSION_RESTORED",
        "document",
        doc.doc_key,
        f"from={source_ver.version_number} to={ver.version_number}",
    )
    db.commit()
    db.refresh(ver)
    return ver


def transition_document_status(
    db: Session,
    user: AuthenticatedUser,
    doc: GovernedDocument,
    target_status: str,
    comments: str = "",
) -> GovernedDocument:
    if target_status not in VALID_STATUSES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid target status.")
    if target_status not in ALLOWED_TRANSITIONS.get(doc.status, set()):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Transition {doc.status} -> {target_status} is not allowed.",
        )

    latest_ver = db.scalar(
        select(DocumentVersion)
        .where(DocumentVersion.document_id == doc.id, DocumentVersion.version_number == doc.current_version)
    )
    if latest_ver is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Current version record missing.")

    if target_status == STATUS_SUBMITTED:
        if doc.owner_user_id != user.id and not user.has_any_role(ROLE_ADMIN):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only owner can submit for review.")
    else:
        if not user.has_any_role(ROLE_TEAM_LEAD, ROLE_ADMIN):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only Team Lead or Admin can perform review transitions.",
            )
        # Prevent self-approval / self-publication
        if doc.owner_user_id == user.id and target_status in {STATUS_APPROVED, STATUS_PUBLISHED}:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Users cannot approve or publish their own submissions.",
            )
        if target_status in {STATUS_REJECTED, STATUS_CHANGES_REQUESTED, STATUS_ARCHIVED} and not comments.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Comments/reason are mandatory when setting status to {target_status}.",
            )

    prev_status = doc.status
    doc.status = target_status
    latest_ver.status = target_status
    if target_status == STATUS_PUBLISHED:
        latest_ver.is_immutable = True
    if target_status == STATUS_ARCHIVED:
        doc.archive_reason = comments.strip()[:500]
        doc.archived_by_user_id = user.id
        doc.archived_at = utcnow()

    db.add(
        DocumentApproval(
            document_id=doc.id,
            version_id=latest_ver.id,
            reviewer_user_id=user.id,
            action=target_status,
            from_status=prev_status,
            to_status=target_status,
            comments=comments.strip()[:2000] or None,
        )
    )
    log_audit(
        db,
        user.id,
        f"GOV_STATUS_{target_status}",
        "document",
        doc.doc_key,
        f"{prev_status}->{target_status}",
    )
    db.commit()
    db.refresh(doc)
    return doc


def record_access_event(
    db: Session,
    doc: GovernedDocument,
    version_id: int | None,
    user_id: int,
    event_type: str,
) -> None:
    db.add(
        DocumentAccessEvent(
            document_id=doc.id,
            version_id=version_id,
            user_id=user_id,
            event_type=event_type,
        )
    )
    if event_type == "VIEW":
        doc.view_count += 1
    elif event_type == "DOWNLOAD":
        doc.download_count += 1
    db.commit()


def get_governance_analytics(db: Session, user: AuthenticatedUser) -> dict[str, Any]:
    is_privileged = user.has_any_role(ROLE_TEAM_LEAD, ROLE_ADMIN)
    base_filter = True if is_privileged else or_(
        GovernedDocument.owner_user_id == user.id,
        GovernedDocument.status == STATUS_PUBLISHED,
    )

    total_docs = db.scalar(select(func.count(GovernedDocument.id)).where(base_filter)) or 0
    published_docs = (
        db.scalar(
            select(func.count(GovernedDocument.id)).where(
                base_filter, GovernedDocument.status == STATUS_PUBLISHED
            )
        )
        or 0
    )
    pending_approvals = (
        db.scalar(
            select(func.count(GovernedDocument.id)).where(
                base_filter,
                GovernedDocument.status.in_([STATUS_SUBMITTED, STATUS_UNDER_REVIEW]),
            )
        )
        or 0
    )
    total_views = db.scalar(select(func.coalesce(func.sum(GovernedDocument.view_count), 0)).where(base_filter)) or 0
    total_downloads = (
        db.scalar(select(func.coalesce(func.sum(GovernedDocument.download_count), 0)).where(base_filter)) or 0
    )

    soon = utcnow() + timedelta(days=30)
    approaching_review = (
        db.scalar(
            select(func.count(GovernedDocument.id)).where(
                base_filter,
                GovernedDocument.review_date.is_not(None),
                GovernedDocument.review_date <= soon,
                GovernedDocument.status == STATUS_PUBLISHED,
            )
        )
        or 0
    )

    approved_count = 0
    rejected_count = 0
    if is_privileged:
        approved_count = (
            db.scalar(select(func.count(DocumentApproval.id)).where(DocumentApproval.action == STATUS_APPROVED))
            or 0
        )
        rejected_count = (
            db.scalar(select(func.count(DocumentApproval.id)).where(DocumentApproval.action == STATUS_REJECTED))
            or 0
        )

    return {
        "scope": "team" if is_privileged else "personal_and_published",
        "total_documents": int(total_docs),
        "published_documents": int(published_docs),
        "pending_approvals": int(pending_approvals),
        "total_views": int(total_views),
        "total_downloads": int(total_downloads),
        "approaching_review": int(approaching_review),
        "approved_count": int(approved_count),
        "rejected_count": int(rejected_count),
    }
