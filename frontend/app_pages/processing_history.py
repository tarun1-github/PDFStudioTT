"""Processing History page: job queue status and personal generated documents."""
import pandas as pd
import streamlit as st

from frontend.api_client import api_download_bytes, api_get
from frontend.components.ui import format_bytes, show_api_error

st.caption("Monitor background job execution and download your generated PDFs.")

try:
    jobs = api_get("/api/jobs")
    docs = api_get("/api/files/documents")
except Exception as exc:
    show_api_error(exc)
    st.stop()

tab1, tab2 = st.tabs(["My generated PDFs", "Job execution log"])

with tab1:
    if not docs:
        st.info("You have not generated any PDFs yet.")
    else:
        for doc in docs:
            c1, c2 = st.columns([4, 1], vertical_alignment="center")
            with c1:
                st.markdown(f"**{doc['title']}** (`{doc['operation_type']}`)")
                st.caption(
                    f"{doc['filename']} • {doc['page_count']} pages • {format_bytes(doc['file_size_bytes'])} • {doc['created_at']}"
                )
            with c2:
                pdf_bytes = api_download_bytes(f"/api/files/documents/{doc['doc_uuid']}/download")
                st.download_button(
                    "Download",
                    data=pdf_bytes,
                    file_name=doc["filename"],
                    mime="application/pdf",
                    key=f"hist_dl_{doc['doc_uuid']}",
                    icon=":material/download:",
                    width="stretch",
                )

with tab2:
    if not jobs:
        st.info("No jobs found.")
    else:
        df = pd.DataFrame(jobs)
        st.dataframe(df, width="stretch", hide_index=True, alt="PDF processing job history")
