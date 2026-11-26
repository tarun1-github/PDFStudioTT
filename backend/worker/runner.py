"""Background worker polling the MSSQL job queue with controlled concurrency."""
import json
import signal
import socket
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from backend.config import get_settings
from backend.database.models import PdfJob, User
from backend.database.session import db_transaction
from backend.logging_config import configure_logging
from backend.security.storage import ensure_user_folders, resolve_safe_path, sanitize_filename
from backend.services.compiler_service import CompilerItem, compile_mixed_documents
from backend.services.document_pdf_service import convert_document_to_pdf
from backend.services.image_pdf_service import images_to_pdf
from backend.services.job_service import claim_next_job, mark_job_completed, mark_job_failed
from backend.services.learning_book_service import LearningSection, create_learning_book
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

logger = configure_logging()
_STOP = False


def _handle_signal(_signum, _frame) -> None:
    global _STOP
    _STOP = True


def execute_job(job_id: int) -> None:
    """Execute a single claimed job inside its own DB transaction."""
    settings = get_settings()
    storage_root = settings.STORAGE_ROOT.resolve()

    with db_transaction() as db:
        job = db.get(PdfJob, job_id)
        if job is None:
            return
        user = db.get(User, job.user_id)
        if user is None:
            mark_job_failed(db, job, "Owner user not found.")
            return

        payload = json.loads(job.payload_json)
        folders = ensure_user_folders(user.storage_folder, storage_root)
        user_root = folders["root"]
        out_name = sanitize_filename(payload.get("output_filename") or f"{job.job_type}_{job.job_uuid[:8]}.pdf")
        if not out_name.lower().endswith(".pdf"):
            out_name += ".pdf"
        output_path = (folders["output"] / f"{job.job_uuid[:8]}_{out_name}").resolve()

        try:
            job_type = job.job_type
            if job_type == "image_to_pdf":
                input_paths = [resolve_safe_path(p, storage_root) for p in payload["input_paths"]]
                res = images_to_pdf(
                    input_paths,
                    output_path,
                    page_size=payload.get("page_size", "A4"),
                    orientation=payload.get("orientation", "auto"),
                    margin_mm=float(payload.get("margin_mm", 10.0)),
                )
            elif job_type == "document_to_pdf":
                inp = resolve_safe_path(payload["input_path"], storage_root)
                res = convert_document_to_pdf(inp, output_path, timeout_seconds=settings.JOB_TIMEOUT_SECONDS)
            elif job_type == "compile_pdf":
                items = [
                    CompilerItem(
                        path=resolve_safe_path(it["path"], storage_root),
                        section_title=it.get("section_title", ""),
                    )
                    for it in payload["items"]
                ]
                res = compile_mixed_documents(
                    items,
                    output_path,
                    page_size=payload.get("page_size", "A4"),
                    orientation=payload.get("orientation", "auto"),
                    margin_mm=float(payload.get("margin_mm", 10.0)),
                )
            elif job_type == "learning_book":
                sections = [
                    LearningSection(
                        heading=s["heading"],
                        file_path=resolve_safe_path(s["path"], storage_root),
                    )
                    for s in payload["sections"]
                ]
                res = create_learning_book(
                    output_path=output_path,
                    title=payload["title"],
                    subtitle=payload.get("subtitle", ""),
                    author=payload.get("author", user.display_name),
                    date_str=payload.get("date_str", ""),
                    template_name=payload.get("template_name", "Corporate Technical Manual"),
                    sections=sections,
                )
            elif job_type == "pdf_manager":
                op = payload["operation"]
                if op == "merge":
                    paths = [resolve_safe_path(p, storage_root) for p in payload["input_paths"]]
                    res = merge_pdfs(paths, output_path, add_bookmarks=bool(payload.get("add_bookmarks", True)))
                else:
                    inp = resolve_safe_path(payload["input_path"], storage_root)
                    if op == "split":
                        res = split_pdf(inp, output_path, int(payload["start_page"]), int(payload["end_page"]))
                    elif op == "extract":
                        res = extract_pages(inp, output_path, [int(x) for x in payload["pages"]])
                    elif op == "rotate":
                        pages = [int(x) for x in payload["pages"]] if payload.get("pages") else None
                        res = rotate_pages(inp, output_path, int(payload["angle"]), pages)
                    elif op == "compress":
                        res = compress_pdf(inp, output_path)
                    elif op == "page_numbers":
                        res = add_page_numbers(inp, output_path, payload.get("position", "bottom-right"))
                    elif op == "header_footer":
                        res = add_header_footer(
                            inp, output_path, payload.get("header_text", ""), payload.get("footer_text", "")
                        )
                    elif op == "watermark":
                        res = add_watermark(inp, output_path, payload["text"])
                    elif op == "bookmarks":
                        bms = [(b["title"], int(b["page"])) for b in payload["bookmarks"]]
                        res = add_bookmarks(inp, output_path, bms)
                    elif op == "metadata":
                        res = update_metadata(
                            inp,
                            output_path,
                            title=payload.get("title", ""),
                            author=payload.get("author", ""),
                            subject=payload.get("subject", ""),
                            keywords=payload.get("keywords", ""),
                        )
                    else:
                        raise ValueError(f"Unknown PDF manager operation: {op}")
            else:
                raise ValueError(f"Unsupported job type: {job_type}")

            if not output_path.is_relative_to(user_root):
                raise RuntimeError("Output path escaped user root.")

            rel_out = output_path.relative_to(storage_root).as_posix()
            mark_job_completed(
                db=db,
                job=job,
                doc_title=payload.get("title") or out_name,
                filename=output_path.name,
                relative_path=rel_out,
                operation_type=job_type,
                page_count=int(res["page_count"]),
                file_size_bytes=int(res["file_size_bytes"]),
            )
            logger.info("Completed job %s (%s)", job.job_uuid, job.job_type)
        except Exception as exc:
            logger.exception("Job %s failed", job.job_uuid)
            mark_job_failed(db, job, str(exc))


def run_worker_loop(poll_interval: float = 2.0) -> None:
    """Poll MSSQL queue and process jobs with controlled concurrency."""
    settings = get_settings()
    worker_id = f"{socket.gethostname()}-worker"
    max_workers = max(1, min(settings.MAX_CONCURRENT_JOBS, 4))
    logger.info("Starting PDF Studio worker '%s' (max_workers=%d)", worker_id, max_workers)

    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)

    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        while not _STOP:
            claimed_id: int | None = None
            try:
                with db_transaction() as db:
                    job = claim_next_job(db, worker_id)
                    if job is not None:
                        claimed_id = job.id
            except Exception as exc:
                logger.error("Worker polling error: %s", exc)
                time.sleep(poll_interval)
                continue

            if claimed_id is not None:
                pool.submit(execute_job, claimed_id)
            else:
                time.sleep(poll_interval)


if __name__ == "__main__":
    run_worker_loop()
