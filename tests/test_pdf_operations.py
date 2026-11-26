"""PDF Manager, Compiler, and Learning Book Creator tests."""
from pathlib import Path
from PIL import Image
from pypdf import PdfReader

from backend.services.compiler_service import CompilerItem, compile_mixed_documents
from backend.services.image_pdf_service import images_to_pdf
from backend.services.learning_book_service import LearningSection, create_learning_book
from backend.services.pdf_manager_service import (
    add_bookmarks,
    add_page_numbers,
    compress_pdf,
    extract_pages,
    merge_pdfs,
    rotate_pages,
    split_pdf,
)


def _sample_pdf(path: Path, num_pages: int = 3) -> Path:
    imgs = []
    for i in range(num_pages):
        img_p = path.parent / f"{path.stem}_{i}.png"
        Image.new("RGB", (600, 800), (20 * (i + 1), 90, 160)).save(img_p)
        imgs.append(img_p)
    images_to_pdf(imgs, path)
    return path


def test_pdf_manager_operations(tmp_path: Path):
    p1 = _sample_pdf(tmp_path / "a.pdf", 2)
    p2 = _sample_pdf(tmp_path / "b.pdf", 2)

    merged = tmp_path / "merged.pdf"
    assert merge_pdfs([p1, p2], merged, add_bookmarks=True)["page_count"] == 4
    assert len(PdfReader(str(merged)).outline) >= 2

    split_out = tmp_path / "split.pdf"
    assert split_pdf(merged, split_out, 2, 3)["page_count"] == 2

    ext_out = tmp_path / "extracted.pdf"
    assert extract_pages(merged, ext_out, [1, 4])["page_count"] == 2

    rot_out = tmp_path / "rotated.pdf"
    assert rotate_pages(ext_out, rot_out, 90, [1])["page_count"] == 2

    num_out = tmp_path / "numbered.pdf"
    assert add_page_numbers(merged, num_out)["page_count"] == 4

    bm_out = tmp_path / "bookmarked.pdf"
    assert add_bookmarks(num_out, bm_out, [("Intro", 1), ("Part 2", 3)])["page_count"] == 4
    assert len(PdfReader(str(bm_out)).outline) >= 2

    comp_out = tmp_path / "compressed.pdf"
    assert compress_pdf(bm_out, comp_out)["page_count"] == 4


def test_mixed_compiler_and_learning_book(tmp_path: Path):
    img = tmp_path / "sketch.png"
    Image.new("RGB", (1000, 700), (40, 110, 200)).save(img)
    txt = tmp_path / "notes.txt"
    txt.write_text("Section text content.", encoding="utf-8")
    existing_pdf = _sample_pdf(tmp_path / "existing.pdf", 1)

    compiled = tmp_path / "compiled.pdf"
    res_c = compile_mixed_documents(
        [
            CompilerItem(img, "Architecture Sketch"),
            CompilerItem(txt, "Notes"),
            CompilerItem(existing_pdf, "Appendix"),
        ],
        compiled,
    )
    assert res_c["page_count"] == 3

    book = tmp_path / "book.pdf"
    res_b = create_learning_book(
        output_path=book,
        title="AI Engineering Guide",
        subtitle="Sketchnotes & Patterns",
        author="Test Author",
        date_str="2026-11-26",
        template_name="AI Learning Notes",
        sections=[
            LearningSection("Chapter 1: Sketch", img),
            LearningSection("Chapter 2: Notes", txt),
        ],
    )
    assert res_b["page_count"] >= 4
    reader = PdfReader(str(book))
    assert reader.metadata.get("/Title") == "AI Engineering Guide"
    assert len(reader.outline) >= 4
