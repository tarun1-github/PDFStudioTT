"""Database schema verification and seed data initialization."""
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.config import get_settings
from backend.database.models import ApplicationSetting, DocumentCategory, Role, User, UserRole

DEFAULT_CATEGORIES = [
    "Cisco Collaboration",
    "CUCM",
    "Unity Connection",
    "SIP and Voice Gateways",
    "Linux",
    "Automation",
    "Python",
    "AI and Agentic AI",
    "RAG",
    "Training and Learning",
    "General Technical Documentation",
]

DEFAULT_ROLES = [
    ("Engineer", "Upload, convert, compile, download personal docs, view shared library."),
    ("Team Lead", "Engineer permissions plus publish approved docs and view team activity."),
    ("Admin", "Full administrative access: users, roles, audit logs, and settings."),
]

DEFAULT_DEV_USERS = [
    ("engineer1", "Alex Rivera (Engineer)", "engineer1@pdfstudio.local", "user_001", "Engineer"),
    ("lead1", "Jordan Lee (Team Lead)", "lead1@pdfstudio.local", "user_002", "Team Lead"),
    ("admin1", "Morgan Chen (Admin)", "admin1@pdfstudio.local", "user_003", "Admin"),
]

DEFAULT_SETTINGS = [
    ("max_upload_mb", "100", "Maximum upload size per file in MB."),
    ("max_concurrent_jobs", "3", "Maximum concurrent background PDF jobs."),
    ("temp_retention_hours", "24", "Hours before temporary files are eligible for cleanup."),
    ("default_page_size", "A4", "Default PDF page size."),
    ("oidc_enabled", "false", "Corporate OIDC/SSO status."),
]


def seed_database(db: Session) -> None:
    """Idempotently seed roles, settings, and (in development) sample team users."""
    settings = get_settings()

    role_map: dict[str, Role] = {}
    for role_name, desc in DEFAULT_ROLES:
        role = db.scalar(select(Role).where(Role.name == role_name))
        if role is None:
            role = Role(name=role_name, description=desc)
            db.add(role)
            db.flush()
        role_map[role_name] = role

    if settings.APP_ENV.lower() == "development":
        for username, display_name, email, folder, role_name in DEFAULT_DEV_USERS:
            user = db.scalar(select(User).where(User.username == username))
            if user is None:
                user = User(
                    username=username,
                    display_name=display_name,
                    email=email,
                    storage_folder=folder,
                    auth_provider="local_dev",
                    is_active=True,
                )
                db.add(user)
                db.flush()
                db.add(UserRole(user_id=user.id, role_id=role_map[role_name].id))

    for key, val, desc in DEFAULT_SETTINGS:
        existing = db.scalar(
            select(ApplicationSetting).where(ApplicationSetting.setting_key == key)
        )
        if existing is None:
            db.add(ApplicationSetting(setting_key=key, setting_value=val, description=desc))

    for cat_name in DEFAULT_CATEGORIES:
        existing_cat = db.scalar(
            select(DocumentCategory).where(DocumentCategory.name == cat_name)
        )
        if existing_cat is None:
            db.add(DocumentCategory(name=cat_name, is_active=True))

    db.commit()
