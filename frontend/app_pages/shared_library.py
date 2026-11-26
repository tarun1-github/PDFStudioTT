"""Enhanced Shared Knowledge Library with Governance, Version Control, Comparison & Analytics."""
import pandas as pd
import streamlit as st

from frontend.api_client import api_download_bytes, api_get, api_post, api_upload_file
from frontend.components.ui import format_bytes, show_api_error

st.caption("Governed team knowledge library with version control, approval workflows, version diff, and analytics.")

try:
    categories = api_get("/api/governance/categories")
    cat_names = ["All"] + [c["name"] for c in categories]
    analytics = api_get("/api/governance/analytics")
except Exception as exc:
    show_api_error(exc)
    st.stop()

tab_lib, tab_sub, tab_app, tab_ana = st.tabs([
    "Knowledge Library",
    "Submit & Revisions",
    "Approval Workflow",
    "Analytics & Categories",
])

with tab_lib:
    c1, c2, c3, c4 = st.columns([2, 1.5, 1, 1])
    q = c1.text_input("Search title, description, or tags", value="", key="gov_search")
    sel_cat = c2.selectbox("Category", options=cat_names, key="gov_cat")
    sel_status = c3.selectbox(
        "Status",
        options=["All", "PUBLISHED", "DRAFT", "SUBMITTED", "UNDER_REVIEW", "CHANGES_REQUESTED", "APPROVED", "REJECTED", "ARCHIVED"],
        key="gov_status",
    )
    sort_by = c4.selectbox("Sort by", options=["latest", "most_downloaded"], key="gov_sort")

    params = {"q": q, "sort_by": sort_by}
    if sel_cat != "All":
        params["category"] = sel_cat
    if sel_status != "All":
        params["doc_status"] = sel_status

    docs = api_get("/api/governance/documents", params=params)
    if not docs:
        st.info("No governed documents match the current filters.")
    else:
        for d in docs:
            with st.container(border=True):
                h1, h2 = st.columns([4, 1])
                with h1:
                    st.markdown(f"**{d['title']}**  `v{d['current_version']}`  `{d['status']}`")
                    st.caption(
                        f"Category: {d['category']} • Owner: {d['owner']} • "
                        f"Views: {d['view_count']} • Downloads: {d['download_count']}"
                    )
                    if d.get("description"):
                        st.write(d["description"])
                    if d.get("tags"):
                        st.caption("Tags: " + ", ".join(f"`{t}`" for t in d["tags"]))
                with h2:
                    if st.button("Versions & Compare", key=f"ver_btn_{d['doc_key']}", width="stretch"):
                        st.session_state["selected_gov_doc"] = d["doc_key"]

        sel_key = st.session_state.get("selected_gov_doc")
        if sel_key:
            with st.container(border=True):
                st.subheader("Version history & comparison")
                versions = api_get(f"/api/governance/documents/{sel_key}/versions")
                st.dataframe(
                    pd.DataFrame(versions)[["version_number", "filename", "status", "is_immutable", "sha256_hash", "created_at"]],
                    width="stretch",
                    hide_index=True,
                    alt="Document version history",
                )
                ver_map = {f"v{v['version_number']} ({v['status']})": v for v in versions}
                vc1, vc2, vc3 = st.columns([2, 1, 1], vertical_alignment="bottom")
                chosen_lbl = vc1.selectbox("Select version", options=list(ver_map.keys()), key="sel_ver_dl")
                chosen_v = ver_map[chosen_lbl]
                dl_bytes = api_download_bytes(f"/api/governance/documents/{sel_key}/versions/{chosen_v['id']}/download")
                vc2.download_button(
                    "Download",
                    data=dl_bytes,
                    file_name=chosen_v["filename"],
                    mime="application/pdf",
                    key="dl_sel_ver",
                    width="stretch",
                )
                if vc3.button("Restore as draft", key="restore_sel_ver", width="stretch"):
                    try:
                        api_post(f"/api/governance/documents/{sel_key}/versions/{chosen_v['id']}/restore")
                        st.success("Restored as a new DRAFT revision.", title="Restored")
                        st.rerun()
                    except Exception as exc:
                        show_api_error(exc)

                if len(versions) >= 2:
                    st.divider()
                    cc1, cc2, cc3 = st.columns([2, 2, 1], vertical_alignment="bottom")
                    old_lbl = cc1.selectbox("Older version", options=list(ver_map.keys()), index=len(versions) - 1, key="cmp_old")
                    new_lbl = cc2.selectbox("Newer version", options=list(ver_map.keys()), index=0, key="cmp_new")
                    if cc3.button("Compare", key="cmp_run", width="stretch"):
                        cmp_res = api_get(
                            f"/api/governance/documents/{sel_key}/compare",
                            params={"old_version_id": ver_map[old_lbl]["id"], "new_version_id": ver_map[new_lbl]["id"]},
                        )
                        st.info(cmp_res["summary"], title="Comparison summary")
                        if cmp_res["added_lines"]:
                            st.caption("Added text lines (sample):")
                            st.code("\n".join(cmp_res["added_lines"][:15]))
                        if cmp_res["removed_lines"]:
                            st.caption("Removed text lines (sample):")
                            st.code("\n".join(cmp_res["removed_lines"][:15]))

with tab_sub:
    with st.form("create_gov_doc_form"):
        st.subheader("Create new governed document (v1.0 DRAFT)")
        title = st.text_input("Document title")
        desc = st.text_area("Description")
        fc1, fc2, fc3 = st.columns(3)
        cat = fc1.selectbox("Category", options=[c["name"] for c in categories])
        tech = fc2.text_input("Technology (e.g. CUCM, Python, RAG)")
        rev_days = fc3.number_input("Review cycle (days, 0 = none)", min_value=0, max_value=730, value=90)
        tags_raw = st.text_input("Tags (comma-separated)")
        up_pdf = st.file_uploader("Upload PDF", type=["pdf"], key="gov_up_pdf")
        if st.form_submit_button("Create Draft v1.0", type="primary"):
            if not up_pdf or not title.strip():
                st.warning("Title and PDF file are required.")
            else:
                try:
                    saved = api_upload_file(up_pdf.name, up_pdf.getvalue(), "application/pdf")
                    res = api_post(
                        "/api/governance/documents",
                        {
                            "title": title,
                            "description": desc,
                            "category": cat,
                            "technology": tech,
                            "tags": [t.strip() for t in tags_raw.split(",") if t.strip()],
                            "source_relative_path": saved["relative_path"],
                            "review_days": int(rev_days) if rev_days > 0 else None,
                        },
                    )
                    st.success(f"Created `{res['doc_key']}` v{res['version_number']} ({res['status']}).", title="Draft created")
                    st.rerun()
                except Exception as exc:
                    show_api_error(exc)

with tab_app:
    all_docs = api_get("/api/governance/documents")
    if not all_docs:
        st.info("No documents available for workflow actions.")
    else:
        doc_choices = {f"{d['title']} (v{d['current_version']} - {d['status']})": d["doc_key"] for d in all_docs}
        chosen_doc_lbl = st.selectbox("Select document", options=list(doc_choices.keys()), key="wf_doc_sel")
        chosen_key = doc_choices[chosen_doc_lbl]
        target_status = st.selectbox(
            "Target state",
            options=["SUBMITTED", "UNDER_REVIEW", "CHANGES_REQUESTED", "APPROVED", "PUBLISHED", "REJECTED", "ARCHIVED"],
        )
        comments = st.text_area("Review comments / reason (mandatory for Reject, Changes Requested, Archive)")
        if st.button("Apply Workflow Transition", type="primary"):
            try:
                res = api_post(
                    f"/api/governance/documents/{chosen_key}/transition",
                    {"target_status": target_status, "comments": comments},
                )
                st.success(f"Status updated to `{res['status']}`.", title="Workflow updated")
                st.rerun()
            except Exception as exc:
                show_api_error(exc)

        approvals = api_get(f"/api/governance/documents/{chosen_key}/approvals")
        if approvals:
            st.subheader("Approval history")
            st.dataframe(pd.DataFrame(approvals), width="stretch", hide_index=True, alt="Approval history")

with tab_ana:
    with st.grid(4, gap="medium"):
        st.metric("Total documents", analytics["total_documents"], border=True)
        st.metric("Published", analytics["published_documents"], border=True)
        st.metric("Pending approvals", analytics["pending_approvals"], border=True)
        st.metric("Downloads", analytics["total_downloads"], border=True)
    with st.form("add_cat_form"):
        st.subheader("Add category (Admin only)")
        new_cat = st.text_input("Category name")
        new_cat_desc = st.text_input("Description")
        if st.form_submit_button("Add Category"):
            try:
                api_post("/api/governance/categories", {"name": new_cat, "description": new_cat_desc})
                st.success(f"Added category `{new_cat}`.", title="Created")
                st.rerun()
            except Exception as exc:
                show_api_error(exc)
