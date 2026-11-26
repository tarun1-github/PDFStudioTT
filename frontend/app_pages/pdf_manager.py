"""PDF Manager: merge, split, extract, rotate, compress, number, watermark, bookmarks, metadata."""
import streamlit as st

from frontend.api_client import api_post
from frontend.components.ui import (
    render_generated_pdf_result,
    show_api_error,
    upload_many_to_backend,
)

st.caption("Perform precision operations on existing PDF documents with automatic output validation.")

operation = st.selectbox(
    "Select PDF operation",
    [
        "merge",
        "split",
        "extract",
        "rotate",
        "compress",
        "page_numbers",
        "header_footer",
        "watermark",
        "bookmarks",
        "metadata",
    ],
    format_func=lambda x: x.replace("_", " ").title(),
)

allow_multi = operation == "merge"
uploaded = st.file_uploader(
    "Upload PDF file(s)",
    type=["pdf"],
    accept_multiple_files=allow_multi,
)

if uploaded:
    files_list = uploaded if isinstance(uploaded, list) else [uploaded]
    params: dict = {}
    output_filename = f"{operation}_output.pdf"

    with st.container(border=True):
        if operation == "merge":
            params["add_bookmarks"] = st.checkbox("Add bookmark per merged file", value=True)
        elif operation == "split":
            c1, c2 = st.columns(2)
            params["start_page"] = int(c1.number_input("Start page", min_value=1, value=1))
            params["end_page"] = int(c2.number_input("End page", min_value=1, value=1))
        elif operation == "extract":
            raw_pages = st.text_input("Pages to extract (comma-separated, e.g. 1,3,5)", value="1")
            params["pages"] = [int(p.strip()) for p in raw_pages.split(",") if p.strip().isdigit()]
        elif operation == "rotate":
            c1, c2 = st.columns(2)
            params["angle"] = int(c1.selectbox("Rotation angle", [90, 180, 270]))
            raw_pages = c2.text_input("Pages to rotate (blank = all pages)", value="")
            params["pages"] = [int(p.strip()) for p in raw_pages.split(",") if p.strip().isdigit()] or None
        elif operation == "page_numbers":
            params["position"] = st.segmented_control(
                "Position", options=["bottom-right", "bottom-center"], default="bottom-right"
            )
        elif operation == "header_footer":
            params["header_text"] = st.text_input("Header text", value="PDF Studio – Confidential")
            params["footer_text"] = st.text_input("Footer text", value="Internal Engineering Document")
        elif operation == "watermark":
            params["text"] = st.text_input("Watermark text", value="CONFIDENTIAL")
        elif operation == "bookmarks":
            raw_bm = st.text_area("Bookmarks (one per line: `Title, Page`)", value="Introduction, 1")
            bms = []
            for line in raw_bm.splitlines():
                if "," in line:
                    t, p = line.rsplit(",", 1)
                    if p.strip().isdigit():
                        bms.append({"title": t.strip(), "page": int(p.strip())})
            params["bookmarks"] = bms
        elif operation == "metadata":
            c1, c2 = st.columns(2)
            params["title"] = c1.text_input("Title", value="")
            params["author"] = c2.text_input("Author", value="")
            params["subject"] = c1.text_input("Subject", value="")
            params["keywords"] = c2.text_input("Keywords", value="")

        output_filename = st.text_input("Output filename", value=output_filename)

        if st.button("Execute operation", type="primary", icon=":material/build:", width="stretch"):
            try:
                saved = upload_many_to_backend(files_list)
                body: dict = {
                    "operation": operation,
                    "output_filename": output_filename,
                    "params": params,
                }
                if operation == "merge":
                    body["input_paths"] = [s["relative_path"] for s in saved]
                else:
                    body["input_path"] = saved[0]["relative_path"]

                with st.spinner(f"Running {operation}..."):
                    res = api_post("/api/pdf/manage", body)
                render_generated_pdf_result(res)
            except Exception as exc:
                show_api_error(exc)
