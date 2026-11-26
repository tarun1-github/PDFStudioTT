"""Safe multi-user pilot load tests (3, 8, 15, and 20 concurrent users) against isolated test data."""
import os
import time
from concurrent.futures import ThreadPoolExecutor
from io import BytesIO

import psutil
import pytest
from PIL import Image


@pytest.mark.parametrize("user_count", [3, 8, 15, 20])
def test_pilot_concurrent_users_tiers(isolated_env, user_count: int):
    client = isolated_env["client"]
    user_cycle = ["engineer1", "lead1", "admin1"]
    proc = psutil.Process(os.getpid())
    mem_before_mb = proc.memory_info().rss / (1024 * 1024)

    def _simulate_user(idx: int) -> tuple[int, float, float]:
        username = user_cycle[idx % len(user_cycle)]
        buf = BytesIO()
        Image.new("RGB", (360, 480), ((idx * 17) % 255, 90, 170)).save(buf, format="PNG")

        t0 = time.perf_counter()
        up = client.post(
            "/api/files/upload",
            headers={"X-Username": username},
            files={"file": (f"tier{user_count}_u{idx}.png", buf.getvalue(), "image/png")},
        )
        t_upload = time.perf_counter() - t0
        if up.status_code != 200:
            return up.status_code, t_upload, 0.0

        t1 = time.perf_counter()
        gen = client.post(
            "/api/pdf/image-to-pdf",
            headers={"X-Username": username},
            json={
                "input_paths": [up.json()["relative_path"]],
                "output_filename": f"tier{user_count}_out_{idx}.pdf",
            },
        )
        t_gen = time.perf_counter() - t1
        return gen.status_code, t_upload, t_gen

    t_start = time.perf_counter()
    with ThreadPoolExecutor(max_workers=user_count) as pool:
        results = list(pool.map(_simulate_user, range(user_count)))
    total_elapsed = time.perf_counter() - t_start
    mem_after_mb = proc.memory_info().rss / (1024 * 1024)

    statuses = [r[0] for r in results]
    upload_times = [r[1] for r in results]
    gen_times = [r[2] for r in results]

    print(
        f"\n[LOAD TIER {user_count} USERS] total={total_elapsed:.2f}s | "
        f"avg_upload={sum(upload_times)/len(upload_times):.3f}s | "
        f"avg_pdf_gen={sum(gen_times)/len(gen_times):.3f}s | "
        f"rss_delta={mem_after_mb - mem_before_mb:+.1f}MB"
    )
    assert all(s == 200 for s in statuses), f"Failures in {user_count}-user tier: {statuses}"
    assert total_elapsed < 30.0
