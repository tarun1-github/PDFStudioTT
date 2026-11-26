"""Dedicated tests for colorful sketchnote OCR preprocessing, header/footer page numbers, and sorting."""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

from backend.services.document_sequence_service import (
    analyze_document_sequence,
    extract_sequence_metadata,
    try_vision_fallback,
)


def _make_colorful_sketchnote(
    path: Path,
    header_text: str = "",
    footer_text: str = "",
    bg_color: tuple[int, int, int] = (242, 236, 218),
    add_diagram: bool = True,
) -> Path:
    img = Image.new("RGB", (1200, 900), bg_color)
    d = ImageDraw.Draw(img)
    font = ImageFont.truetype(r"C:\Windows\Fonts\arial.ttf", 28)

    if header_text:
        d.text((35, 28), header_text, fill=(25, 25, 30), font=font)
    if add_diagram:
        # Simulate colorful sketchnote boxes/arrows in the body
        d.rectangle([120, 240, 520, 480], outline=(37, 99, 235), width=4, fill=(219, 234, 254))
        d.ellipse([660, 260, 1020, 520], outline=(5, 150, 105), width=4, fill=(209, 250, 229))
        d.line([520, 360, 660, 390], fill=(220, 38, 38), width=5)
        d.text((160, 340), "Concept Diagram 10.1.2.3", fill=(15, 23, 42), font=font)
    if footer_text:
        d.text((420, 825), footer_text, fill=(30, 30, 35), font=font)

    fmt = "JPEG" if path.suffix.lower() in {".jpg", ".jpeg"} else "PNG"
    img.save(path, format=fmt)
    return path


def test_sketchnote_header_colon_and_pipe_chapter_extraction(tmp_path: Path):
    p = _make_colorful_sketchnote(
        tmp_path / "handwritten_sket_7.png",
        header_text="Nimisha Taneja | Class X | 25 Nov 2026 | Chapter 1 | Page: 2",
    )
    item = extract_sequence_metadata(p, 0, "handwritten_sket_7.png")
    assert item.detected_chapter == "1"
    assert item.detected_page == 2
    assert item.confidence_label == "High"
    assert item.status == "Detected"


def test_colorful_sketchnotes_random_filenames_and_accuracy(tmp_path: Path):
    specs = [
        ("sket_99.png", "Nimisha Taneja | Class X | 25 Nov 2026 | Chapter 1 | Page: 4", "", 4),
        ("rand_a.jpg", "Unit 1 | Page 1", "", 1),
        ("sket_7.png", "Nimisha Taneja | Class X | 25 Nov 2026 | Chapter 1 | Page: 2", "", 2),
        ("notes_z.png", "Chapter 1", "Pg. 3", 3),
        ("final_0.png", "Chapter 1", "Page - 5", 5),
    ]
    entries = []
    for fname, hdr, ftr, _expected_pg in specs:
        p = _make_colorful_sketchnote(tmp_path / fname, header_text=hdr, footer_text=ftr)
        entries.append((p, fname))

    res = analyze_document_sequence(entries, sort_mode="Automatic Detection")
    items = res["items"]
    detected_pages = [it["detected_page"] for it in items]

    correct_pages = sum(1 for it, exp in zip(items, [1, 2, 3, 4, 5]) if it["detected_page"] == exp)
    print(f"\n[SKETCHNOTE ACCURACY] page_accuracy={correct_pages}/5 ({correct_pages/5*100:.0f}%)")
    assert detected_pages == [1, 2, 3, 4, 5]
    assert res["duplicates"] == []
    assert res["missing_pages"] == []


def test_sketchnote_duplicates_missing_and_vision_unavailable(tmp_path: Path, monkeypatch):
    p1 = _make_colorful_sketchnote(tmp_path / "a.png", header_text="Chapter 1 | Page: 1")
    p2 = _make_colorful_sketchnote(tmp_path / "b.png", header_text="Chapter 1 | Page: 2")
    p2_dup = _make_colorful_sketchnote(tmp_path / "c.png", header_text="Chapter 1 | Page: 2")
    p4 = _make_colorful_sketchnote(tmp_path / "d.png", header_text="Chapter 1 | Page: 4")

    res = analyze_document_sequence(
        [(p4, "d"), (p2, "b"), (p1, "a"), (p2_dup, "c")],
        sort_mode="Automatic Detection",
    )
    assert any("Duplicate page 2" in d for d in res["duplicates"])
    assert any("Missing page 3" in m for m in res["missing_pages"])

    # Vision fallback unavailable returns None safely
    monkeypatch.setenv("VISION_FALLBACK_ENABLED", "false")
    assert try_vision_fallback(p1) is None
