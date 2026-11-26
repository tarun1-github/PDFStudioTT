"""PDF Studio – Team Document Publishing Platform (Streamlit Entrypoint)."""
import sys
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

APP_ROOT = Path(__file__).resolve().parent.parent
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

load_dotenv(APP_ROOT / ".env")

st.set_page_config(
    page_title="PDF Studio – Team Document Publishing Platform",
    page_icon=":material/picture_as_pdf:",
    layout="wide",
    initial_sidebar_state="expanded",
)

if "active_username" not in st.session_state:
    st.session_state.active_username = "engineer1"

DEV_USERS = {
    "engineer1": "Alex Rivera (Engineer)",
    "lead1": "Jordan Lee (Team Lead)",
    "admin1": "Morgan Chen (Admin)",
}

with st.sidebar:
    st.markdown("### :material/picture_as_pdf: PDF STUDIO")
    st.caption("Team Document Publishing Platform")
    st.divider()
    selected_user = st.selectbox(
        "Active workspace user (Dev Mode)",
        options=list(DEV_USERS.keys()),
        format_func=lambda k: DEV_USERS[k],
        key="active_username",
        help="Development-only user switcher. Production uses corporate OIDC/SSO.",
    )
    st.caption(f"Signed in as `{selected_user}`")

pages = {
    "Workspace": [
        st.Page(
            "app_pages/dashboard.py",
            title="Dashboard",
            icon=":material/dashboard:",
            help="Overview of processed documents, job health, storage metrics, and recent activity.",
        ),
        st.Page(
            "app_pages/shared_library.py",
            title="Shared library",
            icon=":material/folder_shared:",
            help="Browse and download approved team learning material, technical docs, and sketchnotes.",
        ),
        st.Page(
            "app_pages/processing_history.py",
            title="Processing history",
            icon=":material/history:",
            help="Track queued, active, completed, and failed PDF jobs and download your outputs.",
        ),
    ],
    "Publishing & Conversion": [
        st.Page(
            "app_pages/learning_book_creator.py",
            title="Learning book creator",
            icon=":material/menu_book:",
            help="Create structured technical manuals and sketchnote books with cover, TOC, and bookmarks.",
        ),
        st.Page(
            "app_pages/pdf_compiler.py",
            title="PDF compiler",
            icon=":material/layers:",
            help="Combine mixed images, Office/Markdown docs, and PDFs into one ordered PDF.",
        ),
        st.Page(
            "app_pages/image_to_pdf.py",
            title="Image to PDF",
            icon=":material/image:",
            help="Convert PNG, JPG, BMP, TIFF, and WEBP images to high-quality PDFs.",
        ),
        st.Page(
            "app_pages/document_to_pdf.py",
            title="Document to PDF",
            icon=":material/description:",
            help="Convert DOCX, TXT, MD, HTML, XLSX, and PPTX documents to verified PDFs.",
        ),
        st.Page(
            "app_pages/pdf_manager.py",
            title="PDF manager",
            icon=":material/build:",
            help="Merge, split, extract, rotate, compress, number, watermark, and bookmark PDFs.",
        ),
    ],
    "Administration": [
        st.Page(
            "app_pages/user_management.py",
            title="User management",
            icon=":material/group:",
            help="Manage team accounts, roles (Engineer, Team Lead, Admin), and audit activity.",
        ),
        st.Page(
            "app_pages/settings.py",
            title="Settings",
            icon=":material/settings:",
            help="Inspect MSSQL health, LibreOffice dependency status, and application settings.",
        ),
    ],
}

current_page = st.navigation(pages, position="sidebar")
st.title(current_page.title, icon=current_page.icon)
current_page.run()
