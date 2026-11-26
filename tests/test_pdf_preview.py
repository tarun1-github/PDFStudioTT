"""PDF preview component tests: Image, Document, Compiler, multi-page, large PDF, missing dep, isolation."""
from io import BytesIO
from pathlib import Path
from PIL import Image
from streamlit.testing.v1 import AppTest

from frontend.components import ui as ui_comp


def _png_bytes(color=(20, 80, 180)) -> bytes:
    buf = BytesIO()
    Image.new("RGB", (300, 400), color).save(buf, format="PNG")
    return buf.getvalue()


def test_streamlit_pdf_package_installed():
    assert ui_comp.is_pdf_preview_available() is True


def test_pdf_preview_workflows_and_isolation(isolated_env, monkeypatch):
    client = isolated_env["client"]

    # 1. Image-to-PDF
    up_img = client.post(
        "/api/files/upload",
        headers={"X-Username": "engineer1"},
        files={"file": ("p1.png", _png_bytes(), "image/png")},
    )
    img_res = client.post(
        "/api/pdf/image-to-pdf",
        headers={"X-Username": "engineer1"},
        json={"input_paths": [up_img.json()["relative_path"]], "output_filename": "img_prev.pdf"},
    ).json()

    # 2. Document-to-PDF
    up_txt = client.post(
        "/api/files/upload",
        headers={"X-Username": "engineer1"},
        files={"file": ("doc.txt", b"Preview document text", "text/plain")},
    )
    doc_res = client.post(
        "/api/pdf/document-to-pdf",
        headers={"X-Username": "engineer1"},
        json={"input_path": up_txt.json()["relative_path"], "output_filename": "doc_prev.pdf"},
    ).json()

    # 3 & 4. PDF Compiler + Multi-page (25 pages for large PDF preview)
    many_imgs = [up_img.json()["relative_path"]] * 25
    large_res = client.post(
        "/api/pdf/image-to-pdf",
        headers={"X-Username": "engineer1"},
        json={"input_paths": many_imgs, "output_filename": "large_25p.pdf"},
    ).json()
    assert large_res["page_count"] == 25

    comp_res = client.post(
        "/api/pdf/compile",
        headers={"X-Username": "engineer1"},
        json={
            "items": [
                {"path": up_img.json()["relative_path"], "section_title": "Image"},
                {"path": up_txt.json()["relative_path"], "section_title": "Doc"},
            ],
            "output_filename": "comp_prev.pdf",
        },
    ).json()
    assert comp_res["page_count"] == 2

    # User isolation: lead1 cannot fetch engineer1's generated PDF bytes for preview
    r_forbidden = client.get(
        f"/api/files/documents/{comp_res['doc_uuid']}/download",
        headers={"X-Username": "lead1"},
    )
    assert r_forbidden.status_code == 403

    # Render helper via AppTest for Image, Document, Compiler, and 25-page Large PDF
    def _fake_download(path: str) -> bytes:
        r = client.get(path, headers={"X-Username": "engineer1"})
        assert r.status_code == 200
        return r.content

    monkeypatch.setattr(ui_comp, "api_download_bytes", _fake_download)

    for result_obj in (img_res, doc_res, comp_res, large_res):
        at = AppTest.from_string(
            f"from frontend.components.ui import render_generated_pdf_result\n"
            f"render_generated_pdf_result({result_obj!r})\n"
        )
        at.run()
        assert not at.exception
        assert len(at.warning) == 0

    # Missing dependency error handling
    monkeypatch.setattr(ui_comp, "is_pdf_preview_available", lambda: False)
    at_missing = AppTest.from_string(
        f"from frontend.components.ui import render_generated_pdf_result\n"
        f"render_generated_pdf_result({img_res!r})\n"
    )
    at_missing.run()
    assert not at_missing.exception
    assert len(at_missing.warning) == 1
    assert "streamlit-pdf" in at_missing.warning[0].value
