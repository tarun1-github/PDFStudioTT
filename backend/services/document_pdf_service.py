"""Document-to-PDF conversion using LibreOffice headless and ReportLab."""
import shutil
import subprocess
import tempfile
from pathlib import Path
from xml.sax.saxutils import escape

import markdown as md_lib
from bs4 import BeautifulSoup
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

from backend.services.image_pdf_service import verify_pdf_file

OFFICE_EXTENSIONS = {".docx", ".xlsx", ".pptx", ".html", ".htm"}
TEXT_MARKUP_EXTENSIONS = {".txt", ".md"}

LIBREOFFICE_CANDIDATES = [
    shutil.which("soffice"),
    shutil.which("libreoffice"),
    r"C:\Program Files\LibreOffice\program\soffice.exe",
    r"C:\Program Files (x86)\LibreOffice\program\soffice.exe",
]


def detect_libreoffice() -> str | None:
    """Return the path to soffice executable if installed, else None."""
    for candidate in LIBREOFFICE_CANDIDATES:
        if candidate and Path(candidate).exists():
            return str(Path(candidate))
    return None


def _text_or_markdown_to_pdf(input_path: Path, output_path: Path) -> None:
    raw = input_path.read_text(encoding="utf-8", errors="replace")
    if input_path.suffix.lower() == ".md":
        html = md_lib.markdown(raw, extensions=["tables", "fenced_code"])
        soup = BeautifulSoup(html, "html.parser")
        lines = [el.get_text(" ", strip=True) for el in soup.find_all(["h1", "h2", "h3", "p", "li", "pre"])]
        if not lines:
            lines = raw.splitlines()
    else:
        lines = raw.splitlines()

    output_path.parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=A4,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=18 * mm,
        bottomMargin=18 * mm,
        title=input_path.stem,
    )
    styles = getSampleStyleSheet()
    body_style = ParagraphStyle(
        "PdfStudioBody",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=10,
        leading=14,
    )
    story = []
    for line in lines:
        if not line.strip():
            story.append(Spacer(1, 6))
        else:
            story.append(Paragraph(escape(line), body_style))
            story.append(Spacer(1, 3))
    if not story:
        story.append(Paragraph(" ", body_style))
    doc.build(story)


def convert_document_to_pdf(
    input_path: Path,
    output_path: Path,
    timeout_seconds: int = 120,
) -> dict[str, int | str]:
    """Convert DOCX, TXT, MD, HTML, XLSX, or PPTX to a verified PDF."""
    if not input_path.exists():
        raise FileNotFoundError(f"Input file not found: {input_path}")

    ext = input_path.suffix.lower()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if ext in TEXT_MARKUP_EXTENSIONS:
        _text_or_markdown_to_pdf(input_path, output_path)
        page_count = verify_pdf_file(output_path)
        return {
            "output_path": str(output_path),
            "page_count": page_count,
            "file_size_bytes": output_path.stat().st_size,
            "engine": "reportlab",
        }

    if ext not in OFFICE_EXTENSIONS:
        raise ValueError(f"Unsupported document extension: {ext}")

    soffice = detect_libreoffice()
    if not soffice:
        raise RuntimeError(
            "LibreOffice (soffice.exe) is not installed on this machine. "
            "Install it with: winget install TheDocumentFoundation.LibreOffice"
        )

    with tempfile.TemporaryDirectory(prefix="pdfstudio_lo_") as tmp_dir:
        tmp_path = Path(tmp_dir)
        profile_dir = tmp_path / "lo_profile"
        profile_dir.mkdir(parents=True, exist_ok=True)
        cmd = [
            soffice,
            "--headless",
            "--norestore",
            f"-env:UserInstallation=file:///{profile_dir.as_posix()}",
            "--convert-to",
            "pdf",
            "--outdir",
            str(tmp_path),
            str(input_path),
        ]
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
        )
        if proc.returncode != 0:
            raise RuntimeError(
                f"LibreOffice conversion failed (exit {proc.returncode}): {proc.stderr or proc.stdout}"
            )

        expected_pdf = tmp_path / f"{input_path.stem}.pdf"
        if not expected_pdf.exists():
            pdfs = list(tmp_path.glob("*.pdf"))
            if not pdfs:
                raise RuntimeError("LibreOffice exited 0 but produced no PDF file.")
            expected_pdf = pdfs[0]

        shutil.move(str(expected_pdf), str(output_path))

    page_count = verify_pdf_file(output_path)
    return {
        "output_path": str(output_path),
        "page_count": page_count,
        "file_size_bytes": output_path.stat().st_size,
        "engine": "libreoffice",
    }
