"""Image-to-PDF conversion tests."""
from pathlib import Path
from PIL import Image
from pypdf import PdfReader

from backend.services.image_pdf_service import images_to_pdf


def _make_image(path: Path, size: tuple[int, int], color: tuple[int, int, int], fmt: str) -> Path:
    img = Image.new("RGB", size, color=color)
    img.save(path, format=fmt)
    return path


def test_png_and_jpg_to_pdf_and_orientations(tmp_path: Path):
    png_portrait = _make_image(tmp_path / "p.png", (600, 1000), (30, 80, 180), "PNG")
    jpg_landscape = _make_image(tmp_path / "l.jpg", (1200, 700), (180, 50, 40), "JPEG")

    out_multi = tmp_path / "multi.pdf"
    res = images_to_pdf([png_portrait, jpg_landscape], out_multi, page_size="A4", orientation="auto")
    assert res["page_count"] == 2

    reader = PdfReader(str(out_multi))
    p1 = reader.pages[0].mediabox
    p2 = reader.pages[1].mediabox
    assert float(p1.height) > float(p1.width)  # portrait
    assert float(p2.width) > float(p2.height)  # landscape


def test_explicit_portrait_and_landscape(tmp_path: Path):
    img = _make_image(tmp_path / "sq.png", (500, 500), (10, 120, 90), "PNG")

    out_p = tmp_path / "portrait.pdf"
    images_to_pdf([img], out_p, page_size="Letter", orientation="portrait")
    mb_p = PdfReader(str(out_p)).pages[0].mediabox
    assert float(mb_p.height) > float(mb_p.width)

    out_l = tmp_path / "landscape.pdf"
    images_to_pdf([img], out_l, page_size="A3", orientation="landscape")
    mb_l = PdfReader(str(out_l)).pages[0].mediabox
    assert float(mb_l.width) > float(mb_l.height)
