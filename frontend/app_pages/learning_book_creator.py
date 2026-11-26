"""Flagship Learning Book Creator: cover page, TOC, templates, bookmarks, and sketchnotes."""
from datetime import date
from pathlib import Path
import streamlit as st

from frontend.api_client import api_post
from frontend.components.ui import (
    render_generated_pdf_result,
    show_api_error,
    upload_many_to_backend,
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
    if "book_sections" not in st.session_state or len(st.session_state.book_sections) != len(uploaded):
        st.session_state.book_sections = [
            {"idx": i, "heading": Path(uf.name).stem.replace("_", " ").title()}
            for i, uf in enumerate(uploaded)
        ]

    with st.container(border=True):
        st.subheader("Chapters & section headings")
        sections = st.session_state.book_sections
        for pos, sec in enumerate(sections):
            uf = uploaded[sec["idx"]]
            c1, c2, c3 = st.columns([4, 1, 1], vertical_alignment="bottom")
            with c1:
                sec["heading"] = st.text_input(
                    f"Chapter {pos + 1} ({uf.name})",
                    value=sec["heading"],
                    key=f"book_sec_{pos}_{sec['idx']}",
                )
            with c2:
                if pos > 0 and st.button("Up", key=f"book_up_{pos}", icon=":material/arrow_upward:", width="stretch"):
                    sections[pos - 1], sections[pos] = sections[pos], sections[pos - 1]
                    st.rerun()
            with c3:
                if pos < len(sections) - 1 and st.button("Down", key=f"book_dn_{pos}", icon=":material/arrow_downward:", width="stretch"):
                    sections[pos + 1], sections[pos] = sections[pos], sections[pos + 1]
                    st.rerun()

    if st.button("Build Learning Book PDF", type="primary", icon=":material/menu_book:", width="stretch"):
        try:
            ordered_files = [uploaded[s["idx"]] for s in st.session_state.book_sections]
            saved = upload_many_to_backend(ordered_files)
            payload_sections = [
                {"heading": sec["heading"], "path": s["relative_path"]}
                for sec, s in zip(st.session_state.book_sections, saved)
            ]
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
