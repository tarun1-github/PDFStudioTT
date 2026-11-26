"""Image-to-PDF conversion preserving aspect ratio, orientation, and quality."""
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageOps
from pypdf import PdfReader
from reportlab.lib.pagesizes import A3, A4, LETTER, landscape, portrait
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

PAGE_SIZES = {
    "A4": A4,
    "A3": A3,
    "LETTER": LETTER,
}


def verify_pdf_file(pdf_path: Path) -> int:
    """Verify a PDF exists, is non-empty, and can be opened by pypdf. Returns page count."""
    if not pdf_path.exists() or pdf_path.stat().st_size == 0:
        raise ValueError(f"Generated PDF is missing or empty: {pdf_path}")
    reader = PdfReader(str(pdf_path))
    if len(reader.pages) < 1:
        raise ValueError("Generated PDF contains zero pages.")
    return len(reader.pages)


def _resolve_page_size(
    page_size: str,
    orientation: str,
    img_width: int,
    img_height: int,
) -> tuple[float, float]:
    key = page_size.strip().upper()
    if key == "ORIGINAL":
        # Convert pixels to points (72 pt/in at 96 dpi)
        w_pt = img_width * 72.0 / 96.0
        h_pt = img_height * 72.0 / 96.0
        if orientation.lower() == "landscape" and h_pt > w_pt:
            return (h_pt, w_pt)
        if orientation.lower() == "portrait" and w_pt > h_pt:
            return (h_pt, w_pt)
        return (w_pt, h_pt)

    base = PAGE_SIZES.get(key, A4)
    orient = orientation.strip().lower()
    if orient == "auto":
        return landscape(base) if img_width > img_height else portrait(base)
    if orient == "landscape":
        return landscape(base)
    return portrait(base)


def images_to_pdf(
    image_paths: list[Path],
    output_path: Path,
    page_size: str = "A4",
    orientation: str = "auto",
    margin_mm: float = 10.0,
) -> dict[str, int | str]:
    """Convert one or more images into a high-quality PDF without stretching."""
    if not image_paths:
        raise ValueError("At least one image is required.")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    margin_pt = max(0.0, margin_mm) * mm if page_size.strip().upper() != "ORIGINAL" else 0.0

    c = canvas.Canvas(str(output_path))
    c.setTitle(output_path.stem)

    for img_path in image_paths:
        with Image.open(img_path) as raw_img:
            img = ImageOps.exif_transpose(raw_img)
            if img.mode in ("RGBA", "LA", "P"):
                bg = Image.new("RGB", img.size, (255, 255, 255))
                if img.mode == "P":
                    img = img.convert("RGBA")
                bg.paste(img, mask=img.split()[-1] if img.mode in ("RGBA", "LA") else None)
                img = bg
            elif img.mode != "RGB":
                img = img.convert("RGB")

            img_w, img_h = img.size
            page_w, page_h = _resolve_page_size(page_size, orientation, img_w, img_h)
            c.setPageSize((page_w, page_h))

            avail_w = max(10.0, page_w - 2 * margin_pt)
            avail_h = max(10.0, page_h - 2 * margin_pt)
            scale = min(avail_w / img_w, avail_h / img_h)
            draw_w = img_w * scale
            draw_h = img_h * scale
            x = (page_w - draw_w) / 2.0
            y = (page_h - draw_h) / 2.0

            buf = BytesIO()
            img.save(buf, format="PNG", optimize=True)
            buf.seek(0)
            c.drawImage(
                ImageReader(buf),
                x,
                y,
                width=draw_w,
                height=draw_h,
                preserveAspectRatio=True,
                mask="auto",
            )
            c.showPage()

    c.save()
    page_count = verify_pdf_file(output_path)
    return {
        "output_path": str(output_path),
        "page_count": page_count,
        "file_size_bytes": output_path.stat().st_size,
    }
