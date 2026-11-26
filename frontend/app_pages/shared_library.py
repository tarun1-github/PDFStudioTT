"""Shared Library page: browse approved team documents and publish (Team Lead / Admin)."""
import streamlit as st

from frontend.api_client import api_download_bytes, api_get, api_post
from frontend.components.ui import show_api_error

st.caption("Access approved team learning materials, technical documents, and sketchnotes.")

CATEGORIES = ["All", "learning_material", "technical_documents", "sketchnotes", "published_pdfs"]
selected_cat = st.segmented_control("Category", options=CATEGORIES, default="All")

try:
    params = None if selected_cat in (None, "All") else {"category": selected_cat}
    shared_docs = api_get("/api/shared", params=params)
    my_docs = api_get("/api/files/documents")
except Exception as exc:
    show_api_error(exc)
    st.stop()

with st.container(border=True):
    st.subheader("Published team documents")
    if not shared_docs:
        st.info("No shared documents published in this category yet.")
    else:
        for doc in shared_docs:
            c1, c2 = st.columns([4, 1], vertical_alignment="center")
            with c1:
                st.markdown(f"**{doc['title']}**  `{doc['category']}`")
                if doc.get("description"):
                    st.caption(doc["description"])
            with c2:
                pdf_bytes = api_download_bytes(f"/api/shared/{doc['id']}/download")
                st.download_button(
                    "Download",
                    data=pdf_bytes,
                    file_name=f"{doc['title']}.pdf",
                    mime="application/pdf",
                    key=f"dl_shared_{doc['id']}",
                    icon=":material/download:",
                    width="stretch",
                )

with st.expander("Publish a personal document to Shared Library (Team Lead / Admin only)", expanded=False):
    if not my_docs:
        st.info("Generate a PDF first before publishing.")
    else:
        doc_map = {f"{d['title']} ({d['filename']})": d["doc_uuid"] for d in my_docs}
        chosen = st.selectbox("Select document", options=list(doc_map.keys()))
        pub_cat = st.selectbox(
            "Target shared category",
            options=["learning_material", "technical_documents", "sketchnotes", "published_pdfs"],
        )
        pub_title = st.text_input("Published title", value=chosen.split(" (")[0])
        pub_desc = st.text_area("Description", value="")
        if st.button("Publish to Shared Library", type="primary", icon=":material/publish:"):
            try:
                api_post(
                    "/api/shared/publish",
                    {
                        "doc_uuid": doc_map[chosen],
                        "category": pub_cat,
                        "title": pub_title,
                        "description": pub_desc,
                    },
                )
                st.success("Document published to Shared Library.", title="Published")
                st.rerun()
            except Exception as exc:
                show_api_error(exc)
