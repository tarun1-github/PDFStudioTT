"""Smart Document Sequencing Engine using embedded text, Office parsers, and local OCR."""
import re
import shutil
import subprocess
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import pymupdf
from bs4 import BeautifulSoup
from docx import Document as DocxDocument
from openpyxl import load_workbook
from PIL import Image, ImageOps
from pptx import Presentation

from backend.security.storage import IMAGE_EXTENSIONS

APP_ROOT = Path(__file__).resolve().parent.parent.parent
WIN_OCR_SCRIPT = APP_ROOT / "scripts" / "win_ocr.ps1"

SORT_MODES = (
    "Original Upload Order",
    "Automatic Detection",
    "Sort by Page Number",
    "Sort by Chapter Number",
    "Chapter then Page Number",
    "Manual Ordering",
)

_ROMAN_MAP = {"I": 1, "V": 5, "X": 10, "L": 50, "C": 100}

# False-positive exclusion patterns (dates, IPs, phones, versions, figures, technical values)
_FALSE_POSITIVE_LINE_RE = re.compile(
    r"(?i)\b(version|ver\.?|v\d+\.\d+|ip|port|tel|phone|fax|fig\.?|figure|table|model|rev\.?|date)\b"
    r"|\b\d{1,3}(?:\.\d{1,3}){3}\b"
    r"|\b\d{4}[-/]\d{1,2}[-/]\d{1,2}\b"
    r"|\b\d{1,2}[-/]\d{1,2}[-/]\d{2,4}\b"
    r"|\+?\d[\d\s\-()]{7,}\d"
)

_PAGE_EXPLICIT_RE = re.compile(
    r"(?i)\b(?:page|pg\.?|p\.?)\s*([ivxlc]+|\d{1,4})(?:\s*(?:of|/)\s*(\d{1,4}))?\b"
)
_PAGE_FRACTION_RE = re.compile(r"(?i)\b(\d{1,4})\s*(?:of|/)\s*(\d{1,4})\b")
_STANDALONE_INT_RE = re.compile(r"^\s*[-–—\[\(]?\s*(\d{1,4})\s*[-–—\]\)]?\s*$")
_STANDALONE_ROMAN_RE = re.compile(r"^\s*[-–—\[\(]?\s*([ivxlc]{1,6})\s*[-–—\]\)]?\s*$", re.IGNORECASE)

_CHAPTER_WORD_RE = re.compile(
    r"(?i)^\s*(?:chapter|unit|module|section|part)\s+(\d+(?:\.\d+)*)\b(?:[\s:\-–—]+(.+))?$"
)
_APPENDIX_RE = re.compile(
    r"(?i)^\s*appendix\s+([A-Z])\b(?:[\s:\-–—]+(.+))?$"
)
_HIERARCHICAL_HEADING_RE = re.compile(
    r"^\s*(\d+(?:\.\d+)+)\s+([A-Za-z][^\n]{1,100})$"
)
_FILENAME_PAGE_RE = re.compile(r"(?i)(?:page|pg|p)[_\-\s]*(\d{1,4})")
_FILENAME_CHAP_RE = re.compile(r"(?i)(?:ch|chap|chapter|unit|mod|module)[_\-\s]*(\d+(?:\.\d+)*)")


@dataclass
class SequenceAnalysisItem:
    original_index: int
    proposed_order: int
    relative_path: str
    filename: str
    detected_chapter: str | None
    chapter_sort_key: list[int] | None
    detected_page: int | None
    detected_page_display: str | None
    total_pages: int | None
    extracted_heading: str | None
    detection_method: str
    confidence: float
    confidence_label: str
    status: str
    evidence_text: str
    physical_page_index: int | None = None
    physical_page_count: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def roman_to_int(roman: str) -> int | None:
    s = roman.strip().upper()
    if not s or not all(ch in _ROMAN_MAP for ch in s):
        return None
    total = 0
    prev = 0
    for ch in reversed(s):
        val = _ROMAN_MAP[ch]
        total = total - val if val < prev else total + val
        prev = val
    return total if 1 <= total <= 100 else None


def parse_chapter_sort_key(chapter: str | None) -> list[int] | None:
    """Convert chapter/section labels like '1.10' or 'Appendix B' into natural sort keys."""
    if not chapter:
        return None
    c = chapter.strip()
    m_app = re.match(r"(?i)^appendix\s+([A-Z])$", c)
    if m_app:
        return [10000, ord(m_app.group(1).upper()) - ord("A") + 1]
    nums = re.findall(r"\d+", c)
    if not nums:
        return None
    return [int(n) for n in nums]


def detect_ocr_engine() -> str:
    """Detect available local OCR engine without external cloud dependencies."""
    if shutil.which("tesseract"):
        return "tesseract"
    if WIN_OCR_SCRIPT.exists():
        return "windows_ocr"
    return "none"


def run_local_ocr_on_image(image_path: Path, max_dim: int = 1800) -> str:
    """Run local offline OCR on an image, resizing large images to save memory."""
    engine = detect_ocr_engine()
    if engine == "none":
        return ""

    try:
        with tempfile.TemporaryDirectory(prefix="pdfstudio_ocr_") as tmp_dir:
            target_path = image_path
            with Image.open(image_path) as raw:
                img = ImageOps.exif_transpose(raw)
                if max(img.size) > max_dim or image_path.suffix.lower() not in {".png", ".jpg", ".jpeg"}:
                    img = img.convert("RGB")
                    img.thumbnail((max_dim, max_dim), Image.Resampling.LANCZOS)
                    tmp_img = Path(tmp_dir) / "ocr_input.png"
                    img.save(tmp_img, format="PNG")
                    target_path = tmp_img

            if engine == "tesseract":
                proc = subprocess.run(
                    ["tesseract", str(target_path), "stdout", "--psm", "6"],
                    capture_output=True,
                    text=True,
                    timeout=30,
                    check=False,
                )
                return proc.stdout.strip() if proc.returncode == 0 else ""

            proc = subprocess.run(
                [
                    "powershell",
                    "-NoProfile",
                    "-ExecutionPolicy",
                    "Bypass",
                    "-File",
                    str(WIN_OCR_SCRIPT),
                    "-ImagePath",
                    str(target_path),
                ],
                capture_output=True,
                text=True,
                timeout=30,
                check=False,
            )
            return proc.stdout.strip() if proc.returncode == 0 else ""
    except (subprocess.TimeoutExpired, OSError, Exception):
        return ""


def _extract_text_from_file(file_path: Path) -> tuple[str, str, int | None]:
    """Return (extracted_text, detection_method, physical_page_count)."""
    ext = file_path.suffix.lower()
    if ext in IMAGE_EXTENSIONS:
        text = run_local_ocr_on_image(file_path)
        return text, ("ocr" if text else "filename"), 1

    if ext == ".pdf":
        doc = pymupdf.open(str(file_path))
        try:
            page_count = len(doc)
            if page_count == 0:
                return "", "none", 0
            first_page = doc[0]
            text = first_page.get_text("text").strip()
            if len(text) >= 15:
                return text, "embedded_text", page_count
            # Scanned PDF fallback: render first page at 150 DPI for local OCR
            pix = first_page.get_pixmap(dpi=150)
            with tempfile.TemporaryDirectory(prefix="pdfstudio_pdf_ocr_") as tmp_dir:
                tmp_png = Path(tmp_dir) / "page0.png"
                pix.save(str(tmp_png))
                ocr_text = run_local_ocr_on_image(tmp_png)
            return ocr_text, ("ocr" if ocr_text else "filename"), page_count
        finally:
            doc.close()

    if ext == ".docx":
        doc = DocxDocument(str(file_path))
        lines = [p.text.strip() for p in doc.paragraphs if p.text.strip()]
        return "\n".join(lines[:40]), "embedded_text", None

    if ext == ".pptx":
        prs = Presentation(str(file_path))
        lines: list[str] = []
        for slide in prs.slides[:10]:
            for shape in slide.shapes:
                if shape.has_text_frame:
                    txt = shape.text_frame.text.strip()
                    if txt:
                        lines.append(txt)
        return "\n".join(lines[:40]), "embedded_text", len(prs.slides)

    if ext == ".xlsx":
        wb = load_workbook(str(file_path), read_only=True, data_only=True)
        try:
            lines = []
            for sheet in wb.sheetnames[:3]:
                ws = wb[sheet]
                lines.append(sheet)
                for row in ws.iter_rows(max_row=8, values_only=True):
                    vals = [str(v).strip() for v in row if v is not None and str(v).strip()]
                    if vals:
                        lines.append(" ".join(vals))
            return "\n".join(lines), "embedded_text", None
        finally:
            wb.close()

    if ext in {".html", ".htm"}:
        soup = BeautifulSoup(file_path.read_text(encoding="utf-8", errors="replace"), "html.parser")
        lines = [el.get_text(" ", strip=True) for el in soup.find_all(["h1", "h2", "h3", "p"])[:30]]
        return "\n".join(lines), "embedded_text", None

    if ext in {".txt", ".md"}:
        raw = file_path.read_text(encoding="utf-8", errors="replace")
        cleaned = [ln.lstrip("# ").strip() for ln in raw.splitlines()[:40] if ln.strip()]
        return "\n".join(cleaned), "embedded_text", None

    return "", "filename", None


def extract_sequence_metadata(
    file_path: Path,
    original_index: int,
    relative_path: str,
) -> SequenceAnalysisItem:
    """Analyze a single file's content (with filename fallback) for chapter & page info."""
    text, method, phys_pages = _extract_text_from_file(file_path)
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]

    detected_chapter: str | None = None
    chapter_key: list[int] | None = None
    extracted_heading: str | None = None
    detected_page: int | None = None
    detected_page_display: str | None = None
    total_pages: int | None = None
    evidence_parts: list[str] = []
    confidence = 0.0

    # 1. Chapter / Section / Heading detection
    for ln in lines[:25]:
        if _FALSE_POSITIVE_LINE_RE.search(ln) and not re.match(r"(?i)^\s*(chapter|unit|module|appendix)\b", ln):
            continue
        m_chap = _CHAPTER_WORD_RE.match(ln)
        if m_chap:
            detected_chapter = m_chap.group(1)
            chapter_key = parse_chapter_sort_key(detected_chapter)
            extracted_heading = (m_chap.group(2) or ln).strip()[:120]
            evidence_parts.append(ln[:80])
            confidence = max(confidence, 0.90 if method == "embedded_text" else 0.85)
            break
        m_app = _APPENDIX_RE.match(ln)
        if m_app:
            detected_chapter = f"Appendix {m_app.group(1).upper()}"
            chapter_key = parse_chapter_sort_key(detected_chapter)
            extracted_heading = (m_app.group(2) or ln).strip()[:120]
            evidence_parts.append(ln[:80])
            confidence = max(confidence, 0.88)
            break
        m_hier = _HIERARCHICAL_HEADING_RE.match(ln)
        if m_hier:
            detected_chapter = m_hier.group(1)
            chapter_key = parse_chapter_sort_key(detected_chapter)
            extracted_heading = m_hier.group(2).strip()[:120]
            evidence_parts.append(ln[:80])
            confidence = max(confidence, 0.82)
            break

    if not extracted_heading and lines:
        extracted_heading = lines[0][:100]

    # 2. Page number detection (explicit markers first, then header/footer standalone)
    for ln in lines:
        if _FALSE_POSITIVE_LINE_RE.search(ln) and not _PAGE_EXPLICIT_RE.search(ln):
            continue
        m_exp = _PAGE_EXPLICIT_RE.search(ln)
        if m_exp:
            raw_pg = m_exp.group(1)
            if raw_pg.isdigit():
                detected_page = int(raw_pg)
                detected_page_display = raw_pg
            else:
                r_val = roman_to_int(raw_pg)
                if r_val is not None:
                    detected_page = r_val
                    detected_page_display = raw_pg.lower()
            if m_exp.group(2):
                total_pages = int(m_exp.group(2))
            if detected_page is not None:
                evidence_parts.append(m_exp.group(0))
                confidence = max(confidence, 0.95 if method == "embedded_text" else 0.85)
                break

    if detected_page is None:
        # Check fraction "1/10" or "1 of 10" in header/footer lines
        edge_lines = lines[:2] + (lines[-2:] if len(lines) > 2 else [])
        for ln in edge_lines:
            if _FALSE_POSITIVE_LINE_RE.search(ln):
                continue
            m_frac = _PAGE_FRACTION_RE.search(ln)
            if m_frac:
                p_num, t_num = int(m_frac.group(1)), int(m_frac.group(2))
                if 1 <= p_num <= t_num <= 2000:
                    detected_page = p_num
                    detected_page_display = str(p_num)
                    total_pages = t_num
                    evidence_parts.append(m_frac.group(0))
                    confidence = max(confidence, 0.82 if method == "embedded_text" else 0.72)
                    break

    if detected_page is None and lines:
        edge_lines = lines[:2] + (lines[-2:] if len(lines) > 2 else [])
        for ln in edge_lines:
            if _FALSE_POSITIVE_LINE_RE.search(ln):
                continue
            m_int = _STANDALONE_INT_RE.match(ln)
            if m_int and 1 <= int(m_int.group(1)) <= 2000:
                detected_page = int(m_int.group(1))
                detected_page_display = str(detected_page)
                evidence_parts.append(ln)
                confidence = max(confidence, 0.70 if method == "embedded_text" else 0.62)
                break
            m_rom = _STANDALONE_ROMAN_RE.match(ln)
            if m_rom:
                r_val = roman_to_int(m_rom.group(1))
                if r_val is not None:
                    detected_page = r_val
                    detected_page_display = m_rom.group(1).lower()
                    evidence_parts.append(ln)
                    confidence = max(confidence, 0.65)
                    break

    # 3. Filename fallback only when content yielded nothing
    stem = file_path.stem
    if detected_chapter is None:
        m_fc = _FILENAME_CHAP_RE.search(stem)
        if m_fc:
            detected_chapter = m_fc.group(1)
            chapter_key = parse_chapter_sort_key(detected_chapter)
            method = "filename" if method != "embedded_text" else method
            confidence = max(confidence, 0.45)
            evidence_parts.append(f"filename:{m_fc.group(0)}")

    if detected_page is None:
        m_fp = _FILENAME_PAGE_RE.search(stem)
        if m_fp:
            detected_page = int(m_fp.group(1))
            detected_page_display = str(detected_page)
            method = "filename" if method != "embedded_text" else method
            confidence = max(confidence, 0.45)
            evidence_parts.append(f"filename:{m_fp.group(0)}")

    if detected_page is None and detected_chapter is None:
        confidence_label = "Not detected"
        status = "Not detected"
        if not evidence_parts:
            evidence_parts.append("No sequence markers detected")
    elif confidence >= 0.80:
        confidence_label = "High confidence"
        status = "High confidence"
    elif confidence >= 0.55:
        confidence_label = "Medium confidence"
        status = "Medium confidence"
    else:
        confidence_label = "Low confidence"
        status = "Low confidence"

    return SequenceAnalysisItem(
        original_index=original_index,
        proposed_order=original_index + 1,
        relative_path=relative_path,
        filename=file_path.name,
        detected_chapter=detected_chapter,
        chapter_sort_key=chapter_key,
        detected_page=detected_page,
        detected_page_display=detected_page_display,
        total_pages=total_pages,
        extracted_heading=extracted_heading,
        detection_method=method,
        confidence=round(confidence, 2),
        confidence_label=confidence_label,
        status=status,
        evidence_text=" | ".join(evidence_parts)[:200],
        physical_page_index=0 if file_path.suffix.lower() == ".pdf" else None,
        physical_page_count=phys_pages,
    )


def _choose_effective_mode(items: list[SequenceAnalysisItem], requested_mode: str) -> str:
    if requested_mode != "Automatic Detection":
        return requested_mode
    has_chap = any(it.chapter_sort_key is not None for it in items)
    has_page = any(it.detected_page is not None for it in items)
    if has_chap and has_page:
        return "Chapter then Page Number"
    if has_page:
        return "Sort by Page Number"
    if has_chap:
        return "Sort by Chapter Number"
    return "Original Upload Order"


def sort_and_validate_sequence(
    items: list[SequenceAnalysisItem],
    sort_mode: str = "Automatic Detection",
) -> dict[str, Any]:
    """Sort analyzed items according to the chosen mode and detect duplicates/missing pages."""
    effective_mode = _choose_effective_mode(items, sort_mode)

    if effective_mode in ("Original Upload Order", "Manual Ordering"):
        ordered = sorted(items, key=lambda it: it.original_index)
    elif effective_mode == "Sort by Page Number":
        ordered = sorted(
            items,
            key=lambda it: (
                0 if it.detected_page is not None else 1,
                it.detected_page if it.detected_page is not None else 999999,
                it.original_index,
            ),
        )
    elif effective_mode == "Sort by Chapter Number":
        ordered = sorted(
            items,
            key=lambda it: (
                0 if it.chapter_sort_key is not None else 1,
                it.chapter_sort_key if it.chapter_sort_key is not None else [999999],
                it.original_index,
            ),
        )
    else:  # Chapter then Page Number
        ordered = sorted(
            items,
            key=lambda it: (
                0 if (it.chapter_sort_key is not None or it.detected_page is not None) else 1,
                0 if it.chapter_sort_key is not None else 1,
                it.chapter_sort_key if it.chapter_sort_key is not None else [999999],
                0 if it.detected_page is not None else 1,
                it.detected_page if it.detected_page is not None else 999999,
                it.original_index,
            ),
        )

    for idx, it in enumerate(ordered, start=1):
        it.proposed_order = idx

    # Duplicate & missing page detection grouped by chapter
    duplicates: list[str] = []
    missing_pages: list[str] = []
    by_chapter: dict[str, list[SequenceAnalysisItem]] = {}
    for it in ordered:
        chap_label = it.detected_chapter or "Unassigned"
        by_chapter.setdefault(chap_label, []).append(it)

    for chap_label, group in by_chapter.items():
        seen_pages: dict[int, list[SequenceAnalysisItem]] = {}
        for it in group:
            if it.detected_page is not None:
                seen_pages.setdefault(it.detected_page, []).append(it)
        for pg, dup_items in sorted(seen_pages.items()):
            if len(dup_items) > 1:
                duplicates.append(f"Chapter '{chap_label}': Duplicate page {pg} ({len(dup_items)} files)")
                for di in dup_items:
                    di.status = "Duplicate page"

        if seen_pages:
            nums = sorted(seen_pages.keys())
            for expected in range(nums[0], nums[-1] + 1):
                if expected not in seen_pages:
                    missing_pages.append(f"Chapter '{chap_label}': Missing page {expected}")

    return {
        "requested_mode": sort_mode,
        "resolved_mode": effective_mode,
        "items": [it.to_dict() for it in ordered],
        "duplicates": duplicates,
        "missing_pages": missing_pages,
        "ocr_engine": detect_ocr_engine(),
    }


def analyze_document_sequence(
    file_entries: list[tuple[Path, str]],
    sort_mode: str = "Automatic Detection",
) -> dict[str, Any]:
    """Analyze up to 100 uploaded files and return sorted sequence + diagnostics."""
    if len(file_entries) > 100:
        raise ValueError("Batch size exceeds maximum of 100 files.")
    analyzed = [
        extract_sequence_metadata(path, idx, rel)
        for idx, (path, rel) in enumerate(file_entries)
    ]
    return sort_and_validate_sequence(analyzed, sort_mode=sort_mode)
