"""End-to-end validation for Dashboard modules, Personal/Shared storage, and Background job queue."""
import os
import time
from io import BytesIO
from pathlib import Path
from PIL import Image

from backend.config import get_settings
from backend.database.models import PdfJob, User
from backend.security.storage import cleanup_temp_files
from backend.services.job_service import (
    JOB_COMPLETED,
    JOB_FAILED,
    JOB_PROCESSING,
    JOB_QUEUED,
    claim_next_job,
    mark_job_failed,
    submit_job,
)


def test_all_ten_streamlit_modules_present_and_valid():
    app_dir = Path(__file__).resolve().parent.parent / "frontend"
    expected_pages = [
        "dashboard.py",
        "image_to_pdf.py",
        "document_to_pdf.py",
        "pdf_compiler.py",
        "learning_book_creator.py",
        "pdf_manager.py",
        "shared_library.py",
        "processing_history.py",
        "user_management.py",
        "settings.py",
    ]
    entrypoint_src = (app_dir / "streamlit_app.py").read_text(encoding="utf-8")
    for page_file in expected_pages:
        full_path = app_dir / "app_pages" / page_file
        assert full_path.is_file(), f"Missing Streamlit page: {full_path}"
        assert page_file in entrypoint_src, f"Page {page_file} not wired in streamlit_app.py"
        compile(full_path.read_text(encoding="utf-8"), str(full_path), "exec")


def test_personal_and_shared_storage_isolation(isolated_env):
    client = isolated_env["client"]

    # User A (engineer1) uploads and generates a private PDF
    buf = BytesIO()
    Image.new("RGB", (240, 320), (15, 75, 160)).save(buf, format="PNG")
    up_a = client.post(
        "/api/files/upload",
        headers={"X-Username": "engineer1"},
        files={"file": ("private_a.png", buf.getvalue(), "image/png")},
    )
    assert up_a.status_code == 200
    gen_a = client.post(
        "/api/pdf/image-to-pdf",
        headers={"X-Username": "engineer1"},
        json={"input_paths": [up_a.json()["relative_path"]], "output_filename": "private_a.pdf"},
    )
    assert gen_a.status_code == 200
    doc_a_uuid = gen_a.json()["doc_uuid"]

    # User A can download their own private PDF
    dl_a = client.get(f"/api/files/documents/{doc_a_uuid}/download", headers={"X-Username": "engineer1"})
    assert dl_a.status_code == 200
    assert dl_a.content.startswith(b"%PDF-")

    # User B (lead1) CANNOT access User A's private PDF
    dl_b = client.get(f"/api/files/documents/{doc_a_uuid}/download", headers={"X-Username": "lead1"})
    assert dl_b.status_code == 403

    # Unauthorized user (engineer1) CANNOT publish to shared folders
    pub_unauth = client.post(
        "/api/shared/publish",
        headers={"X-Username": "engineer1"},
        json={"doc_uuid": doc_a_uuid, "category": "technical_documents", "title": "Unauthorized"},
    )
    assert pub_unauth.status_code == 403

    # Authorized user (lead1) creates and publishes a document to shared storage
    up_b = client.post(
        "/api/files/upload",
        headers={"X-Username": "lead1"},
        files={"file": ("team_b.png", buf.getvalue(), "image/png")},
    )
    gen_b = client.post(
        "/api/pdf/image-to-pdf",
        headers={"X-Username": "lead1"},
        json={"input_paths": [up_b.json()["relative_path"]], "output_filename": "team_b.pdf"},
    )
    doc_b_uuid = gen_b.json()["doc_uuid"]

    pub_auth = client.post(
        "/api/shared/publish",
        headers={"X-Username": "lead1"},
        json={"doc_uuid": doc_b_uuid, "category": "technical_documents", "title": "Approved Guide"},
    )
    assert pub_auth.status_code == 200
    shared_id = pub_auth.json()["id"]

    # Both Engineer and Team Lead can read & download approved shared docs
    dl_shared = client.get(f"/api/shared/{shared_id}/download", headers={"X-Username": "engineer1"})
    assert dl_shared.status_code == 200
    assert dl_shared.content.startswith(b"%PDF-")


def test_background_job_queue_lifecycle_and_temp_cleanup(isolated_env):
    SessionLocal = isolated_env["session_factory"]
    storage = isolated_env["storage"]

    with SessionLocal() as db:
        user = db.query(User).filter(User.username == "engineer1").first()
        assert user is not None

        # 1. Job creation -> QUEUED
        job = submit_job(db, user.id, "image_to_pdf", {"input_paths": [], "output_filename": "q.pdf"})
        assert job.status == JOB_QUEUED

        # 2. Worker claim -> PROCESSING, and duplicate claim returns None
        claimed = claim_next_job(db, "worker-1")
        assert claimed is not None
        assert claimed.id == job.id
        assert claimed.status == JOB_PROCESSING

        duplicate_claim = claim_next_job(db, "worker-2")
        assert duplicate_claim is None

        # 3. Failure & retry -> FAILED after max_retries
        for _ in range(claimed.max_retries + 1):
            mark_job_failed(db, claimed, "Simulated conversion error")
        db.refresh(claimed)
        assert claimed.status == JOB_FAILED
        assert "Simulated conversion error" in (claimed.error_message or "")

        # 4. Cleanup job record
        db.delete(claimed)
        db.commit()

    # 5. Temporary file cleanup
    temp_dir = storage / "temp"
    temp_dir.mkdir(parents=True, exist_ok=True)
    old_file = temp_dir / "old_temp.pdf"
    old_file.write_bytes(b"%PDF-1.4")
    stale_time = time.time() - (48 * 3600)
    os.utime(old_file, (stale_time, stale_time))

    fresh_file = temp_dir / "fresh_temp.pdf"
    fresh_file.write_bytes(b"%PDF-1.4")

    removed = cleanup_temp_files(max_age_hours=24, storage_root=storage)
    assert removed == 1
    assert not old_file.exists()
    assert fresh_file.exists()
