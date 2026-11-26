"""PDF Optimization & Compression Engine preserving searchable text, bookmarks, links, and metadata."""
import shutil
from io import BytesIO
from pathlib import Path
from typing import Any

import pymupdf
from PIL import Image

from backend.services.image_pdf_service import verify_pdf_file

COMPRESSION_PROFILES: dict[str, dict[str, Any]] = {
    "Original Quality": {"dpi": None, "quality": None, "warning": None},
    "High Quality": {"dpi": 200, "quality": 88, "warning": None},
    "Balanced": {"dpi": 150, "quality": 75, "warning": None},
    "Small File Size": {
        "dpi": 100,
        "quality": 55,
        "warning": "Small File Size mode downsamples images to 100 DPI; verify fine handwritten notes or dense diagrams.",
    },
}


def optimize_pdf(
    input_path: Path,
    output_path: Path,
    mode: str = "Original Quality",
) -> dict[str, Any]:
    """Optimize a PDF into a separate output file while preserving text, bookmarks, links, and metadata."""
    if not input_path.exists():
        raise FileNotFoundError(f"Source PDF not found: {input_path}")
    profile = COMPRESSION_PROFILES.get(mode, COMPRESSION_PROFILES["Original Quality"])
    output_path.parent.mkdir(parents=True, exist_ok=True)
    orig_size = input_path.stat().st_size

    if mode == "Original Quality":
        shutil.copy2(input_path, output_path)
        pages = verify_pdf_file(output_path)
        return {
            "output_path": str(output_path),
            "mode": mode,
            "original_size_bytes": orig_size,
            "optimized_size_bytes": output_path.stat().st_size,
            "reduction_pct": 0.0,
            "page_count": pages,
            "already_optimized": False,
            "readability_warning": None,
        }

    target_dpi = int(profile["dpi"])
    jpeg_quality = int(profile["quality"])

    doc = pymupdf.open(str(input_path))
    try:
        processed_xrefs: set[int] = set()
        for page in doc:
            for img_info in page.get_images(full=True):
                xref = img_info[0]
                if xref in processed_xrefs:
                    continue
                processed_xrefs.add(xref)
                try:
                    base_img = doc.extract_image(xref)
                    raw_bytes = base_img.get("image")
                    if not raw_bytes:
                        continue
                    with Image.open(BytesIO(raw_bytes)) as pil_img:
                        w, h = pil_img.size
                        # Scale relative to ~200 DPI baseline to avoid upscaling small images
                        max_px = int((target_dpi / 72.0) * 842)
                        if max(w, h) > max_px:
                            pil_img.thumbnail((max_px, max_px), Image.Resampling.LANCZOS)
                        if pil_img.mode in ("RGBA", "LA", "P"):
                            bg = Image.new("RGB", pil_img.size, (255, 255, 255))
                            if pil_img.mode == "P":
                                pil_img = pil_img.convert("RGBA")
                            bg.paste(pil_img, mask=pil_img.split()[-1] if pil_img.mode in ("RGBA", "LA") else None)
                            pil_img = bg
                        elif pil_img.mode != "RGB":
                            pil_img = pil_img.convert("RGB")
                        out_buf = BytesIO()
                        pil_img.save(out_buf, format="JPEG", quality=jpeg_quality, optimize=True)
                        new_bytes = out_buf.getvalue()
                        if len(new_bytes) < len(raw_bytes):
                            page.replace_image(xref, stream=new_bytes)
                except Exception:
                    continue

        doc.save(str(output_path), garbage=4, deflate=True, clean=True)
    finally:
        doc.close()

    opt_size = output_path.stat().st_size
    already_optimized = opt_size >= orig_size
    if already_optimized and mode != "Original Quality":
        shutil.copy2(input_path, output_path)
        opt_size = output_path.stat().st_size

    reduction = round(((orig_size - opt_size) / orig_size) * 100.0, 2) if orig_size > 0 else 0.0
    pages = verify_pdf_file(output_path)
    return {
        "output_path": str(output_path),
        "mode": mode,
        "original_size_bytes": orig_size,
        "optimized_size_bytes": opt_size,
        "reduction_pct": max(0.0, reduction),
        "page_count": pages,
        "already_optimized": already_optimized,
        "readability_warning": profile["warning"],
    }
