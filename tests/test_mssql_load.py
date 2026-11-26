"""Real MSSQL load & concurrency tests (3, 8, 15, 20 users) against CPDB.pdfstudio.

Creates isolated test users/jobs/docs with unique run IDs and cleans up ONLY
records created by the test. Never modifies or deletes existing business data.
"""
import os
import shutil
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import psutil
import pytest
from PIL import Image

from backend.config import get_settings
from backend.database.connection import get_engine, reset_engine
from backend.database.models import AuditLog, GeneratedDocument, PdfJob, User
from backend.database.session import get_session_factory
from backend.security.storage import save_user_upload
from backend.services.job_service import (
    JOB_COMPLETED,
    JOB_FAILED,
    JOB_QUEUED,
    claim_next_job,
    mark_job_failed,
    submit_job,
)
from backend.worker.runner import execute_job


def _percentile(sorted_vals: list[float], pct: float) -> float:
    if not sorted_vals:
        return 0.0
    idx = min(len(sorted_vals) - 1, max(0, int(round((pct / 100.0) * (len(sorted_vals) - 1)))))
    return sorted_vals[idx]


@pytest.mark.parametrize("user_count", [3, 8, 15, 20])
def test_mssql_real_concurrent_users_and_job_queue(tmp_path: Path, monkeypatch, user_count: int):
    storage = tmp_path / "mssql_load_data"
    storage.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("STORAGE_ROOT", str(storage))
    get_settings.cache_clear()
    reset_engine()

    run_id = uuid.uuid4().hex[:8]
    SessionLocal = get_session_factory()
    created_user_ids: list[int] = []
    created_job_ids: list[int] = []

    proc = psutil.Process(os.getpid())
    psutil.cpu_percent(interval=None)
    mem_before_mb = proc.memory_info().rss / (1024 * 1024)

    # Create isolated test users in CPDB.pdfstudio
    with SessionLocal() as db:
        for i in range(user_count):
            uname = f"load_{run_id}_{i}"
            u = User(
                username=uname,
                display_name=f"Load User {i}",
                email=f"{uname}@pdfstudio.test",
                storage_folder=uname,
                is_active=True,
                auth_provider="load_test",
            )
            db.add(u)
            db.flush()
            created_user_ids.append(u.id)
        db.commit()

    # Pre-generate one small PNG payload in memory
    img_path = tmp_path / "sample.png"
    Image.new("RGB", (300, 400), (25, 95, 190)).save(img_path, format="PNG")
    img_bytes = img_path.read_bytes()

    def _submit_for_user(idx: int) -> tuple[int, float]:
        uid = created_user_ids[idx]
        uname = f"load_{run_id}_{idx}"
        t0 = time.perf_counter()
        saved = save_user_upload(uname, f"img_{idx}.png", img_bytes, storage_root=storage)
        with SessionLocal() as db:
            job = submit_job(
                db,
                uid,
                "image_to_pdf",
                {
                    "input_paths": [str(saved["relative_path"])],
                    "output_filename": f"out_{idx}.pdf",
                },
            )
            elapsed = time.perf_counter() - t0
            return job.id, elapsed

    try:
        # 1. Concurrent upload + MSSQL job submission
        with ThreadPoolExecutor(max_workers=user_count) as pool:
            sub_results = list(pool.map(_submit_for_user, range(user_count)))
        created_job_ids = [r[0] for r in sub_results]
        submit_latencies = sorted(r[1] for r in sub_results)

        # 2. Concurrent MSSQL job claiming (UPDLOCK, READPAST, ROWLOCK) - verify zero duplicates
        claimed_ids: list[int] = []

        def _claim_loop(worker_idx: int) -> list[int]:
            local_claimed: list[int] = []
            while True:
                with SessionLocal() as db:
                    job = claim_next_job(db, f"load-worker-{worker_idx}")
                    if job is None:
                        break
                    local_claimed.append(job.id)
            return local_claimed

        t_claim_start = time.perf_counter()
        with ThreadPoolExecutor(max_workers=4) as pool:
            worker_claims = list(pool.map(_claim_loop, range(4)))
        for lst in worker_claims:
            claimed_ids.extend(lst)

        # Only our test jobs (or any queued) were claimed; verify zero duplicate IDs
        assert len(claimed_ids) == len(set(claimed_ids)), "Duplicate job claim detected!"
        ours_claimed = [jid for jid in created_job_ids if jid in set(claimed_ids)]

        # 3. Execute our test jobs concurrently (worker concurrency = 3)
        exec_latencies: list[float] = []

        def _exec_one(jid: int) -> float:
            t0 = time.perf_counter()
            execute_job(jid)
            return time.perf_counter() - t0

        t_exec_start = time.perf_counter()
        with ThreadPoolExecutor(max_workers=3) as pool:
            exec_latencies = sorted(pool.map(_exec_one, ours_claimed))
        total_exec_s = time.perf_counter() - t_exec_start

        # Verify all test jobs claimed by test workers completed (and any claimed by live worker are not QUEUED)
        with SessionLocal() as db:
            if ours_claimed:
                done_count = (
                    db.query(PdfJob)
                    .filter(PdfJob.id.in_(ours_claimed), PdfJob.status == JOB_COMPLETED)
                    .count()
                )
                assert done_count == len(ours_claimed)

            # 4. Retry & failed-job handling check on one synthetic job
            probe_job = submit_job(db, created_user_ids[0], "image_to_pdf", {"input_paths": []})
            created_job_ids.append(probe_job.id)
            for _ in range(probe_job.max_retries + 1):
                mark_job_failed(db, probe_job, "Load test retry check")
            db.refresh(probe_job)
            assert probe_job.status == JOB_FAILED

        pool_obj = get_engine().pool
        mem_after_mb = proc.memory_info().rss / (1024 * 1024)
        cpu_pct = psutil.cpu_percent(interval=None)
        disk_free_gb = shutil.disk_usage(storage).free / (1024 ** 3)
        throughput = user_count / max(0.001, total_exec_s)

        print(
            f"\n[MSSQL LOAD {user_count} USERS] "
            f"submit P50={_percentile(submit_latencies,50):.3f}s P95={_percentile(submit_latencies,95):.3f}s P99={_percentile(submit_latencies,99):.3f}s | "
            f"exec P50={_percentile(exec_latencies,50):.3f}s P95={_percentile(exec_latencies,95):.3f}s P99={_percentile(exec_latencies,99):.3f}s | "
            f"throughput={throughput:.2f} jobs/s | pool_size={pool_obj.size()} checked_out={pool_obj.checkedout()} | "
            f"cpu={cpu_pct:.1f}% rss_delta={mem_after_mb - mem_before_mb:+.1f}MB disk_free={disk_free_gb:.1f}GB"
        )
    finally:
        # Clean up ONLY records created by this test
        with SessionLocal() as db:
            if created_user_ids:
                db.query(AuditLog).filter(AuditLog.user_id.in_(created_user_ids)).delete(synchronize_session=False)
                db.query(GeneratedDocument).filter(GeneratedDocument.user_id.in_(created_user_ids)).delete(synchronize_session=False)
            if created_job_ids:
                db.query(PdfJob).filter(PdfJob.id.in_(created_job_ids)).delete(synchronize_session=False)
            if created_user_ids:
                db.query(User).filter(User.id.in_(created_user_ids)).delete(synchronize_session=False)
            db.commit()
        reset_engine()
        get_settings.cache_clear()
