"""Professional Learning Book Publisher: cover designer, clickable TOC, nested bookmarks, dividers, Roman/chapter numbering, and compression."""
import tempfile
from dataclasses import dataclass, field
from io import BytesIO
from pathlib import Path
from typing import Any

import pymupdf
from PIL import Image, ImageOps
from pypdf import PdfReader
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape, portrait
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

from backend.security.storage import DOCUMENT_EXTENSIONS, IMAGE_EXTENSIONS, PDF_EXTENSIONS
from backend.services.document_pdf_service import convert_document_to_pdf
from backend.services.image_pdf_service import verify_pdf_file
from backend.services.pdf_optimization_service import optimize_pdf

TEMPLATES = {
    "Corporate Technical Manual": {
        "accent": colors.HexColor("#0F172A"),
        "primary": colors.HexColor("#2563EB"),
        "bg": colors.HexColor("#F8FAFC"),
        "text": colors.HexColor("#0F172A"),
        "muted": colors.HexColor("#475569"),
    },
    "Cisco Learning Guide": {
        "accent": colors.HexColor("#032D60"),
        "primary": colors.HexColor("#00BCEB"),
        "bg": colors.HexColor("#F0F9FF"),
        "text": colors.HexColor("#0F172A"),
        "muted": colors.HexColor("#0369A1"),
    },
    "Training Workbook": {
        "accent": colors.HexColor("#1E293B"),
        "primary": colors.HexColor("#059669"),
        "bg": colors.HexColor("#F0FDF4"),
        "text": colors.HexColor("#0F172A"),
        "muted": colors.HexColor("#047857"),
    },
    "Minimal Professional": {
        "accent": colors.HexColor("#18181B"),
        "primary": colors.HexColor("#52525B"),
        "bg": colors.HexColor("#FFFFFF"),
        "text": colors.HexColor("#18181B"),
        "muted": colors.HexColor("#71717A"),
    },
    # Legacy aliases preserved for backward compatibility
    "AI Learning Notes": {
        "accent": colors.HexColor("#1E1B4B"),
        "primary": colors.HexColor("#3B82F6"),
        "bg": colors.HexColor("#EEF2FF"),
        "text": colors.HexColor("#1E293B"),
        "muted": colors.HexColor("#4338CA"),
    },
    "Sketchnote Collection": {
        "accent": colors.HexColor("#0B3B5B"),
        "primary": colors.HexColor("#0284C7"),
        "bg": colors.HexColor("#F0F9FF"),
        "text": colors.HexColor("#0F172A"),
        "muted": colors.HexColor("#0369A1"),
    },
}


def _int_to_roman(n: int) -> str:
    vals = [(100, "c"), (90, "xc"), (50, "l"), (40, "xl"), (10, "x"), (9, "ix"), (5, "v"), (4, "iv"), (1, "i")]
    res = []
    for v, sym in vals:
        while n >= v:
            res.append(sym)
            n -= v
    return "".join(res)


@dataclass
class LearningSection:
    heading: str
    file_path: Path
    chapter_number: str | None = None
    chapter_title: str | None = None
    subtitle: str = ""
    overview: str = ""
    level: int = 1  # 1 = Chapter, 2 = Nested Section


@dataclass
class LearningBookConfig:
    title: str
    subtitle: str = ""
    author: str = ""
    organization: str = ""
    date_str: str = ""
    version: str = "1.0"
    classification: str = ""
    template_name: str = "Corporate Technical Manual"
    page_orientation: str = "portrait"  # "portrait" or "landscape"
    logo_path: Path | None = None

    # TOC & Bookmarks
    include_toc: bool = True
    toc_title: str = "Table of Contents"

    # Dividers
    include_dividers: bool = False
    divider_style: str = "Classic Banner"
    count_dividers_in_numbering: bool = True

    # Headers, Footers & Page Numbering
    header_text: str = ""
    footer_text: str = ""
    page_number_style: str = "Page 1 of N"  # "None", "1, 2, 3", "Page 1 of N"
    roman_preliminary: bool = True
    hf_alignment: str = "right"  # "left", "center", "right"
    skip_first_chapter_hf: bool = False

    # Metadata
    meta_subject: str = ""
    meta_keywords: str = ""
    meta_creator: str = "PDF Studio Professional Publisher"
    meta_producer: str = "PDF Studio"

    # Compression
    compression_mode: str = "Original Quality"


def _cover_pagesize(orientation: str) -> tuple[float, float]:
    return landscape(A4) if orientation.lower() == "landscape" else portrait(A4)


def _draw_cover_page(output_pdf: Path, cfg: LearningBookConfig) -> None:
    theme = TEMPLATES.get(cfg.template_name, TEMPLATES["Corporate Technical Manual"])
    sz = _cover_pagesize(cfg.page_orientation)
    w, h = sz
    c = canvas.Canvas(str(output_pdf), pagesize=sz)
    c.setFillColor(theme["bg"])
    c.rect(0, 0, w, h, fill=1, stroke=0)

    # Top brand header
    c.setFillColor(theme["accent"])
    c.rect(0, h - 28 * mm, w, 28 * mm, fill=1, stroke=0)
    c.setFillColor(theme["primary"])
    c.rect(0, h - 31 * mm, w, 3 * mm, fill=1, stroke=0)

    c.setFillColor(colors.white)
    c.setFont("Helvetica-Bold", 11)
    org_prefix = f"{cfg.organization.upper()}  |  " if cfg.organization else ""
    c.drawString(20 * mm, h - 18 * mm, f"{org_prefix}{cfg.template_name.upper()}")

    # Optional Logo (aspect-ratio preserved)
    if cfg.logo_path and cfg.logo_path.exists():
        with Image.open(cfg.logo_path) as raw_logo:
            logo = ImageOps.exif_transpose(raw_logo)
            if logo.mode not in ("RGB", "RGBA"):
                logo = logo.convert("RGBA")
            lw, lh = logo.size
            max_w, max_h = 36 * mm, 20 * mm
            sc = min(max_w / lw, max_h / lh)
            dw, dh = lw * sc, lh * sc
            buf = BytesIO()
            logo.save(buf, format="PNG")
            buf.seek(0)
            c.drawImage(
                ImageReader(buf),
                w - 20 * mm - dw,
                h - 24 * mm,
                width=dw,
                height=dh,
                preserveAspectRatio=True,
                mask="auto",
            )

    # Title & Subtitle
    c.setFillColor(theme["text"])
    c.setFont("Helvetica-Bold", 26)
    c.drawString(20 * mm, h - 76 * mm, cfg.title[:65])

    if cfg.subtitle:
        c.setFillColor(theme["muted"])
        c.setFont("Helvetica", 14)
        c.drawString(20 * mm, h - 89 * mm, cfg.subtitle[:90])

    c.setStrokeColor(theme["primary"])
    c.setLineWidth(2)
    c.line(20 * mm, h - 98 * mm, w - 20 * mm, h - 98 * mm)

    # Metadata block
    y_meta = 52 * mm
    c.setFillColor(theme["text"])
    c.setFont("Helvetica-Bold", 11)
    c.drawString(20 * mm, y_meta, f"Prepared by: {cfg.author or 'PDF Studio Team'}")
    c.setFont("Helvetica", 10.5)
    c.drawString(20 * mm, y_meta - 8 * mm, f"Date: {cfg.date_str or 'N/A'}    |    Version: {cfg.version or '1.0'}")
    if cfg.classification:
        c.setFillColor(theme["primary"])
        c.setFont("Helvetica-Bold", 10)
        c.drawString(20 * mm, y_meta - 16 * mm, f"Classification: {cfg.classification}")

    c.setFillColor(theme["muted"])
    c.setFont("Helvetica", 8.5)
    c.drawString(20 * mm, 16 * mm, "Generated by PDF Studio – Professional Learning Book Publisher")
    c.showPage()
    c.save()


def render_cover_preview_png(cfg: LearningBookConfig) -> bytes:
    """Render a PNG preview of the cover page for live UI preview."""
    with tempfile.TemporaryDirectory(prefix="pdfstudio_cov_") as tmp:
        cov_pdf = Path(tmp) / "cover.pdf"
        _draw_cover_page(cov_pdf, cfg)
        doc = pymupdf.open(str(cov_pdf))
        try:
            pix = doc[0].get_pixmap(dpi=120)
            return pix.tobytes("png")
        finally:
            doc.close()


def _draw_divider_page(output_pdf: Path, sec: LearningSection, cfg: LearningBookConfig) -> None:
    theme = TEMPLATES.get(cfg.template_name, TEMPLATES["Corporate Technical Manual"])
    sz = _cover_pagesize(cfg.page_orientation)
    w, h = sz
    c = canvas.Canvas(str(output_pdf), pagesize=sz)
    c.setFillColor(theme["bg"])
    c.rect(0, 0, w, h, fill=1, stroke=0)

    if cfg.divider_style == "Minimal Left Accent":
        c.setFillColor(theme["primary"])
        c.rect(14 * mm, h * 0.35, 3 * mm, h * 0.35, fill=1, stroke=0)
    else:
        c.setFillColor(theme["accent"])
        c.rect(0, h * 0.52, w, 34 * mm, fill=1, stroke=0)

    chap_label = f"CHAPTER {sec.chapter_number}" if sec.chapter_number else "SECTION"
    c.setFillColor(colors.white if cfg.divider_style != "Minimal Left Accent" else theme["primary"])
    c.setFont("Helvetica-Bold", 13)
    c.drawString(24 * mm, h * 0.52 + 20 * mm, chap_label)

    c.setFillColor(colors.white if cfg.divider_style != "Minimal Left Accent" else theme["text"])
    c.setFont("Helvetica-Bold", 22)
    c.drawString(24 * mm, h * 0.52 + 8 * mm, (sec.chapter_title or sec.heading)[:60])

    if sec.subtitle:
        c.setFillColor(theme["muted"])
        c.setFont("Helvetica", 13)
        c.drawString(24 * mm, h * 0.42, sec.subtitle[:85])
    if sec.overview:
        c.setFillColor(theme["text"])
        c.setFont("Helvetica", 10.5)
        c.drawString(24 * mm, h * 0.35, sec.overview[:100])

    c.showPage()
    c.save()


def _draw_toc_page(
    output_pdf: Path,
    entries: list[dict[str, Any]],
    cfg: LearningBookConfig,
) -> list[tuple[int, pymupdf.Rect, int]]:
    """Render TOC page(s) and return clickable link specs: (toc_page_idx, rect, target_0idx)."""
    theme = TEMPLATES.get(cfg.template_name, TEMPLATES["Corporate Technical Manual"])
    sz = _cover_pagesize(cfg.page_orientation)
    w, h = sz
    c = canvas.Canvas(str(output_pdf), pagesize=sz)

    def _draw_header():
        c.setFillColor(theme["accent"])
        c.setFont("Helvetica-Bold", 20)
        c.drawString(20 * mm, h - 26 * mm, cfg.toc_title or "Table of Contents")
        c.setStrokeColor(theme["primary"])
        c.setLineWidth(1.5)
        c.line(20 * mm, h - 30 * mm, w - 20 * mm, h - 30 * mm)

    _draw_header()
    y = h - 44 * mm
    toc_page_idx = 0
    links: list[tuple[int, pymupdf.Rect, int]] = []

    for ent in entries:
        if y < 24 * mm:
            c.showPage()
            toc_page_idx += 1
            _draw_header()
            y = h - 44 * mm

        indent = 22 * mm if ent["level"] == 1 else 30 * mm
        c.setFont("Helvetica-Bold" if ent["level"] == 1 else "Helvetica", 11 if ent["level"] == 1 else 10)
        c.setFillColor(theme["text"])
        c.drawString(indent, y, ent["title"][:72])
        c.setFillColor(theme["muted"])
        c.drawRightString(w - 20 * mm, y, str(ent["display_page"]))

        # ReportLab origin is bottom-left; PyMuPDF Rect is top-left
        top_y = h - (y + 11)
        bot_y = h - (y - 3)
        links.append((toc_page_idx, pymupdf.Rect(indent, top_y, w - 20 * mm, bot_y), ent["dest_0idx"]))
        y -= 8.5 * mm

    c.showPage()
    c.save()
    return links


def _render_section_image_pdf(image_path: Path, output_pdf: Path) -> None:
    with Image.open(image_path) as raw_img:
        img = ImageOps.exif_transpose(raw_img)
        if img.mode != "RGB":
            img = img.convert("RGB")
        iw, ih = img.size
        page_sz = landscape(A4) if iw > ih else portrait(A4)
        pw, ph = page_sz
        margin = 12 * mm
        avail_w = pw - 2 * margin
        avail_h = ph - 2 * margin - 12 * mm
        scale = min(avail_w / iw, avail_h / ih)
        dw, dh = iw * scale, ih * scale
        x = (pw - dw) / 2.0
        y = (ph - dh) / 2.0

        c = canvas.Canvas(str(output_pdf), pagesize=page_sz)
        buf = BytesIO()
        img.save(buf, format="PNG", optimize=True)
        buf.seek(0)
        c.drawImage(ImageReader(buf), x, y, width=dw, height=dh, preserveAspectRatio=True)
        c.showPage()
        c.save()


def publish_learning_book(
    cfg: LearningBookConfig,
    sections: list[LearningSection],
    output_path: Path,
) -> dict[str, Any]:
    """Assemble and optionally optimize a complete Professional Learning Book PDF."""
    if not sections:
        raise ValueError("At least one section or document is required.")

    output_path.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="pdfstudio_pub_") as tmp_dir:
        tmp = Path(tmp_dir)
        cover_pdf = tmp / "00_cover.pdf"
        _draw_cover_page(cover_pdf, cfg)

        # Render all content & optional divider PDFs first
        rendered_parts: list[dict[str, Any]] = []
        for idx, sec in enumerate(sections, start=1):
            div_pdf: Path | None = None
            if cfg.include_dividers and sec.level == 1:
                div_pdf = tmp / f"div_{idx}.pdf"
                _draw_divider_page(div_pdf, sec, cfg)

            ext = sec.file_path.suffix.lower()
            sec_pdf = tmp / f"sec_{idx}.pdf"
            if ext in IMAGE_EXTENSIONS:
                _render_section_image_pdf(sec.file_path, sec_pdf)
            elif ext in DOCUMENT_EXTENSIONS:
                convert_document_to_pdf(sec.file_path, sec_pdf)
            elif ext in PDF_EXTENSIONS:
                verify_pdf_file(sec.file_path)
                sec_pdf = sec.file_path
            else:
                raise ValueError(f"Unsupported section file type: {ext}")

            sec_pages = len(PdfReader(str(sec_pdf)).pages)
            rendered_parts.append(
                {
                    "sec": sec,
                    "div_pdf": div_pdf,
                    "sec_pdf": sec_pdf,
                    "sec_pages": sec_pages,
                    "div_pages": 1 if div_pdf else 0,
                }
            )

        # Estimate TOC page count (up to ~24 entries per page)
        toc_page_count = max(1, (len(rendered_parts) + 23) // 24) if cfg.include_toc else 0
        main_start_0idx = 1 + toc_page_count

        # Build TOC entries & hierarchical bookmarks
        toc_entries: list[dict[str, Any]] = []
        bookmarks: list[list[Any]] = [[1, "Cover", 1]]
        if cfg.include_toc:
            bookmarks.append([1, cfg.toc_title or "Table of Contents", 2])

        cursor_0idx = main_start_0idx
        printed_page_num = 1
        page_roles: dict[int, dict[str, Any]] = {}  # 0idx -> {"kind": "cover"|"toc"|"divider"|"content", "label": str, "chap": str}

        page_roles[0] = {"kind": "cover", "label": "", "chap": ""}
        for t_i in range(toc_page_count):
            roman_lbl = _int_to_roman(t_i + 1) if cfg.roman_preliminary else str(t_i + 1)
            page_roles[1 + t_i] = {"kind": "toc", "label": roman_lbl, "chap": cfg.toc_title}

        for part in rendered_parts:
            sec: LearningSection = part["sec"]
            chapter_start_0idx = cursor_0idx
            chapter_start_printed = printed_page_num
            if part["div_pdf"]:
                div_idx = cursor_0idx
                if cfg.count_dividers_in_numbering:
                    page_roles[div_idx] = {"kind": "divider", "label": str(printed_page_num), "chap": sec.heading}
                    printed_page_num += 1
                else:
                    page_roles[div_idx] = {"kind": "divider", "label": "", "chap": sec.heading}
                cursor_0idx += 1

            dest_0idx = chapter_start_0idx if part["div_pdf"] else cursor_0idx
            disp_num = chapter_start_printed if (part["div_pdf"] and cfg.count_dividers_in_numbering) else printed_page_num
            toc_entries.append(
                {
                    "title": sec.heading,
                    "level": 1 if sec.level <= 1 else 2,
                    "display_page": disp_num,
                    "dest_0idx": dest_0idx,
                }
            )
            bm_level = 1 if sec.level <= 1 else 2
            # Ensure valid parent level (cannot start level 2 without prior level 1)
            if bm_level == 2 and not any(b[0] == 1 and b[2] >= 2 for b in bookmarks[1:]):
                bm_level = 1
            entry = [bm_level, sec.heading, dest_0idx + 1]
            if entry not in bookmarks:
                bookmarks.append(entry)

            for p_off in range(part["sec_pages"]):
                page_roles[cursor_0idx + p_off] = {
                    "kind": "content",
                    "label": str(printed_page_num),
                    "chap": sec.heading,
                }
                printed_page_num += 1
            cursor_0idx += part["sec_pages"]

        total_main_pages = printed_page_num - 1

        # Assemble final document in PyMuPDF for clickable links, headers/footers, bookmarks, metadata
        assembled = pymupdf.open()
        cov_doc = pymupdf.open(str(cover_pdf))
        assembled.insert_pdf(cov_doc)
        cov_doc.close()

        toc_links: list[tuple[int, pymupdf.Rect, int]] = []
        if cfg.include_toc:
            toc_pdf = tmp / "01_toc.pdf"
            toc_links = _draw_toc_page(toc_pdf, toc_entries, cfg)
            toc_doc = pymupdf.open(str(toc_pdf))
            assembled.insert_pdf(toc_doc)
            toc_doc.close()

        for part in rendered_parts:
            if part["div_pdf"]:
                d_doc = pymupdf.open(str(part["div_pdf"]))
                assembled.insert_pdf(d_doc)
                d_doc.close()
            s_doc = pymupdf.open(str(part["sec_pdf"]))
            assembled.insert_pdf(s_doc)
            s_doc.close()

        # Insert clickable TOC links
        for toc_pg, rect, dest_0idx in toc_links:
            if 1 + toc_pg < len(assembled) and dest_0idx < len(assembled):
                assembled[1 + toc_pg].insert_link(
                    {"kind": pymupdf.LINK_GOTO, "from": rect, "page": dest_0idx}
                )

        # Stamp headers, footers & page numbers
        for p_idx in range(len(assembled)):
            info = page_roles.get(p_idx, {"kind": "content", "label": "", "chap": ""})
            if info["kind"] == "cover":
                continue
            if cfg.skip_first_chapter_hf and p_idx == main_start_0idx:
                continue

            pg = assembled[p_idx]
            rect = pg.rect
            pw, ph = rect.width, rect.height

            hdr_parts = [p for p in [cfg.header_text or cfg.title, info["chap"] if info["kind"] == "content" else "", cfg.organization] if p]
            hdr_line = "  |  ".join(hdr_parts)[:95]
            if hdr_line:
                pg.insert_text((36, 22), hdr_line, fontsize=8, color=(0.35, 0.42, 0.52))

            num_lbl = ""
            if info["label"] and cfg.page_number_style != "None":
                if info["kind"] == "toc" or cfg.page_number_style == "1, 2, 3":
                    num_lbl = info["label"]
                else:
                    num_lbl = f"Page {info['label']} of {total_main_pages}"

            ftr_left = "  |  ".join([p for p in [cfg.footer_text, f"v{cfg.version}" if cfg.version else "", cfg.classification] if p])[:75]
            if ftr_left:
                pg.insert_text((36, ph - 18), ftr_left, fontsize=8, color=(0.35, 0.42, 0.52))
            if num_lbl:
                if cfg.hf_alignment == "left":
                    x_pos = 36
                elif cfg.hf_alignment == "center":
                    x_pos = max(36, pw / 2 - len(num_lbl) * 2.2)
                else:
                    x_pos = max(36, pw - 36 - len(num_lbl) * 4.5)
                pg.insert_text((x_pos, ph - 18), num_lbl, fontsize=8.5, color=(0.25, 0.32, 0.42))

        assembled.set_toc(bookmarks)
        assembled.set_metadata(
            {
                "title": cfg.title,
                "author": cfg.author,
                "subject": cfg.meta_subject or cfg.subtitle,
                "keywords": cfg.meta_keywords,
                "creator": cfg.meta_creator,
                "producer": cfg.meta_producer,
            }
        )

        uncompressed_pdf = tmp / "assembled_uncompressed.pdf"
        assembled.save(str(uncompressed_pdf), garbage=3, deflate=True)
        assembled.close()

        opt_res = optimize_pdf(uncompressed_pdf, output_path, mode=cfg.compression_mode)

    return {
        "output_path": str(output_path),
        "page_count": opt_res["page_count"],
        "file_size_bytes": opt_res["optimized_size_bytes"],
        "original_size_bytes": opt_res["original_size_bytes"],
        "reduction_pct": opt_res["reduction_pct"],
        "compression_mode": cfg.compression_mode,
        "readability_warning": opt_res["readability_warning"],
        "toc_entries": len(toc_entries),
        "bookmarks_count": len(bookmarks),
    }


def create_learning_book(
    output_path: Path,
    title: str,
    subtitle: str,
    author: str,
    date_str: str,
    template_name: str,
    sections: list[LearningSection],
) -> dict[str, int | str]:
    """Backward-compatible wrapper around publish_learning_book."""
    cfg = LearningBookConfig(
        title=title,
        subtitle=subtitle,
        author=author,
        date_str=date_str,
        template_name=template_name,
    )
    return publish_learning_book(cfg, sections, output_path)
