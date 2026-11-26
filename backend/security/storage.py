"""Secure file storage management with path-traversal and user-isolation controls."""
import hashlib
import re
import time
import uuid
from pathlib import Path

from fastapi import HTTPException, status

from backend.config import get_settings

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".bmp", ".tiff", ".tif", ".webp"}
DOCUMENT_EXTENSIONS = {".docx", ".txt", ".md", ".html", ".htm", ".xlsx", ".pptx"}
PDF_EXTENSIONS = {".pdf"}
ALL_ALLOWED_EXTENSIONS = IMAGE_EXTENSIONS | DOCUMENT_EXTENSIONS | PDF_EXTENSIONS

SHARED_CATEGORIES = (
    "learning_material",
    "technical_documents",
    "sketchnotes",
    "published_pdfs",
)

_FILENAME_SAFE_RE = re.compile(r"[^A-Za-z0-9._-]+")


def ensure_storage_layout(storage_root: Path | None = None) -> Path:
    """Create the required data directory hierarchy."""
    root = (storage_root or get_settings().STORAGE_ROOT).resolve()
    (root / "users").mkdir(parents=True, exist_ok=True)
    for cat in SHARED_CATEGORIES:
        (root / "shared" / cat).mkdir(parents=True, exist_ok=True)
    (root / "temp").mkdir(parents=True, exist_ok=True)
    (root / "templates").mkdir(parents=True, exist_ok=True)
    return root


def ensure_user_folders(storage_folder: str, storage_root: Path | None = None) -> dict[str, Path]:
    """Ensure personal uploads/processing/output directories exist for a user."""
    root = ensure_storage_layout(storage_root)
    safe_folder = sanitize_folder_name(storage_folder)
    user_root = (root / "users" / safe_folder).resolve()
    if not user_root.is_relative_to(root / "users"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid user folder.")

    folders = {
        "root": user_root,
        "uploads": user_root / "uploads",
        "processing": user_root / "processing",
        "output": user_root / "output",
    }
    for p in folders.values():
        p.mkdir(parents=True, exist_ok=True)
    return folders


def sanitize_folder_name(name: str) -> str:
    cleaned = _FILENAME_SAFE_RE.sub("_", name.strip())
    if not cleaned or cleaned in {".", ".."}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid folder name.")
    return cleaned


def sanitize_filename(filename: str) -> str:
    """Strip directory components and unsafe characters from user-provided filenames."""
    base = Path(filename).name.strip()
    cleaned = _FILENAME_SAFE_RE.sub("_", base).lstrip(".")
    if not cleaned:
        cleaned = f"file_{uuid.uuid4().hex[:8]}"
    return cleaned[:180]


def validate_extension(filename: str, allowed_extensions: set[str] | None = None) -> str:
    ext = Path(filename).suffix.lower()
    allowed = allowed_extensions or ALL_ALLOWED_EXTENSIONS
    if ext not in allowed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file extension '{ext or '(none)'}'.",
        )
    return ext


def resolve_safe_path(relative_path: str, allowed_root: Path) -> Path:
    """Resolve a relative storage path and block path traversal."""
    if not relative_path or Path(relative_path).is_absolute() or ".." in Path(relative_path).parts:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid file path.",
        )
    root_resolved = allowed_root.resolve()
    target = (root_resolved / relative_path).resolve()
    if not target.is_relative_to(root_resolved):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: path outside permitted root.",
        )
    return target


def validate_file_content(content: bytes, ext: str) -> None:
    """Basic header/signature validation to reject corrupt or spoofed files."""
    if not content:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Empty file uploaded.")
    if ext == ".pdf" and not content.lstrip().startswith(b"%PDF-"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Corrupt or invalid PDF header.")
    if ext in {".docx", ".xlsx", ".pptx"} and not content.startswith(b"PK"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Corrupt or invalid {ext} archive.",
        )


def save_user_upload(
    storage_folder: str,
    original_filename: str,
    content: bytes,
    allowed_extensions: set[str] | None = None,
    storage_root: Path | None = None,
) -> dict[str, str | int]:
    """Validate and save an uploaded file into the user's isolated uploads directory."""
    settings = get_settings()
    if len(content) > settings.max_upload_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File exceeds MAX_UPLOAD_MB ({settings.MAX_UPLOAD_MB} MB).",
        )

    safe_name = sanitize_filename(original_filename)
    ext = validate_extension(safe_name, allowed_extensions)
    validate_file_content(content, ext)

    folders = ensure_user_folders(storage_folder, storage_root)
    root = (storage_root or settings.STORAGE_ROOT).resolve()

    file_uuid = uuid.uuid4().hex
    stored_filename = f"{file_uuid}_{safe_name}"
    dest = (folders["uploads"] / stored_filename).resolve()
    dest.write_bytes(content)

    sha256 = hashlib.sha256(content).hexdigest()
    rel_path = dest.relative_to(root).as_posix()
    return {
        "file_uuid": file_uuid,
        "original_filename": safe_name,
        "stored_filename": stored_filename,
        "relative_path": rel_path,
        "file_ext": ext,
        "file_size_bytes": len(content),
        "sha256_hash": sha256,
        "absolute_path": str(dest),
    }


def cleanup_temp_files(max_age_hours: int = 24, storage_root: Path | None = None) -> int:
    """Remove temporary files older than max_age_hours."""
    root = ensure_storage_layout(storage_root)
    temp_dir = root / "temp"
    cutoff = time.time() - (max_age_hours * 3600)
    removed = 0
    for item in temp_dir.rglob("*"):
        if item.is_file() and item.stat().st_mtime < cutoff:
            item.unlink(missing_ok=True)
            removed += 1
    return removed
