"""Multi-format PDF Compiler with Smart Sequence Detection."""
import streamlit as st

from frontend.api_client import api_post
from frontend.components.ui import (
    render_generated_pdf_result,
    render_smart_sequence_section,
    show_api_error,
)

st.caption("Combine PNG/JPG images, DOCX/TXT/MD/XLSX/PPTX documents, and existing PDFs into one ordered PDF.")

uploaded = st.file_uploader(
    "Upload files to compile",
    type=["png", "jpg", "jpeg", "bmp", "tiff", "webp", "docx", "txt", "md", "html", "xlsx", "pptx", "pdf"],
    accept_multiple_files=True,
)

if uploaded:
    try:
        ordered_items = render_smart_sequence_section(uploaded, state_prefix="compiler")
    except Exception as exc:
        show_api_error(exc)
        st.stop()

    with st.container(border=True):
        st.subheader("Output configuration")
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            page_size = st.selectbox("Page size", ["A4", "A3", "Letter"])
        with c2:
            orientation = st.segmented_control(
                "Orientation",
                options=["auto", "portrait", "landscape"],
                default="auto",
            )
        with c3:
            margin_mm = st.number_input("Margin (mm)", min_value=0.0, max_value=50.0, value=10.0)
        with c4:
            output_filename = st.text_input("Output filename", value="compiled_document.pdf")

        if st.button("Compile PDF", type="primary", icon=":material/layers:", width="stretch"):
            try:
                payload_items = [
                    {
                        "path": it["relative_path"],
                        "section_title": it.get("extracted_heading") or it["filename"],
                    }
                    for it in ordered_items
                ]
                with st.spinner("Compiling mixed formats into unified PDF..."):
                    res = api_post(
                        "/api/pdf/compile",
                        {
                            "items": payload_items,
                            "page_size": page_size,
                            "orientation": orientation or "auto",
                            "margin_mm": margin_mm,
                            "output_filename": output_filename,
                        },
                    )
                render_generated_pdf_result(res)
            except Exception as exc:
                show_api_error(exc)
