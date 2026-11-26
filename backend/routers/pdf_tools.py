"""Direct synchronous PDF processing endpoints (and queued job wrappers)."""
import json
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.config import get_settings
from backend.database.models import GeneratedDocument, PdfJob
from backend.database.session import get_db
from backend.security.auth import AuthenticatedUser, get_current_user
from backend.security.storage import ensure_user_folders, resolve_safe_path, sanitize_filename
from backend.services.compiler_service import CompilerItem, compile_mixed_documents
from backend.services.document_pdf_service import convert_document_to_pdf
from backend.services.document_sequence_service import analyze_document_sequence
from backend.services.image_pdf_service import images_to_pdf
from backend.services.job_service import JOB_COMPLETED, log_audit, utcnow
from backend.services.learning_book_service import (
    LearningBookConfig,
    LearningSection,
    publish_learning_book,
    render_cover_preview_png,
)
from backend.services.pdf_optimization_service import optimize_pdf
from backend.services.pdf_manager_service import (
    add_bookmarks,
    add_header_footer,
    add_page_numbers,
    add_watermark,
    compress_pdf,
    extract_pages,
    merge_pdfs,
    rotate_pages,
    split_pdf,
    update_metadata,
)

router = APIRouter(prefix="/api/pdf", tags=["PDF Tools"])


def _record_sync_result(
    db: Session,
    user: AuthenticatedUser,
    job_type: str,
    payload: dict,
    title: str,
    output_path: Path,
    res: dict,
) -> dict:
    settings = get_settings()
    storage_root = settings.STORAGE_ROOT.resolve()
    rel_out = output_path.relative_to(storage_root).as_posix()

    job = PdfJob(
        job_uuid=uuid.uuid4().hex,
        user_id=user.id,
        job_type=job_type,
        status=JOB_COMPLETED,
        progress_pct=100,
        payload_json=json.dumps(payload),
        started_at=utcnow(),
        completed_at=utcnow(),
    )
    db.add(job)
    db.flush()

    doc = GeneratedDocument(
        doc_uuid=uuid.uuid4().hex,
        user_id=user.id,
        job_id=job.id,
        title=title[:255],
        filename=output_path.name,
        relative_path=rel_out,
        operation_type=job_type,
        page_count=int(res["page_count"]),
        file_size_bytes=int(res["file_size_bytes"]),
    )
    db.add(doc)
    db.flush()
    job.result_document_id = doc.id
    log_audit(db, user.id, "PDF_GENERATED", "generated_document", doc.doc_uuid, f"type={job_type}")
    db.commit()
    return {
        "doc_uuid": doc.doc_uuid,
        "job_uuid": job.job_uuid,
        "filename": doc.filename,
        "page_count": doc.page_count,
        "file_size_bytes": doc.file_size_bytes,
    }


def _user_output_path(user: AuthenticatedUser, requested_name: str, default_stem: str) -> Path:
    folders = ensure_user_folders(user.storage_folder)
    clean = sanitize_filename(requested_name or f"{default_stem}.pdf")
    if not clean.lower().endswith(".pdf"):
        clean += ".pdf"
    return (folders["output"] / f"{uuid.uuid4().hex[:8]}_{clean}").resolve()


def _resolve_user_input(user: AuthenticatedUser, relative_path: str) -> Path:
    settings = get_settings()
    expected_prefix = f"users/{user.storage_folder}/"
    if relative_path.startswith("users/") and not relative_path.startswith(expected_prefix):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: cannot access another user's files.",
        )
    user_root = (settings.STORAGE_ROOT / "users" / user.storage_folder).resolve()
    rel = relative_path.removeprefix(expected_prefix)
    resolved = resolve_safe_path(rel, user_root)
    if not resolved.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Input file not found.")
    return resolved


class ImageToPdfRequest(BaseModel):
    input_paths: list[str]
    page_size: str = "A4"
    orientation: str = "auto"
    margin_mm: float = 10.0
    output_filename: str = "images.pdf"


@router.post("/image-to-pdf")
def run_image_to_pdf(
    req: ImageToPdfRequest,
    user: AuthenticatedUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    inputs = [_resolve_user_input(user, p) for p in req.input_paths]
    out = _user_output_path(user, req.output_filename, "images")
    try:
        res = images_to_pdf(inputs, out, req.page_size, req.orientation, req.margin_mm)
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    return _record_sync_result(db, user, "image_to_pdf", req.model_dump(), out.stem, out, res)


class DocumentToPdfRequest(BaseModel):
    input_path: str
    output_filename: str = "document.pdf"


@router.post("/document-to-pdf")
def run_document_to_pdf(
    req: DocumentToPdfRequest,
    user: AuthenticatedUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    inp = _resolve_user_input(user, req.input_path)
    out = _user_output_path(user, req.output_filename, inp.stem)
    try:
        res = convert_document_to_pdf(inp, out)
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    return _record_sync_result(db, user, "document_to_pdf", req.model_dump(), out.stem, out, res)


class AnalyzeSequenceRequest(BaseModel):
    input_paths: list[str]
    sort_mode: str = "Automatic Detection"


@router.post("/analyze-sequence")
def run_analyze_sequence(
    req: AnalyzeSequenceRequest,
    user: AuthenticatedUser = Depends(get_current_user),
) -> dict:
    entries = [(_resolve_user_input(user, p), p) for p in req.input_paths]
    try:
        return analyze_document_sequence(entries, sort_mode=req.sort_mode)
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


class CompileItemModel(BaseModel):
    path: str
    section_title: str = ""


class CompilePdfRequest(BaseModel):
    items: list[CompileItemModel]
    page_size: str = "A4"
    orientation: str = "auto"
    margin_mm: float = 10.0
    output_filename: str = "compiled.pdf"


@router.post("/compile")
def run_compile_pdf(
    req: CompilePdfRequest,
    user: AuthenticatedUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    items = [CompilerItem(_resolve_user_input(user, it.path), it.section_title) for it in req.items]
    out = _user_output_path(user, req.output_filename, "compiled")
    try:
        res = compile_mixed_documents(items, out, req.page_size, req.orientation, req.margin_mm)
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    return _record_sync_result(db, user, "compile_pdf", req.model_dump(), out.stem, out, res)


class LearningSectionModel(BaseModel):
    heading: str
    path: str
    chapter_number: str | None = None
    chapter_title: str | None = None
    subtitle: str = ""
    overview: str = ""
    level: int = 1


class LearningBookRequest(BaseModel):
    title: str
    subtitle: str = ""
    author: str = ""
    organization: str = ""
    date_str: str = ""
    version: str = "1.0"
    classification: str = ""
    template_name: str = "Corporate Technical Manual"
    page_orientation: str = "portrait"
    logo_path: str | None = None
    include_toc: bool = True
    toc_title: str = "Table of Contents"
    include_dividers: bool = False
    divider_style: str = "Classic Banner"
    count_dividers_in_numbering: bool = True
    header_text: str = ""
    footer_text: str = ""
    page_number_style: str = "Page 1 of N"
    roman_preliminary: bool = True
    hf_alignment: str = "right"
    skip_first_chapter_hf: bool = False
    meta_subject: str = ""
    meta_keywords: str = ""
    compression_mode: str = "Original Quality"
    sections: list[LearningSectionModel]
    output_filename: str = "learning_book.pdf"


@router.post("/learning-book/preview-cover")
def preview_learning_book_cover(
    req: LearningBookRequest,
    user: AuthenticatedUser = Depends(get_current_user),
) -> Response:
    logo = _resolve_user_input(user, req.logo_path) if req.logo_path else None
    cfg = LearningBookConfig(
        title=req.title,
        subtitle=req.subtitle,
        author=req.author or user.display_name,
        organization=req.organization,
        date_str=req.date_str,
        version=req.version,
        classification=req.classification,
        template_name=req.template_name,
        page_orientation=req.page_orientation,
        logo_path=logo,
    )
    png_bytes = render_cover_preview_png(cfg)
    return Response(content=png_bytes, media_type="image/png")


@router.post("/learning-book")
def run_learning_book(
    req: LearningBookRequest,
    user: AuthenticatedUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    sections = [
        LearningSection(
            heading=s.heading,
            file_path=_resolve_user_input(user, s.path),
            chapter_number=s.chapter_number,
            chapter_title=s.chapter_title,
            subtitle=s.subtitle,
            overview=s.overview,
            level=s.level,
        )
        for s in req.sections
    ]
    logo = _resolve_user_input(user, req.logo_path) if req.logo_path else None
    cfg = LearningBookConfig(
        title=req.title,
        subtitle=req.subtitle,
        author=req.author or user.display_name,
        organization=req.organization,
        date_str=req.date_str,
        version=req.version,
        classification=req.classification,
        template_name=req.template_name,
        page_orientation=req.page_orientation,
        logo_path=logo,
        include_toc=req.include_toc,
        toc_title=req.toc_title,
        include_dividers=req.include_dividers,
        divider_style=req.divider_style,
        count_dividers_in_numbering=req.count_dividers_in_numbering,
        header_text=req.header_text,
        footer_text=req.footer_text,
        page_number_style=req.page_number_style,
        roman_preliminary=req.roman_preliminary,
        hf_alignment=req.hf_alignment,
        skip_first_chapter_hf=req.skip_first_chapter_hf,
        meta_subject=req.meta_subject,
        meta_keywords=req.meta_keywords,
        compression_mode=req.compression_mode,
    )
    out = _user_output_path(user, req.output_filename, "learning_book")
    try:
        res = publish_learning_book(cfg, sections, out)
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    record = _record_sync_result(db, user, "learning_book", req.model_dump(), req.title, out, res)
    record.update(
        {
            "original_size_bytes": res.get("original_size_bytes"),
            "reduction_pct": res.get("reduction_pct"),
            "readability_warning": res.get("readability_warning"),
            "toc_entries": res.get("toc_entries"),
            "bookmarks_count": res.get("bookmarks_count"),
        }
    )
    return record


class OptimizePdfRequest(BaseModel):
    input_path: str
    mode: str = "Balanced"
    output_filename: str = "optimized.pdf"


@router.post("/optimize")
def run_optimize_pdf(
    req: OptimizePdfRequest,
    user: AuthenticatedUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    inp = _resolve_user_input(user, req.input_path)
    out = _user_output_path(user, req.output_filename, inp.stem)
    try:
        res = optimize_pdf(inp, out, mode=req.mode)
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    record = _record_sync_result(db, user, "pdf_optimize", req.model_dump(), out.stem, out, res)
    record.update(
        {
            "original_size_bytes": res["original_size_bytes"],
            "reduction_pct": res["reduction_pct"],
            "already_optimized": res["already_optimized"],
            "readability_warning": res["readability_warning"],
        }
    )
    return record


class PdfManagerRequest(BaseModel):
    operation: str
    input_path: str | None = None
    input_paths: list[str] | None = None
    output_filename: str = "managed.pdf"
    params: dict = {}


@router.post("/manage")
def run_pdf_manager(
    req: PdfManagerRequest,
    user: AuthenticatedUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    out = _user_output_path(user, req.output_filename, req.operation)
    op = req.operation
    p = req.params
    try:
        if op == "merge":
            paths = [_resolve_user_input(user, x) for x in (req.input_paths or [])]
            res = merge_pdfs(paths, out, add_bookmarks=bool(p.get("add_bookmarks", True)))
        else:
            if not req.input_path:
                raise ValueError("input_path is required.")
            inp = _resolve_user_input(user, req.input_path)
            if op == "split":
                res = split_pdf(inp, out, int(p["start_page"]), int(p["end_page"]))
            elif op == "extract":
                res = extract_pages(inp, out, [int(x) for x in p["pages"]])
            elif op == "rotate":
                pages = [int(x) for x in p["pages"]] if p.get("pages") else None
                res = rotate_pages(inp, out, int(p["angle"]), pages)
            elif op == "compress":
                res = compress_pdf(inp, out)
            elif op == "page_numbers":
                res = add_page_numbers(inp, out, p.get("position", "bottom-right"))
            elif op == "header_footer":
                res = add_header_footer(inp, out, p.get("header_text", ""), p.get("footer_text", ""))
            elif op == "watermark":
                res = add_watermark(inp, out, p["text"])
            elif op == "bookmarks":
                bms = [(b["title"], int(b["page"])) for b in p["bookmarks"]]
                res = add_bookmarks(inp, out, bms)
            elif op == "metadata":
                res = update_metadata(
                    inp,
                    out,
                    title=p.get("title", ""),
                    author=p.get("author", ""),
                    subject=p.get("subject", ""),
                    keywords=p.get("keywords", ""),
                )
            else:
                raise ValueError(f"Unsupported PDF operation: {op}")
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    return _record_sync_result(db, user, f"pdf_manager_{op}", req.model_dump(), out.stem, out, res)
