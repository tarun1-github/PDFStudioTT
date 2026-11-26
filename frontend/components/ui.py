"""Reusable SaaS-style UI components for PDF Studio."""
import importlib.util

import httpx
import pandas as pd
import streamlit as st

from frontend.api_client import api_download_bytes, api_post, api_upload_file

SMART_SORT_MODES = [
    "Automatic Detection",
    "Original Upload Order",
    "Sort by Page Number",
    "Sort by Chapter Number",
    "Chapter then Page Number",
    "Manual Ordering",
]


def is_pdf_preview_available() -> bool:
    """Return True if the streamlit-pdf viewer package is installed in the active venv."""
    return importlib.util.find_spec("streamlit_pdf") is not None


def format_bytes(num_bytes: int) -> str:
    if num_bytes < 1024:
        return f"{num_bytes} B"
    if num_bytes < 1024 ** 2:
        return f"{num_bytes / 1024:.1f} KB"
    if num_bytes < 1024 ** 3:
        return f"{num_bytes / (1024 ** 2):.2f} MB"
    return f"{num_bytes / (1024 ** 3):.2f} GB"


def show_api_error(exc: Exception) -> None:
    if isinstance(exc, httpx.HTTPStatusError):
        try:
            detail = exc.response.json().get("detail", exc.response.text)
        except Exception:
            detail = exc.response.text
        st.error(f"{detail}", title=f"Request failed ({exc.response.status_code})")
    elif isinstance(exc, httpx.ConnectError):
        st.error(
            "Cannot reach the FastAPI backend. Start it with `scripts/start_api.ps1`.",
            title="Backend offline",
        )
    else:
        st.error(str(exc), title="Operation failed")


def upload_many_to_backend(uploaded_files) -> list[dict]:
    """Upload Streamlit UploadedFile objects to the backend and return metadata dicts."""
    results = []
    progress = st.progress(0, text="Uploading files to isolated user storage...")
    total = len(uploaded_files)
    for idx, uf in enumerate(uploaded_files, start=1):
        res = api_upload_file(uf.name, uf.getvalue(), uf.type or "application/octet-stream")
        results.append(res)
        progress.progress(idx / total, text=f"Uploaded {idx}/{total}: {uf.name}")
    progress.empty()
    return results


def render_generated_pdf_result(result: dict, label: str = "Download generated PDF") -> None:
    """Display generated PDF metadata, inline preview, and download button."""
    doc_uuid = result["doc_uuid"]
    filename = result["filename"]
    pages = result.get("page_count", 0)
    size_str = format_bytes(int(result.get("file_size_bytes", 0)))

    st.success(
        f"Generated **{filename}** ({pages} pages, {size_str}).",
        title="PDF ready",
    )
    pdf_bytes = api_download_bytes(f"/api/files/documents/{doc_uuid}/download")
    col1, _col2 = st.columns([1, 3])
    with col1:
        st.download_button(
            label=label,
            data=pdf_bytes,
            file_name=filename,
            mime="application/pdf",
            icon=":material/download:",
            type="primary",
            width="stretch",
        )
    with st.expander("Preview generated PDF", expanded=True):
        if is_pdf_preview_available():
            st.pdf(pdf_bytes, alt=f"Preview of {filename}")
        else:
            st.warning(
                "Inline PDF preview requires `streamlit-pdf`. Install it in `.venv` with "
                "`pip install \"streamlit[pdf]\"`. You can still download the PDF above.",
                title="PDF preview component unavailable",
            )


def render_smart_sequence_section(uploaded_files, state_prefix: str) -> list[dict]:
    """Reusable Smart Sequence Detection UI returning ordered item dicts with heading & path."""
    sig = tuple((uf.name, uf.size) for uf in uploaded_files)
    cache_key = f"{state_prefix}_seq_cache"
    sig_key = f"{state_prefix}_seq_sig"
    mode_cache_key = f"{state_prefix}_seq_mode_used"

    with st.container(border=True):
        st.subheader("Smart Sequence Detection")
        c1, c2, c3 = st.columns([2, 2, 1], vertical_alignment="bottom")
        with c1:
            auto_enabled = st.toggle("Enable automatic sequencing", value=True, key=f"{state_prefix}_auto_seq")
        with c2:
            sort_mode = st.selectbox(
                "Sorting mode",
                options=SMART_SORT_MODES,
                index=0 if auto_enabled else 1,
                key=f"{state_prefix}_sort_mode",
            )
        with c3:
            reanalyze = st.button("Re-analyse", icon=":material/refresh:", key=f"{state_prefix}_reanalyze", width="stretch")

        effective_req_mode = sort_mode if auto_enabled else "Original Upload Order"
        if (
            st.session_state.get(sig_key) != sig
            or st.session_state.get(mode_cache_key) != effective_req_mode
            or reanalyze
            or cache_key not in st.session_state
        ):
            saved = upload_many_to_backend(uploaded_files)
            analysis = api_post(
                "/api/pdf/analyze-sequence",
                {
                    "input_paths": [s["relative_path"] for s in saved],
                    "sort_mode": effective_req_mode,
                },
            )
            st.session_state[cache_key] = analysis
            st.session_state[sig_key] = sig
            st.session_state[mode_cache_key] = effective_req_mode

        analysis = st.session_state[cache_key]
        items = analysis["items"]

        st.caption(
            f"Resolved mode: **{analysis.get('resolved_mode')}** | "
            f"OCR engine: `{analysis.get('ocr_engine', 'none')}`"
        )
        for dup in analysis.get("duplicates", []):
            st.warning(dup, title="Duplicate page detected")
        for miss in analysis.get("missing_pages", []):
            st.warning(miss, title="Missing sequence number")

        df = pd.DataFrame(
            [
                {
                    "Proposed order": it["proposed_order"],
                    "Filename": it["filename"],
                    "Detected chapter": it.get("detected_chapter") or "",
                    "Detected page": it.get("detected_page_display") or "",
                    "Extracted heading/title": it.get("extracted_heading") or it["filename"],
                    "Detection method": it["detection_method"],
                    "Confidence": f"{int(it['confidence'] * 100)}% ({it['confidence_label']})",
                    "Status": it["status"],
                    "Evidence": it.get("evidence_text") or "",
                }
                for it in items
            ]
        )
        edited = st.data_editor(
            df,
            width="stretch",
            hide_index=True,
            disabled=["Filename", "Detection method", "Confidence", "Status", "Evidence"],
            key=f"{state_prefix}_seq_editor",
            alt="Smart sequence detection table",
        )

        # Apply manual table edits (order, chapter, page, heading)
        for idx, row in edited.iterrows():
            raw_order = row["Proposed order"]
            items[idx]["proposed_order"] = int(raw_order) if pd.notna(raw_order) else (idx + 1)
            items[idx]["detected_chapter"] = str(row["Detected chapter"]).strip() or None
            raw_pg = str(row["Detected page"]).strip()
            items[idx]["detected_page_display"] = raw_pg or None
            if raw_pg.isdigit():
                items[idx]["detected_page"] = int(raw_pg)
            items[idx]["extracted_heading"] = str(row["Extracted heading/title"]).strip() or items[idx]["filename"]
        items.sort(key=lambda x: (x["proposed_order"], x["original_index"]))
        for pos, it in enumerate(items, start=1):
            it["proposed_order"] = pos

        b1, b2, _b3 = st.columns([1, 1, 2])
        with b1:
            if st.button("Restore original order", key=f"{state_prefix}_restore_orig", width="stretch"):
                items.sort(key=lambda x: x["original_index"])
                for pos, it in enumerate(items, start=1):
                    it["proposed_order"] = pos
                st.rerun()
        with b2:
            if st.button("Accept suggested sequence", key=f"{state_prefix}_accept_seq", type="secondary", width="stretch"):
                st.toast("Sequence accepted.")

        with st.expander("Inspect original image & OCR evidence", expanded=False):
            file_map = {uf.name: uf for uf in uploaded_files}
            item_labels = [f"{it['proposed_order']}. {it['filename']} ({it['status']})" for it in items]
            chosen_lbl = st.selectbox("Select file to inspect", options=item_labels, key=f"{state_prefix}_inspect_sel")
            chosen_it = items[item_labels.index(chosen_lbl)]
            ic1, ic2 = st.columns([1, 2])
            with ic1:
                orig_uf = next((uf for name, uf in file_map.items() if chosen_it["filename"].endswith(name)), None)
                if orig_uf and orig_uf.name.lower().endswith((".png", ".jpg", ".jpeg", ".bmp", ".tiff", ".webp")):
                    st.image(orig_uf, caption=orig_uf.name, width="stretch")
                else:
                    st.info("Image preview available for image files.")
            with ic2:
                st.markdown(f"**Method:** `{chosen_it['detection_method']}` | **Confidence:** `{int(chosen_it['confidence']*100)}% ({chosen_it['confidence_label']})`")
                st.markdown(f"**Evidence:** `{chosen_it.get('evidence_text', '')}`")
                if chosen_it.get("confidence_reason"):
                    st.caption(f"Reason: {chosen_it['confidence_reason']}")

        return items
