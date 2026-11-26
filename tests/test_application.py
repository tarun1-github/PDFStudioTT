"""Application health, API flow, and Streamlit smoke tests."""
from io import BytesIO
from PIL import Image
from streamlit.testing.v1 import AppTest


def test_api_health_and_end_to_end_flow(isolated_env):
    client = isolated_env["client"]

    assert client.get("/health").status_code == 200
    deps = client.get("/health/dependencies")
    assert deps.status_code == 200
    assert deps.json()["storage_ready"] is True

    buf = BytesIO()
    Image.new("RGB", (300, 400), (50, 100, 150)).save(buf, format="PNG")
    up = client.post(
        "/api/files/upload",
        headers={"X-Username": "lead1"},
        files={"file": ("page.png", buf.getvalue(), "image/png")},
    )
    assert up.status_code == 200

    gen = client.post(
        "/api/pdf/image-to-pdf",
        headers={"X-Username": "lead1"},
        json={"input_paths": [up.json()["relative_path"]], "output_filename": "team_doc.pdf"},
    )
    assert gen.status_code == 200
    doc_uuid = gen.json()["doc_uuid"]

    dl = client.get(
        f"/api/files/documents/{doc_uuid}/download",
        headers={"X-Username": "lead1"},
    )
    assert dl.status_code == 200
    assert dl.content.startswith(b"%PDF-")

    pub = client.post(
        "/api/shared/publish",
        headers={"X-Username": "lead1"},
        json={"doc_uuid": doc_uuid, "category": "technical_documents", "title": "Team Guide"},
    )
    assert pub.status_code == 200

    kpis = client.get("/api/jobs/stats/kpis", headers={"X-Username": "lead1"})
    assert kpis.status_code == 200
    assert kpis.json()["pdfs_generated"] == 1


def test_streamlit_app_initializes():
    from pathlib import Path

    app_file = Path(__file__).resolve().parent.parent / "frontend" / "streamlit_app.py"
    at = AppTest.from_file(str(app_file), default_timeout=15)
    at.run()
    assert not at.exception
