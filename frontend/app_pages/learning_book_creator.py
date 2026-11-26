"""Flagship Learning Book Creator with chapter-aware Smart Sequence Detection."""
from datetime import date
import streamlit as st

from frontend.api_client import api_post
from frontend.components.ui import (
    render_generated_pdf_result,
    render_smart_sequence_section,
    show_api_error,
)

st.caption("Publish professional learning manuals and sketchnote collections with cover, TOC, headers, footers, and bookmarks.")

with st.container(border=True):
    st.subheader("Book metadata & template")
    c1, c2 = st.columns(2)
    with c1:
        title = st.text_input("Book title", value="Enterprise Engineering Handbook")
        subtitle = st.text_input("Subtitle", value="Architecture Patterns & Sketchnote Reference")
        template_name = st.selectbox(
            "Book template",
            ["Corporate Technical Manual", "AI Learning Notes", "Sketchnote Collection"],
        )
    with c2:
        author = st.text_input("Author", value="PDF Studio Engineering Team")
        pub_date = st.date_input("Publication date", value=date.today())
        output_filename = st.text_input("Output filename", value="learning_book.pdf")

uploaded = st.file_uploader(
    "Upload sketchnotes, diagrams, documents, or PDF chapters",
    type=["png", "jpg", "jpeg", "bmp", "tiff", "webp", "docx", "txt", "md", "pdf"],
    accept_multiple_files=True,
)

if uploaded:
    try:
        ordered_items = render_smart_sequence_section(uploaded, state_prefix="book")
    except Exception as exc:
        show_api_error(exc)
        st.stop()

    if st.button("Build Learning Book PDF", type="primary", icon=":material/menu_book:", width="stretch"):
        try:
            payload_sections = []
            for it in ordered_items:
                chap = it.get("detected_chapter")
                heading = it.get("extracted_heading") or it["filename"]
                if chap and not heading.lower().startswith(("chapter", "unit", "module", "appendix", str(chap).lower())):
                    heading = f"Chapter {chap} – {heading}"
                payload_sections.append({"heading": heading, "path": it["relative_path"]})

            with st.spinner("Generating cover, Table of Contents, bookmarks, and numbered chapters..."):
                res = api_post(
                    "/api/pdf/learning-book",
                    {
                        "title": title,
                        "subtitle": subtitle,
                        "author": author,
                        "date_str": pub_date.isoformat(),
                        "template_name": template_name,
                        "sections": payload_sections,
                        "output_filename": output_filename,
                    },
                )
            render_generated_pdf_result(res, label="Download Learning Book")
        except Exception as exc:
            show_api_error(exc)
