"""Structured Pilot UAT suite covering all 11 functional areas across Engineer, Team Lead, and Admin."""
from io import BytesIO
from PIL import Image


def _png_bytes(color=(30, 90, 180)) -> bytes:
    buf = BytesIO()
    Image.new("RGB", (320, 420), color).save(buf, format="PNG")
    return buf.getvalue()


def test_uat_roles_workflows_admin_and_monitoring(isolated_env):
    client = isolated_env["client"]

    # 1. Access & session handling
    assert client.get("/api/files/documents").status_code == 401
    assert client.get("/api/admin/users", headers={"X-Username": "engineer1"}).status_code == 403
    assert client.get("/api/admin/users", headers={"X-Username": "lead1"}).status_code == 403
    assert client.get("/api/admin/users", headers={"X-Username": "admin1"}).status_code == 200

    # 2. Image-to-PDF (Engineer)
    up_img = client.post(
        "/api/files/upload",
        headers={"X-Username": "engineer1"},
        files={"file": ("uat_sketch.png", _png_bytes(), "image/png")},
    )
    assert up_img.status_code == 200
    img_pdf = client.post(
        "/api/pdf/image-to-pdf",
        headers={"X-Username": "engineer1"},
        json={"input_paths": [up_img.json()["relative_path"]], "output_filename": "uat_img.pdf"},
    )
    assert img_pdf.status_code == 200
    assert img_pdf.json()["page_count"] == 1

    # 3. Document-to-PDF (TXT)
    up_txt = client.post(
        "/api/files/upload",
        headers={"X-Username": "engineer1"},
        files={"file": ("uat_notes.txt", b"Pilot UAT document text", "text/plain")},
    )
    assert up_txt.status_code == 200
    doc_pdf = client.post(
        "/api/pdf/document-to-pdf",
        headers={"X-Username": "engineer1"},
        json={"input_path": up_txt.json()["relative_path"], "output_filename": "uat_doc.pdf"},
    )
    assert doc_pdf.status_code == 200

    # 4. PDF Compiler (mixed image + text)
    compiled = client.post(
        "/api/pdf/compile",
        headers={"X-Username": "engineer1"},
        json={
            "items": [
                {"path": up_img.json()["relative_path"], "section_title": "Diagram"},
                {"path": up_txt.json()["relative_path"], "section_title": "Notes"},
            ],
            "output_filename": "uat_compiled.pdf",
        },
    )
    assert compiled.status_code == 200
    assert compiled.json()["page_count"] == 2

    # 5. Learning Book Creator
    book = client.post(
        "/api/pdf/learning-book",
        headers={"X-Username": "engineer1"},
        json={
            "title": "Pilot UAT Handbook",
            "subtitle": "Validation Run",
            "author": "Alex Rivera",
            "date_str": "2026-11-26",
            "template_name": "Corporate Technical Manual",
            "sections": [{"heading": "Chapter 1", "path": up_img.json()["relative_path"]}],
            "output_filename": "uat_book.pdf",
        },
    )
    assert book.status_code == 200
    assert book.json()["page_count"] >= 3

    # 6. PDF Manager (watermark)
    dl_book = client.get(
        f"/api/files/documents/{book.json()['doc_uuid']}/download",
        headers={"X-Username": "engineer1"},
    )
    assert dl_book.status_code == 200
    up_pdf = client.post(
        "/api/files/upload",
        headers={"X-Username": "engineer1"},
        files={"file": ("book_src.pdf", dl_book.content, "application/pdf")},
    )
    wm = client.post(
        "/api/pdf/manage",
        headers={"X-Username": "engineer1"},
        json={
            "operation": "watermark",
            "input_path": up_pdf.json()["relative_path"],
            "output_filename": "uat_watermarked.pdf",
            "params": {"text": "PILOT"},
        },
    )
    assert wm.status_code == 200

    # 7 & 8. Personal storage & Shared library (Team Lead publishes, Engineer reads)
    up_lead = client.post(
        "/api/files/upload",
        headers={"X-Username": "lead1"},
        files={"file": ("lead_sketch.png", _png_bytes((10, 120, 90)), "image/png")},
    )
    lead_pdf = client.post(
        "/api/pdf/image-to-pdf",
        headers={"X-Username": "lead1"},
        json={"input_paths": [up_lead.json()["relative_path"]], "output_filename": "lead_pub.pdf"},
    )
    pub = client.post(
        "/api/shared/publish",
        headers={"X-Username": "lead1"},
        json={
            "doc_uuid": lead_pdf.json()["doc_uuid"],
            "category": "learning_material",
            "title": "UAT Shared Guide",
        },
    )
    assert pub.status_code == 200
    shared_list = client.get("/api/shared", headers={"X-Username": "engineer1"})
    assert shared_list.status_code == 200
    assert any(d["title"] == "UAT Shared Guide" for d in shared_list.json())

    # 9. Processing History
    jobs = client.get("/api/jobs", headers={"X-Username": "engineer1"})
    assert jobs.status_code == 200
    assert len(jobs.json()) >= 5

    # 10 & 11. User Management, Audit Logs, Settings (Admin) & Operational Health
    new_user = client.post(
        "/api/admin/users",
        headers={"X-Username": "admin1"},
        json={
            "username": "uat_temp_user",
            "display_name": "UAT Temp",
            "email": "uat_temp@pdfstudio.local",
            "role_name": "Engineer",
        },
    )
    assert new_user.status_code == 200
    uid = new_user.json()["id"]
    assert (
        client.patch(
            f"/api/admin/users/{uid}/role",
            headers={"X-Username": "admin1"},
            json={"role_name": "Team Lead"},
        ).status_code
        == 200
    )
    assert (
        client.put(
            "/api/admin/settings",
            headers={"X-Username": "admin1"},
            json={"setting_key": "default_page_size", "setting_value": "A4"},
        ).status_code
        == 200
    )
    logs = client.get("/api/admin/audit-logs", headers={"X-Username": "admin1"})
    assert logs.status_code == 200 and len(logs.json()) >= 1

    ops = client.get("/health/operations")
    assert ops.status_code == 200
    assert "queued_jobs" in ops.json() and "disk_free_gb" in ops.json()
