"""Settings & system diagnostics page."""
import pandas as pd
import streamlit as st

from frontend.api_client import api_get, api_put
from frontend.components.ui import show_api_error

st.caption("Inspect MSSQL database connectivity, LibreOffice status, and platform settings.")

try:
    db_info = api_get("/health/db")
    deps = api_get("/health/dependencies")
except Exception as exc:
    show_api_error(exc)
    st.stop()

c1, c2 = st.columns(2)
with c1:
    with st.container(border=True):
        st.subheader("MSSQL database status")
        st.json(db_info)
with c2:
    with st.container(border=True):
        st.subheader("Runtime dependencies")
        st.json(deps)

st.divider()
st.subheader("Application settings (Admin)")
try:
    settings_rows = api_get("/api/admin/settings")
    st.dataframe(pd.DataFrame(settings_rows), width="stretch", hide_index=True, alt="Application settings")
    with st.form("update_setting_form"):
        keys = [r["setting_key"] for r in settings_rows]
        sel_key = st.selectbox("Setting key", options=keys)
        new_val = st.text_input("New value")
        if st.form_submit_button("Save setting", type="primary"):
            api_put("/api/admin/settings", {"setting_key": sel_key, "setting_value": new_val})
            st.success(f"Updated `{sel_key}`.", title="Saved")
            st.rerun()
except Exception as exc:
    show_api_error(exc)
