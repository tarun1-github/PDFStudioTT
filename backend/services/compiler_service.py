"""Multi-format PDF Compiler preserving exact user ordering and section bookmarks."""
import tempfile
from dataclasses import dataclass
from pathlib import Path

from pypdf import PdfReader, PdfWriter

from backend.security.storage import DOCUMENT_EXTENSIONS, IMAGE_EXTENSIONS, PDF_EXTENSIONS
from backend.services.document_pdf_service import convert_document_to_pdf
from backend.services.image_pdf_service import images_to_pdf, verify_pdf_file


@dataclass
class CompilerItem:
    path: Path
    section_title: str


def compile_mixed_documents(
    items: list[CompilerItem],
    output_path: Path,
    page_size: str = "A4",
    orientation: str = "auto",
    margin_mm: float = 10.0,
) -> dict[str, int | str]:
    """Compile images, office/text documents, and PDFs into one ordered PDF."""
    if not items:
        raise ValueError("At least one input item is required to compile.")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    writer = PdfWriter()
    current_page_index = 0

    with tempfile.TemporaryDirectory(prefix="pdfstudio_compile_") as tmp_dir:
        tmp_root = Path(tmp_dir)
        for idx, item in enumerate(items, start=1):
            ext = item.path.suffix.lower()
            if ext in IMAGE_EXTENSIONS:
                part_pdf = tmp_root / f"part_{idx}.pdf"
                images_to_pdf(
                    [item.path],
                    part_pdf,
                    page_size=page_size,
                    orientation=orientation,
                    margin_mm=margin_mm,
                )
            elif ext in DOCUMENT_EXTENSIONS:
                part_pdf = tmp_root / f"part_{idx}.pdf"
                convert_document_to_pdf(item.path, part_pdf)
            elif ext in PDF_EXTENSIONS:
                verify_pdf_file(item.path)
                part_pdf = item.path
            else:
                raise ValueError(f"Unsupported file format in compiler: {ext}")

            reader = PdfReader(str(part_pdf))
            if item.section_title.strip():
                writer.add_outline_item(title=item.section_title.strip(), page_number=current_page_index)
            for page in reader.pages:
                writer.add_page(page)
                current_page_index += 1

    with output_path.open("wb") as f:
        writer.write(f)

    page_count = verify_pdf_file(output_path)
    return {
        "output_path": str(output_path),
        "page_count": page_count,
        "file_size_bytes": output_path.stat().st_size,
    }
