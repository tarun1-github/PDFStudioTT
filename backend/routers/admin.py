"""Admin endpoints for user management, roles, audit logs, and settings."""
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.database.models import ApplicationSetting, AuditLog, Role, User, UserRole
from backend.database.session import get_db
from backend.security.auth import ROLE_ADMIN, AuthenticatedUser, require_roles
from backend.security.storage import ensure_user_folders, sanitize_folder_name
from backend.services.job_service import log_audit

router = APIRouter(prefix="/api/admin", tags=["Admin"])


class CreateUserRequest(BaseModel):
    username: str
    display_name: str
    email: str
    role_name: str = "Engineer"


class UpdateRoleRequest(BaseModel):
    role_name: str


class UpdateSettingRequest(BaseModel):
    setting_key: str
    setting_value: str
    description: str | None = None


@router.get("/users")
def list_users(
    _admin: AuthenticatedUser = Depends(require_roles(ROLE_ADMIN)),
    db: Session = Depends(get_db),
) -> list[dict]:
    users = db.scalars(select(User).order_by(User.id.asc())).all()
    output = []
    for u in users:
        roles = list(
            db.scalars(
                select(Role.name)
                .join(UserRole, UserRole.role_id == Role.id)
                .where(UserRole.user_id == u.id)
            ).all()
        )
        output.append(
            {
                "id": u.id,
                "username": u.username,
                "display_name": u.display_name,
                "email": u.email,
                "storage_folder": u.storage_folder,
                "is_active": u.is_active,
                "roles": roles,
                "created_at": u.created_at.isoformat(),
            }
        )
    return output


@router.post("/users")
def create_user(
    req: CreateUserRequest,
    admin: AuthenticatedUser = Depends(require_roles(ROLE_ADMIN)),
    db: Session = Depends(get_db),
) -> dict:
    role = db.scalar(select(Role).where(Role.name == req.role_name))
    if role is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid role name.")
    if db.scalar(select(User).where(User.username == req.username)):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Username already exists.")

    folder = sanitize_folder_name(f"user_{req.username}")
    ensure_user_folders(folder)
    user = User(
        username=req.username.strip(),
        display_name=req.display_name.strip(),
        email=req.email.strip(),
        storage_folder=folder,
        is_active=True,
    )
    db.add(user)
    db.flush()
    db.add(UserRole(user_id=user.id, role_id=role.id))
    log_audit(db, admin.id, "USER_CREATED", "user", str(user.id), f"username={user.username}")
    db.commit()
    return {"id": user.id, "username": user.username, "role": role.name}


@router.patch("/users/{user_id}/role")
def update_user_role(
    user_id: int,
    req: UpdateRoleRequest,
    admin: AuthenticatedUser = Depends(require_roles(ROLE_ADMIN)),
    db: Session = Depends(get_db),
) -> dict:
    user = db.get(User, user_id)
    role = db.scalar(select(Role).where(Role.name == req.role_name))
    if user is None or role is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User or role not found.")
    existing_links = db.scalars(select(UserRole).where(UserRole.user_id == user_id)).all()
    for link in existing_links:
        db.delete(link)
    db.flush()
    db.add(UserRole(user_id=user_id, role_id=role.id))
    log_audit(db, admin.id, "USER_ROLE_UPDATED", "user", str(user_id), f"role={role.name}")
    db.commit()
    return {"user_id": user_id, "role": role.name}


@router.get("/audit-logs")
def list_audit_logs(
    _admin: AuthenticatedUser = Depends(require_roles(ROLE_ADMIN)),
    db: Session = Depends(get_db),
) -> list[dict]:
    logs = db.scalars(select(AuditLog).order_by(AuditLog.created_at.desc()).limit(200)).all()
    return [
        {
            "id": l.id,
            "user_id": l.user_id,
            "action": l.action,
            "resource_type": l.resource_type,
            "resource_id": l.resource_id,
            "details": l.details,
            "created_at": l.created_at.isoformat(),
        }
        for l in logs
    ]


@router.get("/settings")
def get_app_settings(
    _admin: AuthenticatedUser = Depends(require_roles(ROLE_ADMIN)),
    db: Session = Depends(get_db),
) -> list[dict]:
    rows = db.scalars(select(ApplicationSetting).order_by(ApplicationSetting.setting_key.asc())).all()
    return [
        {
            "setting_key": r.setting_key,
            "setting_value": r.setting_value,
            "description": r.description,
        }
        for r in rows
    ]


@router.put("/settings")
def upsert_app_setting(
    req: UpdateSettingRequest,
    admin: AuthenticatedUser = Depends(require_roles(ROLE_ADMIN)),
    db: Session = Depends(get_db),
) -> dict:
    row = db.scalar(select(ApplicationSetting).where(ApplicationSetting.setting_key == req.setting_key))
    if row is None:
        row = ApplicationSetting(
            setting_key=req.setting_key,
            setting_value=req.setting_value,
            description=req.description,
            updated_by_user_id=admin.id,
        )
        db.add(row)
    else:
        row.setting_value = req.setting_value
        if req.description is not None:
            row.description = req.description
        row.updated_by_user_id = admin.id
    log_audit(db, admin.id, "SETTING_UPDATED", "application_setting", req.setting_key, req.setting_value)
    db.commit()
    return {"setting_key": row.setting_key, "setting_value": row.setting_value}
