"""Document to PDF converter supporting DOCX, TXT, MD, HTML, XLSX, and PPTX."""
from pathlib import Path
import streamlit as st

from frontend.api_client import api_get, api_post
from frontend.components.ui import (
    render_generated_pdf_result,
    show_api_error,
    upload_many_to_backend,
)

st.caption("Convert Office, Markdown, HTML, and text documents into verified PDFs.")

try:
    deps = api_get("/health/dependencies")
    if not deps.get("libreoffice_installed"):
        st.warning(
            "LibreOffice (`soffice.exe`) is not detected on this server. "
            "`TXT` and `MD` conversions work natively; `DOCX`, `XLSX`, `PPTX`, and `HTML` require LibreOffice.",
            title="LibreOffice not installed",
        )
except Exception:
    pass

uploaded = st.file_uploader(
    "Upload document",
    type=["docx", "txt", "md", "html", "htm", "xlsx", "pptx"],
    accept_multiple_files=False,
)

if uploaded:
    default_out = f"{Path(uploaded.name).stem}.pdf"
    output_filename = st.text_input("Output PDF filename", value=default_out)
    if st.button("Convert to PDF", type="primary", icon=":material/picture_as_pdf:", width="stretch"):
        try:
            saved = upload_many_to_backend([uploaded])
            with st.spinner("Converting document and verifying PDF output..."):
                res = api_post(
                    "/api/pdf/document-to-pdf",
                    {
                        "input_path": saved[0]["relative_path"],
                        "output_filename": output_filename,
                    },
                )
            render_generated_pdf_result(res)
        except Exception as exc:
            show_api_error(exc)
