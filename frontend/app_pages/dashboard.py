"""Dashboard page with live MSSQL KPIs, job status chart, and recent activity."""
import pandas as pd
import streamlit as st

from frontend.api_client import api_get
from frontend.components.ui import format_bytes, show_api_error

st.caption("Real-time overview of document publishing, background jobs, and team activity.")

try:
    kpis = api_get("/api/jobs/stats/kpis")
    jobs = api_get("/api/jobs")
    db_status = api_get("/health/db")
except Exception as exc:
    show_api_error(exc)
    st.stop()

with st.grid(3, gap="medium"):
    st.metric(
        "Total documents processed",
        f"{kpis['total_documents_processed']:,}",
        border=True,
        height="stretch",
    )
    st.metric(
        "PDFs generated",
        f"{kpis['pdfs_generated']:,}",
        border=True,
        height="stretch",
    )
    st.metric(
        "Total storage processed",
        format_bytes(kpis["total_storage_bytes"]),
        border=True,
        height="stretch",
    )
    st.metric(
        "Successful jobs",
        f"{kpis['successful_jobs']:,}",
        border=True,
        height="stretch",
    )
    st.metric(
        "Failed jobs",
        f"{kpis['failed_jobs']:,}",
        border=True,
        height="stretch",
    )
    st.metric(
        "Active users",
        f"{kpis['active_users']:,}",
        border=True,
        height="stretch",
    )

col_left, col_right = st.columns([2, 1])

with col_left:
    with st.container(border=True):
        st.subheader("Recent processing jobs")
        if jobs:
            df = pd.DataFrame(jobs)[["job_type", "status", "progress_pct", "created_at"]]
            st.dataframe(df, width="stretch", hide_index=True, alt="Recent PDF processing jobs")
        else:
            st.info("No processing jobs recorded yet. Start by converting an image or document.")

with col_right:
    with st.container(border=True):
        st.subheader("Platform health")
        if db_status.get("connected"):
            st.success(
                f"Connected to `{db_status['database']}` (`{db_status['schema']}` schema)",
                title="MSSQL online",
            )
        else:
            st.error(db_status.get("error") or "Database disconnected", title="MSSQL offline")

        if jobs:
            status_counts = pd.DataFrame(jobs)["status"].value_counts().reset_index()
            status_counts.columns = ["status", "count"]
            st.bar_chart(
                status_counts,
                x="status",
                y="count",
                alt="Job counts by status",
            )
