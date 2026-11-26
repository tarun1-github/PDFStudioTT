"""Document-to-PDF conversion tests (TXT, MD, DOCX, XLSX, PPTX)."""
from pathlib import Path
import pytest
from docx import Document
from openpyxl import Workbook
from pptx import Presentation
from pypdf import PdfReader

from backend.services.document_pdf_service import convert_document_to_pdf, detect_libreoffice


def test_txt_and_md_to_pdf(tmp_path: Path):
    txt = tmp_path / "notes.txt"
    txt.write_text("Hello PDF Studio\nLine 2", encoding="utf-8")
    out_txt = tmp_path / "notes.pdf"
    res = convert_document_to_pdf(txt, out_txt)
    assert res["page_count"] >= 1
    assert len(PdfReader(str(out_txt)).pages) >= 1

    md = tmp_path / "readme.md"
    md.write_text("# Heading\n\n- Item A\n- Item B\n", encoding="utf-8")
    out_md = tmp_path / "readme.pdf"
    res_md = convert_document_to_pdf(md, out_md)
    assert res_md["page_count"] >= 1


@pytest.mark.skipif(detect_libreoffice() is None, reason="LibreOffice (soffice.exe) not installed on host")
def test_office_documents_to_pdf_via_libreoffice(tmp_path: Path):
    docx_path = tmp_path / "sample.docx"
    doc = Document()
    doc.add_heading("PDF Studio Test", level=1)
    doc.add_paragraph("Automated DOCX to PDF verification.")
    doc.save(docx_path)
    res_docx = convert_document_to_pdf(docx_path, tmp_path / "sample_docx.pdf")
    assert res_docx["page_count"] >= 1

    xlsx_path = tmp_path / "sample.xlsx"
    wb = Workbook()
    ws = wb.active
    ws["A1"] = "Metric"
    ws["B1"] = 42
    wb.save(xlsx_path)
    res_xlsx = convert_document_to_pdf(xlsx_path, tmp_path / "sample_xlsx.pdf")
    assert res_xlsx["page_count"] >= 1

    pptx_path = tmp_path / "sample.pptx"
    prs = Presentation()
    slide = prs.slides.add_slide(prs.slide_layouts[0])
    slide.shapes.title.text = "PDF Studio Slide"
    prs.save(pptx_path)
    res_pptx = convert_document_to_pdf(pptx_path, tmp_path / "sample_pptx.pdf")
    assert res_pptx["page_count"] >= 1

    html_path = tmp_path / "sample.html"
    html_path.write_text("<html><body><h1>PDF Studio HTML</h1><p>Verified output.</p></body></html>", encoding="utf-8")
    res_html = convert_document_to_pdf(html_path, tmp_path / "sample_html.pdf")
    assert res_html["page_count"] >= 1
