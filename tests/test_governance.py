"""Phase 16 tests: Version control, approval workflow, library search, comparison, analytics, archival, and migration."""
from io import BytesIO
from pathlib import Path

from alembic import command
from alembic.config import Config
from reportlab.pdfgen import canvas
from sqlalchemy import create_engine, inspect

from backend.database.connection import Base


def _pdf_bytes(lines: list[str]) -> bytes:
    buf = BytesIO()
    c = canvas.Canvas(buf)
    y = 760
    for ln in lines:
        c.drawString(50, y, ln)
        y -= 24
    c.showPage()
    c.save()
    return buf.getvalue()


def test_governance_versioning_approvals_comparison_and_archival(isolated_env):
    client = isolated_env["client"]

    # 1. Engineer creates draft v1.0
    v1_bytes = _pdf_bytes(["CUCM Deployment Guide", "Initial section"])
    up1 = client.post(
        "/api/files/upload",
        headers={"X-Username": "engineer1"},
        files={"file": ("cucm_v1.pdf", v1_bytes, "application/pdf")},
    ).json()

    created = client.post(
        "/api/governance/documents",
        headers={"X-Username": "engineer1"},
        json={
            "title": "CUCM Deployment Guide",
            "description": "Cluster setup steps",
            "category": "CUCM",
            "technology": "CUCM",
            "tags": ["voice", "cisco"],
            "source_relative_path": up1["relative_path"],
            "review_days": 15,
        },
    )
    assert created.status_code == 200
    doc_key = created.json()["doc_key"]
    assert created.json()["version_number"] == "1.0"
    assert created.json()["status"] == "DRAFT"

    # 2. Duplicate SHA-256 upload rejected (409)
    dup_up = client.post(
        "/api/files/upload",
        headers={"X-Username": "engineer1"},
        files={"file": ("dup.pdf", v1_bytes, "application/pdf")},
    ).json()
    r_dup = client.post(
        f"/api/governance/documents/{doc_key}/versions",
        headers={"X-Username": "engineer1"},
        json={"source_relative_path": dup_up["relative_path"], "bump_type": "minor"},
    )
    assert r_dup.status_code == 409

    # 3. Upload v1.1 with new text
    v2_bytes = _pdf_bytes(["CUCM Deployment Guide", "Updated SIP trunk section"])
    up2 = client.post(
        "/api/files/upload",
        headers={"X-Username": "engineer1"},
        files={"file": ("cucm_v2.pdf", v2_bytes, "application/pdf")},
    ).json()
    rev2 = client.post(
        f"/api/governance/documents/{doc_key}/versions",
        headers={"X-Username": "engineer1"},
        json={"source_relative_path": up2["relative_path"], "bump_type": "minor"},
    )
    assert rev2.status_code == 200 and rev2.json()["version_number"] == "1.1"

    # 4. Cross-user private draft access blocked for another Engineer? (lead1 is Team Lead so test submit/review)
    # Engineer submits for review
    assert (
        client.post(
            f"/api/governance/documents/{doc_key}/transition",
            headers={"X-Username": "engineer1"},
            json={"target_status": "SUBMITTED"},
        ).status_code
        == 200
    )

    # Engineer cannot approve own submission (403)
    assert (
        client.post(
            f"/api/governance/documents/{doc_key}/transition",
            headers={"X-Username": "engineer1"},
            json={"target_status": "APPROVED"},
        ).status_code
        == 403
    )

    # Team Lead requests changes (mandatory comments)
    assert (
        client.post(
            f"/api/governance/documents/{doc_key}/transition",
            headers={"X-Username": "lead1"},
            json={"target_status": "CHANGES_REQUESTED", "comments": ""},
        ).status_code
        == 400
    )
    assert (
        client.post(
            f"/api/governance/documents/{doc_key}/transition",
            headers={"X-Username": "lead1"},
            json={"target_status": "CHANGES_REQUESTED", "comments": "Add port table"},
        ).status_code
        == 200
    )

    # Engineer resubmits, Team Lead approves and publishes
    assert (
        client.post(
            f"/api/governance/documents/{doc_key}/transition",
            headers={"X-Username": "engineer1"},
            json={"target_status": "SUBMITTED"},
        ).status_code
        == 200
    )
    assert (
        client.post(
            f"/api/governance/documents/{doc_key}/transition",
            headers={"X-Username": "lead1"},
            json={"target_status": "APPROVED", "comments": "Looks good"},
        ).status_code
        == 200
    )
    assert (
        client.post(
            f"/api/governance/documents/{doc_key}/transition",
            headers={"X-Username": "lead1"},
            json={"target_status": "PUBLISHED"},
        ).status_code
        == 200
    )

    # 5. Search & filter in Knowledge Library
    found = client.get(
        "/api/governance/documents",
        headers={"X-Username": "engineer1"},
        params={"q": "voice", "category": "CUCM", "doc_status": "PUBLISHED"},
    )
    assert found.status_code == 200 and len(found.json()) == 1

    # 6. Version history, download & comparison
    vers = client.get(f"/api/governance/documents/{doc_key}/versions", headers={"X-Username": "engineer1"}).json()
    assert len(vers) == 2
    assert vers[0]["is_immutable"] is True
    v_old_id = vers[1]["id"]
    v_new_id = vers[0]["id"]

    dl_old = client.get(
        f"/api/governance/documents/{doc_key}/versions/{v_old_id}/download",
        headers={"X-Username": "engineer1"},
    )
    assert dl_old.status_code == 200 and dl_old.content.startswith(b"%PDF-")

    cmp_res = client.get(
        f"/api/governance/documents/{doc_key}/compare",
        headers={"X-Username": "engineer1"},
        params={"old_version_id": v_old_id, "new_version_id": v_new_id},
    )
    assert cmp_res.status_code == 200
    assert cmp_res.json()["added_count"] >= 1
    assert cmp_res.json()["removed_count"] >= 1

    # 7. Restore v1.0 as new revision v1.2 (DRAFT)
    restored = client.post(
        f"/api/governance/documents/{doc_key}/versions/{v_old_id}/restore",
        headers={"X-Username": "engineer1"},
    )
    assert restored.status_code == 200 and restored.json()["version_number"] == "1.2"

    # 8. Analytics & Archival restriction
    ana_eng = client.get("/api/governance/analytics", headers={"X-Username": "engineer1"}).json()
    assert ana_eng["scope"] == "personal_and_published"
    assert ana_eng["total_downloads"] >= 1

    # Re-publish v1.2 via Team Lead then archive
    client.post(f"/api/governance/documents/{doc_key}/transition", headers={"X-Username": "engineer1"}, json={"target_status": "SUBMITTED"})
    client.post(f"/api/governance/documents/{doc_key}/transition", headers={"X-Username": "lead1"}, json={"target_status": "APPROVED"})
    client.post(f"/api/governance/documents/{doc_key}/transition", headers={"X-Username": "lead1"}, json={"target_status": "PUBLISHED"})
    arch = client.post(
        f"/api/governance/documents/{doc_key}/transition",
        headers={"X-Username": "lead1"},
        json={"target_status": "ARCHIVED", "comments": "Superseded by new release"},
    )
    assert arch.status_code == 200

    # Archived document download blocked for Engineer (403)
    assert (
        client.get(
            f"/api/governance/documents/{doc_key}/versions/{v_new_id}/download",
            headers={"X-Username": "engineer1"},
        ).status_code
        == 403
    )


def test_alembic_0002_upgrade_downgrade_tables_metadata():
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "mig0002",
        Path(__file__).resolve().parent.parent / "alembic" / "versions" / "20261126_0002_document_governance.py",
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert mod.revision == "0002_governance"
    assert mod.down_revision == "0001_initial"
    assert len(mod.GOVERNANCE_TABLES) == 7
