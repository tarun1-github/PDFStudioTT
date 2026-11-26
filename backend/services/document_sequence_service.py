"""Smart Document Sequencing Engine using embedded text, preprocessed multi-region OCR, and optional vision fallback."""
import base64
import json
import re
import shutil
import subprocess
import tempfile
from dataclasses import asdict, dataclass
from io import BytesIO
from pathlib import Path
from typing import Any

import httpx
import pymupdf
from bs4 import BeautifulSoup
from docx import Document as DocxDocument
from openpyxl import load_workbook
from PIL import Image, ImageEnhance, ImageFilter, ImageOps
from pptx import Presentation

from backend.config import get_settings
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

# False-positive exclusion patterns (dates, IPs, phones, versions, figures, technical values, class)
_FALSE_POSITIVE_LINE_RE = re.compile(
    r"(?i)\b(version|ver\.?|v\d+\.\d+|ip|port|tel|phone|fax|fig\.?|figure|table|model|rev\.?|date|class)\b"
    r"|\b\d{1,3}(?:\.\d{1,3}){3}\b"
    r"|\b\d{4}[-/]\d{1,2}[-/]\d{1,2}\b"
    r"|\b\d{1,2}[-/]\d{1,2}[-/]\d{2,4}\b"
    r"|\b\d{1,2}\s+(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\s+\d{2,4}\b"
    r"|\+?\d[\d\s\-()]{7,}\d"
)

# Explicit page markers: Page 1, Page: 2, Page - 2, Pg 1, Pg. 1, P. 1, Page 1 of 10, Page: 2/10
_PAGE_EXPLICIT_RE = re.compile(
    r"(?i)\b(?:page|pg\.?|p\.)\s*[:\-–—]?\s*([ivxlc]+|\d{1,4})(?:\s*(?:of|/)\s*(\d{1,4}))?\b"
)
_PAGE_FRACTION_RE = re.compile(r"(?i)\b(\d{1,4})\s*(?:of|/)\s*(\d{1,4})\b")
_STANDALONE_INT_RE = re.compile(r"^\s*[-–—\[\(]?\s*(\d{1,4})\s*[-–—\]\)]?\s*$")
_STANDALONE_ROMAN_RE = re.compile(r"^\s*[-–—\[\(]?\s*([ivxlc]{1,6})\s*[-–—\]\)]?\s*$", re.IGNORECASE)

# Chapter/Section patterns: line-start OR inline after | / , / -
_CHAPTER_WORD_RE = re.compile(
    r"(?i)(?:^|[|,\-–—]\s*)(?:chapter|unit|module|section|part)\s*[:\-–—]?\s*(\d+(?:\.\d+)*)\b(?:\s*[:\-–—]\s*([^|\n]+))?"
)
_APPENDIX_RE = re.compile(
    r"(?i)(?:^|[|,\-–—]\s*)appendix\s*[:\-–—]?\s*([A-Z])\b(?:\s*[:\-–—]\s*([^|\n]+))?"
)
_HIERARCHICAL_HEADING_RE = re.compile(
    r"^\s*(\d+(?:\.\d+)+)\s+([A-Za-z][^\n]{1,100})$"
)
_FILENAME_PAGE_RE = re.compile(r"(?i)(?:page|pg|p)[_\-\s]*(\d{1,4})")
_FILENAME_CHAP_RE = re.compile(r"(?i)(?:ch|chap|chapter|unit|mod|module)[_\-\s]*(\d+(?:\.\d+)*)")

_VISION_MODEL_HINTS = ("llava", "vision", "vl", "minicpm-v", "moondream", "bakllava", "gemma3", "pixtral")


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
    confidence_reason: str = ""
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


def _preprocess_pil_for_ocr(img: Image.Image, upscale_min_width: int = 1000, max_dim: int = 2000) -> Image.Image:
    """Enhance grayscale contrast, reduce noise, sharpen, and normalize resolution for OCR."""
    work = img.convert("L")
    work = ImageOps.autocontrast(work, cutoff=1)
    work = ImageEnhance.Contrast(work).enhance(1.6)
    work = work.filter(ImageFilter.MedianFilter(size=3))
    work = work.filter(ImageFilter.SHARPEN)
    w, h = work.size
    if w < upscale_min_width:
        scale = min(2.5, upscale_min_width / max(1, w))
        work = work.resize((int(w * scale), int(h * scale)), Image.Resampling.LANCZOS)
    elif max(w, h) > max_dim:
        work.thumbnail((max_dim, max_dim), Image.Resampling.LANCZOS)
    return work


def _invoke_ocr_on_file(target_path: Path, engine: str) -> str:
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


def run_local_ocr_on_image(image_path: Path, max_dim: int = 2000) -> str:
    """Run local offline OCR on header, footer, and full image with preprocessing."""
    engine = detect_ocr_engine()
    if engine == "none":
        return ""

    try:
        with tempfile.TemporaryDirectory(prefix="pdfstudio_ocr_") as tmp_dir:
            tmp = Path(tmp_dir)
            with Image.open(image_path) as raw:
                img = ImageOps.exif_transpose(raw).convert("RGB")
                w, h = img.size

                # 1. Targeted header crop (top 18%) and footer crop (bottom 16%)
                header_crop = _preprocess_pil_for_ocr(img.crop((0, 0, w, max(60, int(h * 0.18)))), upscale_min_width=1400)
                footer_crop = _preprocess_pil_for_ocr(img.crop((0, max(0, int(h * 0.84)), w, h)), upscale_min_width=1400)

                hdr_path = tmp / "hdr.png"
                ftr_path = tmp / "ftr.png"
                header_crop.save(hdr_path, format="PNG")
                footer_crop.save(ftr_path, format="PNG")

                hdr_text = _invoke_ocr_on_file(hdr_path, engine)
                ftr_text = _invoke_ocr_on_file(ftr_path, engine)

                # 2. Full preprocessed image if header+footer did not already yield both markers
                full_text = ""
                combined_edge = f"{hdr_text}\n{ftr_text}"
                if not (_PAGE_EXPLICIT_RE.search(combined_edge) and _CHAPTER_WORD_RE.search(combined_edge)):
                    full_prep = _preprocess_pil_for_ocr(img, upscale_min_width=1000, max_dim=max_dim)
                    full_path = tmp / "full.png"
                    full_prep.save(full_path, format="PNG")
                    full_text = _invoke_ocr_on_file(full_path, engine)

                parts = [p for p in (hdr_text, ftr_text, full_text) if p]
                return "\n".join(parts)
    except (subprocess.TimeoutExpired, OSError, Exception):
        return ""


def _is_vision_model_compatible(base_url: str, model_name: str) -> bool:
    """Verify via Ollama /api/show or known vision model families that the model accepts images."""
    if not base_url or not model_name:
        return False
    try:
        with httpx.Client(timeout=3.0) as client:
            resp = client.post(f"{base_url.rstrip('/')}/api/show", json={"name": model_name})
            if resp.status_code == 200:
                data = resp.json()
                caps = [str(c).lower() for c in data.get("capabilities", [])]
                if "vision" in caps:
                    return True
                fam = str(data.get("details", {}).get("family", "")).lower()
                if any(h in fam for h in _VISION_MODEL_HINTS):
                    return True
    except Exception:
        return False
    return any(h in model_name.lower() for h in _VISION_MODEL_HINTS)


def try_vision_fallback(image_path: Path) -> dict[str, Any] | None:
    """Optional local Ollama vision fallback for ambiguous/low-confidence image pages."""
    settings = get_settings()
    if not settings.VISION_FALLBACK_ENABLED or not settings.OLLAMA_BASE_URL or not settings.OLLAMA_VISION_MODEL:
        return None
    if not _is_vision_model_compatible(settings.OLLAMA_BASE_URL, settings.OLLAMA_VISION_MODEL):
        return None

    try:
        with Image.open(image_path) as raw:
            img = ImageOps.exif_transpose(raw).convert("RGB")
            img.thumbnail((1400, 1400), Image.Resampling.LANCZOS)
            buf = BytesIO()
            img.save(buf, format="PNG")
            b64_img = base64.b64encode(buf.getvalue()).decode("ascii")

        prompt = (
            "Read the header/footer of this page image and return ONLY JSON with keys: "
            '{"page_number": int|null, "total_pages": int|null, "chapter_number": str|null, '
            '"confidence": float, "evidence": str}. Do not guess if unreadable.'
        )
        with httpx.Client(timeout=20.0) as client:
            resp = client.post(
                f"{settings.OLLAMA_BASE_URL.rstrip('/')}/api/generate",
                json={
                    "model": settings.OLLAMA_VISION_MODEL,
                    "prompt": prompt,
                    "images": [b64_img],
                    "format": "json",
                    "stream": False,
                },
            )
            resp.raise_for_status()
            parsed = json.loads(resp.json().get("response", "{}"))
            if not isinstance(parsed, dict):
                return None
            return {
                "page_number": int(parsed["page_number"]) if parsed.get("page_number") is not None else None,
                "total_pages": int(parsed["total_pages"]) if parsed.get("total_pages") is not None else None,
                "chapter_number": str(parsed["chapter_number"]).strip() if parsed.get("chapter_number") else None,
                "confidence": min(0.95, max(0.0, float(parsed.get("confidence", 0.7)))),
                "evidence": str(parsed.get("evidence", ""))[:150],
            }
    except Exception:
        return None


def _extract_text_from_file(file_path: Path) -> tuple[str, str, int | None]:
    """Return (extracted_text, detection_method, physical_page_count)."""
    ext = file_path.suffix.lower()
    try:
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
    except Exception:
        return "", "filename", None

    return "", "filename", None


def extract_sequence_metadata(
    file_path: Path,
    original_index: int,
    relative_path: str,
) -> SequenceAnalysisItem:
    """Analyze a single file's content (plus optional vision fallback & filename fallback)."""
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
    reasons: list[str] = []

    # 1. Chapter / Section / Heading detection (supports inline pipe-separated headers)
    for ln in lines[:25]:
        m_chap = _CHAPTER_WORD_RE.search(ln)
        if m_chap:
            detected_chapter = m_chap.group(1)
            chapter_key = parse_chapter_sort_key(detected_chapter)
            raw_title = (m_chap.group(2) or "").strip()
            extracted_heading = (raw_title or f"Chapter {detected_chapter}").strip()[:120]
            evidence_parts.append(m_chap.group(0).strip(" |,-"))
            confidence = max(confidence, 0.90 if method == "embedded_text" else 0.85)
            break
        m_app = _APPENDIX_RE.search(ln)
        if m_app:
            detected_chapter = f"Appendix {m_app.group(1).upper()}"
            chapter_key = parse_chapter_sort_key(detected_chapter)
            raw_title = (m_app.group(2) or "").strip()
            extracted_heading = (raw_title or detected_chapter).strip()[:120]
            evidence_parts.append(m_app.group(0).strip(" |,-"))
            confidence = max(confidence, 0.88)
            break
        if not _FALSE_POSITIVE_LINE_RE.search(ln):
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

    # 2. Explicit Page Number detection (highest priority: Page: 2, Pg. 1, Page 1 of 10)
    for ln in lines:
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
                confidence = max(confidence, 0.95 if method == "embedded_text" else 0.90)
                break

    if detected_page is None:
        edge_lines = lines[:3] + (lines[-3:] if len(lines) > 3 else [])
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
        edge_lines = lines[:3] + (lines[-3:] if len(lines) > 3 else [])
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

    # 3. Optional local vision fallback for ambiguous image pages (< 0.55 confidence)
    if file_path.suffix.lower() in IMAGE_EXTENSIONS and confidence < 0.55:
        vis = try_vision_fallback(file_path)
        if vis:
            method = "vision_ocr"
            if detected_page is None and vis.get("page_number") is not None:
                detected_page = vis["page_number"]
                detected_page_display = str(detected_page)
            if total_pages is None and vis.get("total_pages") is not None:
                total_pages = vis["total_pages"]
            if detected_chapter is None and vis.get("chapter_number"):
                detected_chapter = vis["chapter_number"]
                chapter_key = parse_chapter_sort_key(detected_chapter)
            confidence = max(confidence, float(vis.get("confidence", 0.75)))
            if vis.get("evidence"):
                evidence_parts.append(f"vision:{vis['evidence']}")

    # 4. Filename fallback ONLY when content/OCR yielded nothing
    stem = file_path.stem
    if detected_chapter is None:
        m_fc = _FILENAME_CHAP_RE.search(stem)
        if m_fc:
            detected_chapter = m_fc.group(1)
            chapter_key = parse_chapter_sort_key(detected_chapter)
            method = "filename" if method != "embedded_text" else method
            confidence = max(confidence, 0.45)
            evidence_parts.append(f"filename:{m_fc.group(0)}")
            reasons.append("Inferred chapter from filename only")

    if detected_page is None:
        m_fp = _FILENAME_PAGE_RE.search(stem)
        if m_fp:
            detected_page = int(m_fp.group(1))
            detected_page_display = str(detected_page)
            method = "filename" if method != "embedded_text" else method
            confidence = max(confidence, 0.45)
            evidence_parts.append(f"filename:{m_fp.group(0)}")
            reasons.append("Inferred page from filename only")

    if detected_page is None and detected_chapter is None:
        confidence_label = "Not detected"
        status = "Not detected"
        if not evidence_parts:
            evidence_parts.append("No sequence markers detected")
        reasons.append("No printed page or chapter marker detected in content or filename")
    elif confidence >= 0.80:
        confidence_label = "High"
        status = "Detected"
        reasons.append("Explicit marker extracted from content")
    elif confidence >= 0.55:
        confidence_label = "Medium"
        status = "Review"
        reasons.append("Marker extracted from edge/standalone text; verify before compiling")
    else:
        confidence_label = "Low"
        status = "Review"
        if not reasons:
            reasons.append("Low-confidence detection; manual review recommended")

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
        evidence_text=" | ".join(evidence_parts)[:220],
        confidence_reason="; ".join(reasons),
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
    """Sort analyzed items according to priority and detect duplicates/missing pages."""
    effective_mode = _choose_effective_mode(items, sort_mode)

    if effective_mode in ("Original Upload Order", "Manual Ordering"):
        ordered = sorted(items, key=lambda it: it.original_index)
    elif effective_mode == "Sort by Page Number":
        ordered = sorted(
            items,
            key=lambda it: (
                0 if it.detected_page is not None else 1,
                it.detected_page if it.detected_page is not None else 999999,
                0 if it.chapter_sort_key is not None else 1,
                it.chapter_sort_key if it.chapter_sort_key is not None else [999999],
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
    else:  # Chapter then Page Number (or Automatic Detection with chapters & pages)
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
