"""Comprehensive tests for Phase 15 Professional Learning Book Publisher & PDF Optimization."""
from io import BytesIO
from pathlib import Path

import pymupdf
from PIL import Image

from backend.services.learning_book_service import (
    LearningBookConfig,
    LearningSection,
    publish_learning_book,
    render_cover_preview_png,
)
from backend.services.pdf_optimization_service import optimize_pdf


def _make_logo_png(path: Path) -> Path:
    Image.new("RGBA", (240, 120), (37, 99, 235, 255)).save(path, format="PNG")
    return path


def _make_large_photo_png(path: Path, size=(1600, 1200)) -> Path:
    img = Image.new("RGB", size)
    px = img.load()
    for y in range(0, size[1], 4):
        for x in range(0, size[0], 4):
            px[x, y] = ((x * 3) % 255, (y * 5) % 255, ((x + y) * 2) % 255)
    img.save(path, format="PNG")
    return path


def test_cover_templates_logo_and_live_preview(tmp_path: Path):
    logo = _make_logo_png(tmp_path / "logo.png")
    for tpl in ("Corporate Technical Manual", "Cisco Learning Guide", "Training Workbook", "Minimal Professional"):
        cfg = LearningBookConfig(
            title=f"{tpl} Book",
            subtitle="Architecture & Labs",
            author="Alex Rivera",
            organization="Platform Engineering",
            date_str="2026-11-26",
            version="2.1",
            classification="Internal",
            template_name=tpl,
            page_orientation="landscape" if tpl == "Training Workbook" else "portrait",
            logo_path=logo,
        )
        png_bytes = render_cover_preview_png(cfg)
        assert png_bytes.startswith(b"\x89PNG")


def test_full_book_toc_links_bookmarks_dividers_roman_and_metadata(tmp_path: Path):
    logo = _make_logo_png(tmp_path / "logo.png")
    ch1 = tmp_path / "ch1.txt"
    ch1.write_text("Chapter 1 searchable body text.\nLine two.", encoding="utf-8")
    sec1_1 = tmp_path / "sec1_1.txt"
    sec1_1.write_text("Section 1.1 searchable details.", encoding="utf-8")
    ch2 = tmp_path / "ch2.png"
    _make_large_photo_png(ch2, (800, 600))

    cfg = LearningBookConfig(
        title="Enterprise Cloud Manual",
        subtitle="Phase 15 Validation",
        author="Jordan Lee",
        organization="Cisco Learning",
        date_str="2026-11-26",
        version="3.0",
        classification="Confidential",
        template_name="Cisco Learning Guide",
        logo_path=logo,
        include_toc=True,
        toc_title="Contents",
        include_dividers=True,
        divider_style="Classic Banner",
        count_dividers_in_numbering=True,
        page_number_style="Page 1 of N",
        roman_preliminary=True,
        hf_alignment="center",
        meta_subject="Cloud Architecture",
        meta_keywords="pdf,studio,cisco",
        compression_mode="High Quality",
    )
    sections = [
        LearningSection("Chapter 1: Foundations", ch1, chapter_number="1", chapter_title="Foundations", level=1),
        LearningSection("1.1 Core Concepts", sec1_1, chapter_number="1.1", chapter_title="Core Concepts", level=2),
        LearningSection("Chapter 2: Diagrams", ch2, chapter_number="2", chapter_title="Diagrams", level=1),
    ]
    out = tmp_path / "published.pdf"
    res = publish_learning_book(cfg, sections, out)
    # 1 Cover + 1 TOC + 2 Dividers (level=1) + 3 Content pages = 7 pages
    assert res["page_count"] == 7

    doc = pymupdf.open(str(out))
    try:
        # Metadata
        assert doc.metadata["title"] == "Enterprise Cloud Manual"
        assert doc.metadata["author"] == "Jordan Lee"
        assert doc.metadata["subject"] == "Cloud Architecture"
        assert doc.metadata["keywords"] == "pdf,studio,cisco"

        # Roman numeral on TOC page (index 1) and reset to Page 1 on first divider (index 2)
        toc_text = doc[1].get_text("text")
        assert "Contents" in toc_text
        assert "i" in toc_text
        div1_text = doc[2].get_text("text")
        assert "Page 1 of 5" in div1_text

        # Searchable text preserved
        assert "Chapter 1 searchable body text" in doc[3].get_text("text")

        # Clickable TOC links
        links = doc[1].get_links()
        assert len(links) == 3
        assert links[0]["page"] == 2  # Chapter 1 divider starts at 0-idx 2

        # Nested bookmarks (level 1 & level 2)
        toc_bm = doc.get_toc()
        assert any(b[0] == 1 and "Chapter 1: Foundations" in b[1] for b in toc_bm)
        assert any(b[0] == 2 and "1.1 Core Concepts" in b[1] for b in toc_bm)
    finally:
        doc.close()


def test_compression_modes_preserve_source_text_and_bookmarks(tmp_path: Path):
    photo = _make_large_photo_png(tmp_path / "photo.png", (1600, 1200))
    txt = tmp_path / "txt.txt"
    txt.write_text("Searchable text preserved across compression.", encoding="utf-8")

    src_pdf = tmp_path / "source_book.pdf"
    cfg = LearningBookConfig(title="Compression Test", author="QA", compression_mode="Original Quality")
    publish_learning_book(
        cfg,
        [LearningSection("Chapter 1", txt, level=1), LearningSection("Chapter 2", photo, level=1)],
        src_pdf,
    )
    orig_bytes = src_pdf.read_bytes()

    for mode in ("High Quality", "Balanced", "Small File Size"):
        opt_pdf = tmp_path / f"opt_{mode.replace(' ', '_')}.pdf"
        res = optimize_pdf(src_pdf, opt_pdf, mode=mode)
        assert res["page_count"] == 4
        assert opt_pdf.stat().st_size <= src_pdf.stat().st_size
        d = pymupdf.open(str(opt_pdf))
        try:
            assert len(d.get_toc()) >= 3
            assert "Searchable text preserved" in d[2].get_text("text")
        finally:
            d.close()

    # Original source file untouched
    assert src_pdf.read_bytes() == orig_bytes


def test_api_publisher_preview_optimize_and_isolation(isolated_env):
    client = isolated_env["client"]

    # Upload logo and chapter as engineer1
    buf = BytesIO()
    Image.new("RGB", (400, 300), (20, 80, 160)).save(buf, format="PNG")
    up = client.post(
        "/api/files/upload",
        headers={"X-Username": "engineer1"},
        files={"file": ("ch1.png", buf.getvalue(), "image/png")},
    ).json()

    # Live cover preview
    cov = client.post(
        "/api/pdf/learning-book/preview-cover",
        headers={"X-Username": "engineer1"},
        json={"title": "API Book", "template_name": "Minimal Professional", "sections": []},
    )
    assert cov.status_code == 200 and cov.content.startswith(b"\x89PNG")

    # Publish book
    pub = client.post(
        "/api/pdf/learning-book",
        headers={"X-Username": "engineer1"},
        json={
            "title": "API Book",
            "template_name": "Minimal Professional",
            "include_dividers": True,
            "compression_mode": "Balanced",
            "sections": [{"heading": "Chapter 1", "path": up["relative_path"], "chapter_number": "1"}],
            "output_filename": "api_book.pdf",
        },
    )
    assert pub.status_code == 200
    doc_uuid = pub.json()["doc_uuid"]

    # Cross-user isolation: lead1 blocked
    assert (
        client.get(f"/api/files/documents/{doc_uuid}/download", headers={"X-Username": "lead1"}).status_code
        == 403
    )
