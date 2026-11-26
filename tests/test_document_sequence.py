"""Comprehensive tests for Smart Document Sequencing (OCR, PDF, DOCX, sorting, duplicates, isolation)."""
import time
from io import BytesIO
from pathlib import Path

from docx import Document as DocxDocument
from PIL import Image, ImageDraw, ImageFont
from pypdf import PdfReader
from reportlab.pdfgen import canvas

from backend.services.document_sequence_service import (
    analyze_document_sequence,
    extract_sequence_metadata,
    parse_chapter_sort_key,
    roman_to_int,
)


def _make_ocr_png(path: Path, text: str) -> Path:
    img = Image.new("RGB", (900, 260), (255, 255, 255))
    d = ImageDraw.Draw(img)
    font = ImageFont.truetype(r"C:\Windows\Fonts\arial.ttf", 34)
    y = 40
    for line in text.splitlines():
        d.text((40, y), line, fill=(0, 0, 0), font=font)
        y += 52
    img.save(path, format="PNG")
    return path


def _make_text_pdf(path: Path, text: str) -> Path:
    c = canvas.Canvas(str(path))
    y = 760
    for line in text.splitlines():
        c.drawString(50, y, line)
        y -= 24
    c.showPage()
    c.save()
    return path


def test_ocr_page_ordering_from_random_filenames(tmp_path: Path):
    f1 = _make_ocr_png(tmp_path / "x9z_random.png", "Architecture Notes\nPage 3 of 3")
    f2 = _make_ocr_png(tmp_path / "a00_img.png", "Architecture Notes\nPage 1 of 3")
    f3 = _make_ocr_png(tmp_path / "m4k_scan.png", "Architecture Notes\nPage 2 of 3")

    res = analyze_document_sequence([(f1, "f1"), (f2, "f2"), (f3, "f3")], sort_mode="Automatic Detection")
    ordered_names = [it["filename"] for it in res["items"]]
    assert ordered_names == ["a00_img.png", "m4k_scan.png", "x9z_random.png"]
    assert [it["detected_page"] for it in res["items"]] == [1, 2, 3]


def test_hierarchical_section_and_chapter_ordering(tmp_path: Path):
    assert parse_chapter_sort_key("1.10") > parse_chapter_sort_key("1.2")
    assert parse_chapter_sort_key("Appendix B") > parse_chapter_sort_key("Appendix A")

    files = []
    for name, content in [
        ("z.txt", "1.10 Advanced Topics\nDetails"),
        ("a.txt", "1.2 Core Setup\nDetails"),
        ("b.txt", "Appendix A - Glossary\nTerms"),
        ("c.txt", "Chapter 1: Introduction\nOverview"),
    ]:
        p = tmp_path / name
        p.write_text(content, encoding="utf-8")
        files.append((p, name))

    res = analyze_document_sequence(files, sort_mode="Sort by Chapter Number")
    assert [it["filename"] for it in res["items"]] == ["c.txt", "a.txt", "z.txt", "b.txt"]


def test_chapter_then_page_and_duplicates_and_missing(tmp_path: Path):
    entries = []
    for idx, (fname, txt) in enumerate([
        ("r1.txt", "Chapter 2\nPage 1"),
        ("r2.txt", "Chapter 1\nPage 4"),
        ("r3.txt", "Chapter 1\nPage 2"),
        ("r4.txt", "Chapter 1\nPage 2"),
        ("r5.txt", "Chapter 1\nPage 1"),
    ]):
        p = tmp_path / fname
        p.write_text(txt, encoding="utf-8")
        entries.append((p, fname))

    res = analyze_document_sequence(entries, sort_mode="Chapter then Page Number")
    assert [it["filename"] for it in res["items"]] == ["r5.txt", "r3.txt", "r4.txt", "r2.txt", "r1.txt"]
    assert any("Duplicate page 2" in d for d in res["duplicates"])
    assert any("Missing page 3" in m for m in res["missing_pages"])
    assert len(res["items"]) == 5  # never auto-deletes duplicates


def test_roman_numerals_and_false_positive_rejection(tmp_path: Path):
    assert roman_to_int("iv") == 4
    p1 = tmp_path / "r_iv.txt"
    p1.write_text("Preface\nPage iv", encoding="utf-8")
    p2 = tmp_path / "r_ii.txt"
    p2.write_text("Preface\nPage ii", encoding="utf-8")
    p_fp = tmp_path / "tech.txt"
    p_fp.write_text(
        "Server IP 10.106.44.24\nVersion 2.10\nDate 2026-11-26\nModel 1234\nPhone +1-555-0199\nFigure 3",
        encoding="utf-8",
    )

    res = analyze_document_sequence([(p1, "1"), (p2, "2"), (p_fp, "3")], sort_mode="Automatic Detection")
    assert [it["filename"] for it in res["items"]] == ["r_ii.txt", "r_iv.txt", "tech.txt"]
    fp_item = res["items"][2]
    assert fp_item["detected_page"] is None
    assert fp_item["status"] == "Not detected"


def test_mixed_docx_pdf_printed_page_vs_physical_index(tmp_path: Path):
    docx_p = tmp_path / "z_doc.docx"
    d = DocxDocument()
    d.add_heading("Chapter 1 - Overview", level=1)
    d.add_paragraph("Page 1")
    d.save(docx_p)

    pdf_p = _make_text_pdf(tmp_path / "a_pdf.pdf", "Chapter 2 - Deep Dive\nPrinted Pg. 5")

    res = analyze_document_sequence([(pdf_p, "pdf"), (docx_p, "docx")], sort_mode="Chapter then Page Number")
    assert res["items"][0]["filename"] == "z_doc.docx"
    assert res["items"][1]["filename"] == "a_pdf.pdf"
    assert res["items"][1]["physical_page_index"] == 0
    assert res["items"][1]["detected_page"] == 5


def test_manual_override_and_upload_order_fallback(tmp_path: Path):
    p1 = tmp_path / "one.txt"
    p1.write_text("Unnumbered alpha", encoding="utf-8")
    p2 = tmp_path / "two.txt"
    p2.write_text("Unnumbered beta", encoding="utf-8")

    res = analyze_document_sequence([(p1, "1"), (p2, "2")], sort_mode="Automatic Detection")
    assert res["resolved_mode"] == "Original Upload Order"
    assert [it["filename"] for it in res["items"]] == ["one.txt", "two.txt"]


def test_api_sequence_compiler_learning_book_and_isolation(isolated_env):
    client = isolated_env["client"]

    # Upload 2 out-of-order text chapters as engineer1
    u1 = client.post(
        "/api/files/upload",
        headers={"X-Username": "engineer1"},
        files={"file": ("rand_b.txt", b"Chapter 2 - Implementation\nPage 2", "text/plain")},
    ).json()
    u2 = client.post(
        "/api/files/upload",
        headers={"X-Username": "engineer1"},
        files={"file": ("rand_a.txt", b"Chapter 1 - Introduction\nPage 1", "text/plain")},
    ).json()

    # Cross-user isolation: lead1 cannot analyze engineer1's file path
    r_cross = client.post(
        "/api/pdf/analyze-sequence",
        headers={"X-Username": "lead1"},
        json={"input_paths": [u1["relative_path"]]},
    )
    assert r_cross.status_code in (400, 403)

    # Analyze sequence as engineer1
    seq = client.post(
        "/api/pdf/analyze-sequence",
        headers={"X-Username": "engineer1"},
        json={"input_paths": [u1["relative_path"], u2["relative_path"]], "sort_mode": "Automatic Detection"},
    )
    assert seq.status_code == 200
    items = seq.json()["items"]
    assert items[0]["filename"].endswith("rand_a.txt")
    assert items[1]["filename"].endswith("rand_b.txt")

    # Compile using suggested order
    comp = client.post(
        "/api/pdf/compile",
        headers={"X-Username": "engineer1"},
        json={
            "items": [{"path": it["relative_path"], "section_title": it["extracted_heading"]} for it in items],
            "output_filename": "seq_compiled.pdf",
        },
    )
    assert comp.status_code == 200 and comp.json()["page_count"] == 2

    # Learning Book Creator using suggested order
    book = client.post(
        "/api/pdf/learning-book",
        headers={"X-Username": "engineer1"},
        json={
            "title": "Sequenced Book",
            "subtitle": "Auto Ordered",
            "author": "Engineer",
            "date_str": "2026-11-26",
            "template_name": "AI Learning Notes",
            "sections": [{"heading": it["extracted_heading"], "path": it["relative_path"]} for it in items],
            "output_filename": "seq_book.pdf",
        },
    )
    assert book.status_code == 200 and book.json()["page_count"] >= 4


def test_ocr_timeout_graceful_fallback(tmp_path: Path, monkeypatch):
    import subprocess
    from backend.services import document_sequence_service as dss

    img = _make_ocr_png(tmp_path / "pg_04_notes.png", "Chapter 1 Page 4")
    monkeypatch.setattr(dss.subprocess, "run", lambda *a, **kw: (_ for _ in ()).throw(subprocess.TimeoutExpired("ocr", 30)))

    res = analyze_document_sequence([(img, "pg_04_notes.png")], sort_mode="Automatic Detection")
    assert len(res["items"]) == 1
    assert res["items"][0]["detected_page"] == 4
    assert res["items"][0]["detection_method"] == "filename"


def test_batch_20_text_docs_performance(tmp_path: Path):
    entries = []
    for i in range(20, 0, -1):
        p = tmp_path / f"rand_{i}.txt"
        p.write_text(f"Chapter 1\nPage {i}", encoding="utf-8")
        entries.append((p, p.name))
    t0 = time.perf_counter()
    res = analyze_document_sequence(entries, sort_mode="Automatic Detection")
    elapsed = time.perf_counter() - t0
    assert [it["detected_page"] for it in res["items"]] == list(range(1, 21))
    assert elapsed < 2.0
