"""Non-destructive PDF version comparison service (text, page count, metadata, image count)."""
import difflib
from pathlib import Path
from typing import Any

import pymupdf


def compare_pdf_versions(old_pdf: Path, new_pdf: Path) -> dict[str, Any]:
    """Compare two PDF versions without modifying either source file."""
    if not old_pdf.exists() or not new_pdf.exists():
        raise FileNotFoundError("Both version files must exist for comparison.")

    doc_old = pymupdf.open(str(old_pdf))
    doc_new = pymupdf.open(str(new_pdf))
    try:
        old_pages = len(doc_old)
        new_pages = len(doc_new)
        old_text_lines: list[str] = []
        new_text_lines: list[str] = []
        old_images = 0
        new_images = 0

        for idx, p in enumerate(doc_old):
            old_images += len(p.get_images(full=False))
            for ln in p.get_text("text").splitlines():
                if ln.strip():
                    old_text_lines.append(f"[p{idx+1}] {ln.strip()}")

        for idx, p in enumerate(doc_new):
            new_images += len(p.get_images(full=False))
            for ln in p.get_text("text").splitlines():
                if ln.strip():
                    new_text_lines.append(f"[p{idx+1}] {ln.strip()}")

        diff = list(difflib.ndiff(old_text_lines, new_text_lines))
        added = [d[2:] for d in diff if d.startswith("+ ")][:100]
        removed = [d[2:] for d in diff if d.startswith("- ")][:100]

        meta_old = doc_old.metadata or {}
        meta_new = doc_new.metadata or {}
        meta_changes = {}
        for k in ("title", "author", "subject", "keywords"):
            if (meta_old.get(k) or "") != (meta_new.get(k) or ""):
                meta_changes[k] = {"old": meta_old.get(k) or "", "new": meta_new.get(k) or ""}

        return {
            "page_count_old": old_pages,
            "page_count_new": new_pages,
            "page_count_delta": new_pages - old_pages,
            "image_count_old": old_images,
            "image_count_new": new_images,
            "image_count_delta": new_images - old_images,
            "added_lines": added,
            "removed_lines": removed,
            "added_count": sum(1 for d in diff if d.startswith("+ ")),
            "removed_count": sum(1 for d in diff if d.startswith("- ")),
            "metadata_changes": meta_changes,
            "summary": (
                f"Pages: {old_pages} -> {new_pages} ({new_pages - old_pages:+d}); "
                f"Text lines +{sum(1 for d in diff if d.startswith('+ '))} / "
                f"-{sum(1 for d in diff if d.startswith('- '))}; "
                f"Images: {old_images} -> {new_images}."
            ),
        }
    finally:
        doc_old.close()
        doc_new.close()
