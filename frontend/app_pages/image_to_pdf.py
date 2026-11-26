"""Image to PDF converter with ordering, thumbnail preview, and aspect-ratio preservation."""
import streamlit as st

from frontend.api_client import api_post
from frontend.components.ui import (
    render_generated_pdf_result,
    show_api_error,
    upload_many_to_backend,
)

st.caption("Convert PNG, JPG, JPEG, BMP, TIFF, and WEBP images into a high-quality PDF without distortion.")

uploaded = st.file_uploader(
    "Upload images",
    type=["png", "jpg", "jpeg", "bmp", "tiff", "tif", "webp"],
    accept_multiple_files=True,
)

if uploaded:
    if "img_order" not in st.session_state or len(st.session_state.img_order) != len(uploaded):
        st.session_state.img_order = list(range(len(uploaded)))

    with st.container(border=True):
        st.subheader("Image order & thumbnail preview")
        cols = st.columns(min(4, len(uploaded)))
        for pos, orig_idx in enumerate(st.session_state.img_order):
            uf = uploaded[orig_idx]
            with cols[pos % len(cols)]:
                st.image(uf, caption=f"{pos + 1}. {uf.name}", width="stretch")
                c1, c2 = st.columns(2)
                with c1:
                    if pos > 0 and st.button("Left", key=f"img_up_{pos}", icon=":material/arrow_back:", width="stretch"):
                        order = st.session_state.img_order
                        order[pos - 1], order[pos] = order[pos], order[pos - 1]
                        st.rerun()
                with c2:
                    if pos < len(uploaded) - 1 and st.button("Right", key=f"img_dn_{pos}", icon=":material/arrow_forward:", width="stretch"):
                        order = st.session_state.img_order
                        order[pos + 1], order[pos] = order[pos], order[pos + 1]
                        st.rerun()

    with st.container(border=True):
        st.subheader("Page layout settings")
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            page_size = st.selectbox("Page size", ["A4", "A3", "Letter", "Original"])
        with c2:
            orientation = st.segmented_control(
                "Orientation",
                options=["auto", "portrait", "landscape"],
                default="auto",
            )
        with c3:
            margin_mm = st.number_input("Margin (mm)", min_value=0.0, max_value=50.0, value=10.0, step=1.0)
        with c4:
            output_filename = st.text_input("Output filename", value="images_bundle.pdf")

        if st.button("Generate PDF", type="primary", icon=":material/picture_as_pdf:", width="stretch"):
            try:
                ordered_files = [uploaded[i] for i in st.session_state.img_order]
                saved = upload_many_to_backend(ordered_files)
                with st.spinner("Rendering PDF..."):
                    res = api_post(
                        "/api/pdf/image-to-pdf",
                        {
                            "input_paths": [s["relative_path"] for s in saved],
                            "page_size": page_size,
                            "orientation": orientation or "auto",
                            "margin_mm": margin_mm,
                            "output_filename": output_filename,
                        },
                    )
                render_generated_pdf_result(res)
            except Exception as exc:
                show_api_error(exc)
