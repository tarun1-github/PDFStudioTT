"""Security tests: RBAC, cross-user isolation, path traversal, corrupt/oversized/invalid uploads."""
from io import BytesIO
from pathlib import Path
from PIL import Image

from backend.security.storage import resolve_safe_path


def test_security_upload_and_isolation(isolated_env):
    client = isolated_env["client"]

    # Invalid extension
    r_bad_ext = client.post(
        "/api/files/upload",
        headers={"X-Username": "engineer1"},
        files={"file": ("malware.exe", b"MZ123", "application/octet-stream")},
    )
    assert r_bad_ext.status_code == 400

    # Corrupt PDF header
    r_corrupt = client.post(
        "/api/files/upload",
        headers={"X-Username": "engineer1"},
        files={"file": ("fake.pdf", b"NOT_A_PDF", "application/pdf")},
    )
    assert r_corrupt.status_code == 400

    # Oversized upload (> 5 MB test limit)
    big_bytes = b"%PDF-1.4\n" + (b"0" * (6 * 1024 * 1024))
    r_big = client.post(
        "/api/files/upload",
        headers={"X-Username": "engineer1"},
        files={"file": ("big.pdf", big_bytes, "application/pdf")},
    )
    assert r_big.status_code == 413

    # Upload valid PNG as engineer1 and generate PDF
    buf = BytesIO()
    Image.new("RGB", (200, 200), (10, 20, 30)).save(buf, format="PNG")
    r_up = client.post(
        "/api/files/upload",
        headers={"X-Username": "engineer1"},
        files={"file": ("valid.png", buf.getvalue(), "image/png")},
    )
    assert r_up.status_code == 200
    rel_path = r_up.json()["relative_path"]

    r_gen = client.post(
        "/api/pdf/image-to-pdf",
        headers={"X-Username": "engineer1"},
        json={"input_paths": [rel_path], "output_filename": "secret.pdf"},
    )
    assert r_gen.status_code == 200
    doc_uuid = r_gen.json()["doc_uuid"]

    # Cross-user download blocked for lead1 (not owner, not Admin)
    r_cross = client.get(
        f"/api/files/documents/{doc_uuid}/download",
        headers={"X-Username": "lead1"},
    )
    assert r_cross.status_code == 403

    # Engineer cannot publish to shared library (403)
    r_pub = client.post(
        "/api/shared/publish",
        headers={"X-Username": "engineer1"},
        json={"doc_uuid": doc_uuid, "category": "published_pdfs", "title": "Attempt"},
    )
    assert r_pub.status_code == 403


def test_path_traversal_blocked(tmp_path: Path):
    import pytest
    from fastapi import HTTPException

    root = tmp_path / "safe"
    root.mkdir()
    with pytest.raises(HTTPException) as exc:
        resolve_safe_path("../../Windows/System32/drivers/etc/hosts", root)
    assert exc.value.status_code in (400, 403)
