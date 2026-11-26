"""Professional Learning Book Publisher: 10-stage workflow with cover designer, clickable TOC, bookmarks, dividers, and compression."""
from datetime import date
import httpx
import streamlit as st

from frontend.api_client import api_post, api_upload_file, get_api_base_url
from frontend.components.ui import (
    format_bytes,
    render_generated_pdf_result,
    render_smart_sequence_section,
    show_api_error,
)

st.caption("Publish structured technical manuals and learning books with cover designer, clickable TOC, nested bookmarks, dividers, and optimization.")

# Initialize persistent workflow state
DEFAULTS = {
    "pub_title": "Enterprise Engineering Handbook",
    "pub_subtitle": "Architecture Patterns & Learning Notes",
    "pub_author": "PDF Studio Engineering Team",
    "pub_org": "Engineering",
    "pub_date": date.today(),
    "pub_version": "1.0",
    "pub_classification": "Internal",
    "pub_template": "Corporate Technical Manual",
    "pub_orientation": "portrait",
    "pub_include_toc": True,
    "pub_toc_title": "Table of Contents",
    "pub_header_text": "",
    "pub_footer_text": "",
    "pub_page_num_style": "Page 1 of N",
    "pub_roman_prelim": True,
    "pub_hf_align": "right",
    "pub_skip_first_hf": False,
    "pub_include_dividers": False,
    "pub_divider_style": "Classic Banner",
    "pub_count_dividers": True,
    "pub_compression": "Original Quality",
    "pub_meta_subject": "",
    "pub_meta_keywords": "",
    "pub_out_name": "learning_book.pdf",
    "pub_logo_rel_path": None,
}
for k, v in DEFAULTS.items():
    if k not in st.session_state:
        st.session_state[k] = v

STAGES = [
    "1. Cover",
    "2. Upload",
    "3. Sequence",
    "4. Chapters",
    "5. TOC & Bookmarks",
    "6. Headers & Numbers",
    "7. Dividers",
    "8. Compression",
    "9. Preview",
    "10. Publish",
]
active_stage = st.segmented_control("Publication workflow stage", options=STAGES, default=STAGES[0])

# Stage 2 uploader kept accessible in session_state
if active_stage == "1. Cover":
    c1, c2 = st.columns([3, 2])
    with c1:
        with st.container(border=True):
            st.subheader("Stage 1: Book details & cover")
            st.text_input("Book title", key="pub_title")
            st.text_input("Subtitle", key="pub_subtitle")
            st.text_input("Author / Prepared by", key="pub_author")
            st.text_input("Organization / Team", key="pub_org")
            sc1, sc2, sc3 = st.columns(3)
            sc1.date_input("Publication date", key="pub_date")
            sc2.text_input("Version", key="pub_version")
            sc3.text_input("Classification (optional)", key="pub_classification")
            tc1, tc2 = st.columns(2)
            tc1.selectbox(
                "Cover design template",
                ["Corporate Technical Manual", "Cisco Learning Guide", "Training Workbook", "Minimal Professional"],
                key="pub_template",
            )
            tc2.segmented_control("Orientation", options=["portrait", "landscape"], key="pub_orientation")
            logo_file = st.file_uploader("Optional cover logo (PNG/JPG)", type=["png", "jpg", "jpeg"], key="pub_logo_up")
            if logo_file is not None:
                res_logo = api_upload_file(logo_file.name, logo_file.getvalue(), logo_file.type or "image/png")
                st.session_state.pub_logo_rel_path = res_logo["relative_path"]
    with c2:
        with st.container(border=True):
            st.subheader("Live cover preview")
            try:
                username = st.session_state.get("active_username", "engineer1")
                with httpx.Client(timeout=15.0) as client:
                    resp = client.post(
                        f"{get_api_base_url()}/api/pdf/learning-book/preview-cover",
                        headers={"X-Username": username},
                        json={
                            "title": st.session_state.pub_title,
                            "subtitle": st.session_state.pub_subtitle,
                            "author": st.session_state.pub_author,
                            "organization": st.session_state.pub_org,
                            "date_str": st.session_state.pub_date.isoformat(),
                            "version": st.session_state.pub_version,
                            "classification": st.session_state.pub_classification,
                            "template_name": st.session_state.pub_template,
                            "page_orientation": st.session_state.pub_orientation or "portrait",
                            "logo_path": st.session_state.pub_logo_rel_path,
                            "sections": [],
                        },
                    )
                    resp.raise_for_status()
                    st.image(resp.content, alt="Live cover page preview", width="stretch")
            except Exception as exc:
                show_api_error(exc)

elif active_stage == "2. Upload":
    with st.container(border=True):
        st.subheader("Stage 2: Upload documents and images")
        uploaded = st.file_uploader(
            "Upload sketchnotes, diagrams, Office/Markdown documents, or PDFs",
            type=["png", "jpg", "jpeg", "bmp", "tiff", "webp", "docx", "txt", "md", "pptx", "xlsx", "pdf"],
            accept_multiple_files=True,
            key="pub_files_uploader",
        )
        if uploaded:
            st.session_state["pub_uploaded_files"] = uploaded
            st.success(f"{len(uploaded)} file(s) staged ({format_bytes(sum(f.size for f in uploaded))}).", title="Ready for sequencing")

elif active_stage == "3. Sequence":
    files = st.session_state.get("pub_uploaded_files")
    if not files:
        st.info("Upload files in **Stage 2** first.")
    else:
        ordered = render_smart_sequence_section(files, state_prefix="book")
        st.session_state["pub_ordered_items"] = ordered

elif active_stage == "4. Chapters":
    items = st.session_state.get("pub_ordered_items")
    if not items:
        st.info("Run **Stage 3 (Smart Sequence Detection)** first.")
    else:
        with st.container(border=True):
            st.subheader("Stage 4: Chapter & section arrangement")
            for idx, it in enumerate(items):
                c1, c2, c3 = st.columns([1, 3, 1])
                it["detected_chapter"] = c1.text_input(
                    f"Chapter # ({idx+1})", value=it.get("detected_chapter") or str(idx + 1), key=f"ch_num_{idx}"
                )
                it["extracted_heading"] = c2.text_input(
                    f"Heading ({it['filename']})", value=it.get("extracted_heading") or it["filename"], key=f"ch_hd_{idx}"
                )
                it["level"] = int(c3.selectbox("Level", [1, 2], index=0 if it.get("level", 1) == 1 else 1, key=f"ch_lvl_{idx}"))

elif active_stage == "5. TOC & Bookmarks":
    with st.container(border=True):
        st.subheader("Stage 5: Table of Contents & PDF Bookmarks")
        st.checkbox("Include clickable Table of Contents", key="pub_include_toc")
        st.text_input("TOC title", key="pub_toc_title")
        st.text_input("Metadata subject", key="pub_meta_subject")
        st.text_input("Metadata keywords", key="pub_meta_keywords")

elif active_stage == "6. Headers & Numbers":
    with st.container(border=True):
        st.subheader("Stage 6: Headers, footers & page numbering")
        st.text_input("Header text (blank = book title)", key="pub_header_text")
        st.text_input("Footer text", key="pub_footer_text")
        c1, c2, c3 = st.columns(3)
        c1.selectbox("Page number style", ["Page 1 of N", "1, 2, 3", "None"], key="pub_page_num_style")
        c2.segmented_control("Alignment", options=["left", "center", "right"], key="pub_hf_align")
        c3.checkbox("Roman numerals on TOC (i, ii, iii)", key="pub_roman_prelim")
        st.checkbox("Skip header/footer on first chapter page", key="pub_skip_first_hf")

elif active_stage == "7. Dividers":
    with st.container(border=True):
        st.subheader("Stage 7: Chapter divider pages")
        st.checkbox("Insert chapter divider pages", key="pub_include_dividers")
        st.selectbox("Divider style", ["Classic Banner", "Minimal Left Accent"], key="pub_divider_style")
        st.checkbox("Count divider pages in page numbering", key="pub_count_dividers")

elif active_stage == "8. Compression":
    with st.container(border=True):
        st.subheader("Stage 8: PDF Optimization & Compression")
        mode = st.selectbox(
            "Compression mode",
            ["Original Quality", "High Quality", "Balanced", "Small File Size"],
            key="pub_compression",
        )
        if mode == "Small File Size":
            st.warning("Small File Size downsamples images to 100 DPI; verify fine handwritten notes.", title="Readability notice")

elif active_stage == "9. Preview":
    items = st.session_state.get("pub_ordered_items") or []
    files = st.session_state.get("pub_uploaded_files") or []
    with st.container(border=True):
        st.subheader("Stage 9: Publication summary")
        total_src_bytes = sum(f.size for f in files)
        chapters = sum(1 for it in items if it.get("level", 1) == 1)
        sections = sum(1 for it in items if it.get("level", 1) == 2)
        with st.grid(3, gap="medium"):
            st.metric("Source size", format_bytes(total_src_bytes), border=True)
            st.metric("Chapters / Sections", f"{chapters} / {sections}", border=True)
            st.metric("Compression", st.session_state.pub_compression, border=True)
        st.caption(f"Template: **{st.session_state.pub_template}** | Orientation: **{st.session_state.pub_orientation}**")

elif active_stage == "10. Publish":
    items = st.session_state.get("pub_ordered_items")
    if not items:
        st.info("Upload and sequence files in Stages 2–3 before publishing.")
    else:
        st.text_input("Output PDF filename", key="pub_out_name")
        if st.button("Publish Learning Book PDF", type="primary", icon=":material/menu_book:", width="stretch"):
            try:
                payload_sections = [
                    {
                        "heading": it.get("extracted_heading") or it["filename"],
                        "path": it["relative_path"],
                        "chapter_number": it.get("detected_chapter"),
                        "chapter_title": it.get("extracted_heading"),
                        "level": it.get("level", 1),
                    }
                    for it in items
                ]
                with st.spinner("Building cover, clickable TOC, bookmarks, headers, and optimizing PDF..."):
                    res = api_post(
                        "/api/pdf/learning-book",
                        {
                            "title": st.session_state.pub_title,
                            "subtitle": st.session_state.pub_subtitle,
                            "author": st.session_state.pub_author,
                            "organization": st.session_state.pub_org,
                            "date_str": st.session_state.pub_date.isoformat(),
                            "version": st.session_state.pub_version,
                            "classification": st.session_state.pub_classification,
                            "template_name": st.session_state.pub_template,
                            "page_orientation": st.session_state.pub_orientation or "portrait",
                            "logo_path": st.session_state.pub_logo_rel_path,
                            "include_toc": st.session_state.pub_include_toc,
                            "toc_title": st.session_state.pub_toc_title,
                            "include_dividers": st.session_state.pub_include_dividers,
                            "divider_style": st.session_state.pub_divider_style,
                            "count_dividers_in_numbering": st.session_state.pub_count_dividers,
                            "header_text": st.session_state.pub_header_text,
                            "footer_text": st.session_state.pub_footer_text,
                            "page_number_style": st.session_state.pub_page_num_style,
                            "roman_preliminary": st.session_state.pub_roman_prelim,
                            "hf_alignment": st.session_state.pub_hf_align or "right",
                            "skip_first_chapter_hf": st.session_state.pub_skip_first_hf,
                            "meta_subject": st.session_state.pub_meta_subject,
                            "meta_keywords": st.session_state.pub_meta_keywords,
                            "compression_mode": st.session_state.pub_compression,
                            "sections": payload_sections,
                            "output_filename": st.session_state.pub_out_name,
                        },
                    )
                if res.get("readability_warning"):
                    st.warning(res["readability_warning"], title="Compression notice")
                render_generated_pdf_result(res, label="Download Learning Book")
            except Exception as exc:
                show_api_error(exc)
