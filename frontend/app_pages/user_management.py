"""User Management & Audit Log page (Admin role required)."""
import pandas as pd
import streamlit as st

from frontend.api_client import api_get, api_patch, api_post
from frontend.components.ui import show_api_error

st.caption("Manage team users, RBAC roles (Engineer, Team Lead, Admin), and security audit logs.")

try:
    users = api_get("/api/admin/users")
    logs = api_get("/api/admin/audit-logs")
except Exception as exc:
    show_api_error(exc)
    st.stop()

with st.container(border=True):
    st.subheader("Team accounts")
    st.dataframe(pd.DataFrame(users), width="stretch", hide_index=True, alt="Team users and roles")

c1, c2 = st.columns(2)
with c1:
    with st.form("create_user_form"):
        st.subheader("Create team user")
        username = st.text_input("Username")
        display_name = st.text_input("Display name")
        email = st.text_input("Email")
        role_name = st.selectbox("Role", ["Engineer", "Team Lead", "Admin"])
        if st.form_submit_button("Create user", type="primary"):
            try:
                api_post(
                    "/api/admin/users",
                    {
                        "username": username,
                        "display_name": display_name,
                        "email": email,
                        "role_name": role_name,
                    },
                )
                st.success(f"Created user `{username}`.", title="User created")
                st.rerun()
            except Exception as exc:
                show_api_error(exc)

with c2:
    with st.form("update_role_form"):
        st.subheader("Update user role")
        user_choices = {f"{u['username']} ({', '.join(u['roles'])})": u["id"] for u in users}
        selected = st.selectbox("User", options=list(user_choices.keys()))
        new_role = st.selectbox("New role", ["Engineer", "Team Lead", "Admin"])
        if st.form_submit_button("Update role", type="primary"):
            try:
                api_patch(f"/api/admin/users/{user_choices[selected]}/role", {"role_name": new_role})
                st.success("Role updated.", title="Updated")
                st.rerun()
            except Exception as exc:
                show_api_error(exc)

with st.container(border=True):
    st.subheader("Recent audit logs")
    if logs:
        st.dataframe(pd.DataFrame(logs), width="stretch", hide_index=True, alt="Audit logs")
    else:
        st.info("No audit events recorded yet.")
