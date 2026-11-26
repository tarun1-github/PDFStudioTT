"""Reusable SaaS-style UI components for PDF Studio."""
import httpx
import streamlit as st

from frontend.api_client import api_download_bytes, api_upload_file


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
    col1, col2 = st.columns([1, 3])
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
        st.pdf(pdf_bytes, alt=f"Preview of {filename}")
