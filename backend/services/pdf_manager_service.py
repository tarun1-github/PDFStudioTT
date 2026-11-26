"""PDF Manager operations: merge, split, extract, rotate, compress, number, watermark, bookmarks, metadata."""
from io import BytesIO
from pathlib import Path

import pikepdf
from pypdf import PdfReader, PdfWriter
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

from backend.services.image_pdf_service import verify_pdf_file


def _result(output_path: Path) -> dict[str, int | str]:
    pages = verify_pdf_file(output_path)
    return {
        "output_path": str(output_path),
        "page_count": pages,
        "file_size_bytes": output_path.stat().st_size,
    }


def merge_pdfs(input_paths: list[Path], output_path: Path, add_bookmarks: bool = True) -> dict[str, int | str]:
    if len(input_paths) < 2:
        raise ValueError("Provide at least 2 PDF files to merge.")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    writer = PdfWriter()
    page_idx = 0
    for p in input_paths:
        reader = PdfReader(str(p))
        if add_bookmarks:
            writer.add_outline_item(title=p.stem, page_number=page_idx)
        for page in reader.pages:
            writer.add_page(page)
            page_idx += 1
    with output_path.open("wb") as f:
        writer.write(f)
    return _result(output_path)


def split_pdf(input_path: Path, output_path: Path, start_page: int, end_page: int) -> dict[str, int | str]:
    reader = PdfReader(str(input_path))
    total = len(reader.pages)
    if start_page < 1 or end_page > total or start_page > end_page:
        raise ValueError(f"Invalid page range {start_page}-{end_page} for {total}-page PDF.")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    writer = PdfWriter()
    for i in range(start_page - 1, end_page):
        writer.add_page(reader.pages[i])
    with output_path.open("wb") as f:
        writer.write(f)
    return _result(output_path)


def extract_pages(input_path: Path, output_path: Path, pages: list[int]) -> dict[str, int | str]:
    reader = PdfReader(str(input_path))
    total = len(reader.pages)
    if not pages:
        raise ValueError("No page numbers specified.")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    writer = PdfWriter()
    for p in pages:
        if p < 1 or p > total:
            raise ValueError(f"Page {p} out of range (1..{total}).")
        writer.add_page(reader.pages[p - 1])
    with output_path.open("wb") as f:
        writer.write(f)
    return _result(output_path)


def rotate_pages(
    input_path: Path,
    output_path: Path,
    angle: int,
    pages: list[int] | None = None,
) -> dict[str, int | str]:
    if angle not in (90, 180, 270):
        raise ValueError("Rotation angle must be 90, 180, or 270.")
    reader = PdfReader(str(input_path))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    writer = PdfWriter()
    target_set = set(pages) if pages else None
    for idx, page in enumerate(reader.pages, start=1):
        if target_set is None or idx in target_set:
            page.rotate(angle)
        writer.add_page(page)
    with output_path.open("wb") as f:
        writer.write(f)
    return _result(output_path)


def compress_pdf(input_path: Path, output_path: Path) -> dict[str, int | str]:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with pikepdf.open(str(input_path)) as pdf:
        pdf.save(
            str(output_path),
            compress_streams=True,
            object_stream_mode=pikepdf.ObjectStreamMode.generate,
        )
    return _result(output_path)


def add_page_numbers(input_path: Path, output_path: Path, position: str = "bottom-right") -> dict[str, int | str]:
    reader = PdfReader(str(input_path))
    total = len(reader.pages)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    writer = PdfWriter()

    for idx, page in enumerate(reader.pages, start=1):
        pw = float(page.mediabox.width)
        ph = float(page.mediabox.height)
        buf = BytesIO()
        c = canvas.Canvas(buf, pagesize=(pw, ph))
        c.setFont("Helvetica", 9)
        c.setFillColor(colors.HexColor("#334155"))
        label = f"{idx} / {total}"
        if position == "bottom-center":
            c.drawCentredString(pw / 2.0, 10 * mm, label)
        else:
            c.drawRightString(pw - 14 * mm, 10 * mm, label)
        c.save()
        buf.seek(0)
        overlay = PdfReader(buf)
        attached = writer.add_page(page)
        attached.merge_page(overlay.pages[0])

    with output_path.open("wb") as f:
        writer.write(f)
    return _result(output_path)


def add_header_footer(
    input_path: Path,
    output_path: Path,
    header_text: str = "",
    footer_text: str = "",
) -> dict[str, int | str]:
    reader = PdfReader(str(input_path))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    writer = PdfWriter()
    for page in reader.pages:
        pw = float(page.mediabox.width)
        ph = float(page.mediabox.height)
        buf = BytesIO()
        c = canvas.Canvas(buf, pagesize=(pw, ph))
        c.setFont("Helvetica", 8.5)
        c.setFillColor(colors.HexColor("#475569"))
        if header_text:
            c.drawString(14 * mm, ph - 10 * mm, header_text[:100])
        if footer_text:
            c.drawString(14 * mm, 10 * mm, footer_text[:100])
        c.save()
        buf.seek(0)
        attached = writer.add_page(page)
        attached.merge_page(PdfReader(buf).pages[0])
    with output_path.open("wb") as f:
        writer.write(f)
    return _result(output_path)


def add_watermark(input_path: Path, output_path: Path, text: str) -> dict[str, int | str]:
    if not text.strip():
        raise ValueError("Watermark text cannot be empty.")
    reader = PdfReader(str(input_path))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    writer = PdfWriter()
    for page in reader.pages:
        pw = float(page.mediabox.width)
        ph = float(page.mediabox.height)
        buf = BytesIO()
        c = canvas.Canvas(buf, pagesize=(pw, ph))
        c.saveState()
        c.translate(pw / 2.0, ph / 2.0)
        c.rotate(45)
        c.setFillAlpha(0.18)
        c.setFillColor(colors.HexColor("#1E3A8A"))
        c.setFont("Helvetica-Bold", 42)
        c.drawCentredString(0, 0, text.strip()[:40])
        c.restoreState()
        c.save()
        buf.seek(0)
        attached = writer.add_page(page)
        attached.merge_page(PdfReader(buf).pages[0])
    with output_path.open("wb") as f:
        writer.write(f)
    return _result(output_path)


def add_bookmarks(
    input_path: Path,
    output_path: Path,
    bookmarks: list[tuple[str, int]],
) -> dict[str, int | str]:
    reader = PdfReader(str(input_path))
    total = len(reader.pages)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    writer = PdfWriter()
    for page in reader.pages:
        writer.add_page(page)
    for title, page_num in bookmarks:
        if 1 <= page_num <= total and title.strip():
            writer.add_outline_item(title=title.strip(), page_number=page_num - 1)
    with output_path.open("wb") as f:
        writer.write(f)
    return _result(output_path)


def update_metadata(
    input_path: Path,
    output_path: Path,
    title: str = "",
    author: str = "",
    subject: str = "",
    keywords: str = "",
) -> dict[str, int | str]:
    reader = PdfReader(str(input_path))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    writer = PdfWriter()
    for page in reader.pages:
        writer.add_page(page)
    meta = {
        "/Title": title,
        "/Author": author,
        "/Subject": subject,
        "/Keywords": keywords,
    }
    writer.add_metadata({k: v for k, v in meta.items() if v})
    with output_path.open("wb") as f:
        writer.write(f)
    return _result(output_path)
