"""Backend authorization and authentication dependencies (Dev mode + fail-closed OIDC)."""
from dataclasses import dataclass
from typing import Callable

from fastapi import Cookie, Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.config import get_settings
from backend.database.models import Role, User, UserRole
from backend.database.session import get_db
from backend.security.storage import ensure_user_folders, sanitize_folder_name

ROLE_ENGINEER = "Engineer"
ROLE_TEAM_LEAD = "Team Lead"
ROLE_ADMIN = "Admin"
SESSION_COOKIE_NAME = "pdfstudio_session"


@dataclass(frozen=True)
class AuthenticatedUser:
    id: int
    username: str
    display_name: str
    email: str
    storage_folder: str
    roles: tuple[str, ...]

    def has_any_role(self, *allowed_roles: str) -> bool:
        if ROLE_ADMIN in self.roles:
            return True
        return any(r in self.roles for r in allowed_roles)


def _provision_or_sync_oidc_user(db: Session, claims) -> AuthenticatedUser:
    user = db.scalar(select(User).where(User.external_subject == claims.subject, User.is_active == True))  # noqa: E712
    if user is None:
        folder = sanitize_folder_name(f"oidc_{claims.username}")
        ensure_user_folders(folder)
        user = User(
            username=claims.username[:100],
            display_name=claims.display_name[:150],
            email=claims.email[:255],
            storage_folder=folder,
            is_active=True,
            auth_provider="oidc",
            external_subject=claims.subject[:255],
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    return AuthenticatedUser(
        id=user.id,
        username=user.username,
        display_name=user.display_name,
        email=user.email,
        storage_folder=user.storage_folder,
        roles=claims.roles,
    )


def get_current_user(
    x_username: str | None = Header(default=None, alias="X-Username"),
    authorization: str | None = Header(default=None, alias="Authorization"),
    session_cookie: str | None = Cookie(default=None, alias=SESSION_COOKIE_NAME),
    db: Session = Depends(get_db),
) -> AuthenticatedUser:
    settings = get_settings()

    if settings.OIDC_ENABLED:
        from backend.security.oidc import verify_oidc_jwt

        token = None
        if authorization and authorization.startswith("Bearer "):
            token = authorization.removeprefix("Bearer ").strip()
        elif session_cookie:
            token = session_cookie.strip()

        if not token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="OIDC bearer token or valid session cookie required.",
            )
        try:
            claims = verify_oidc_jwt(token, settings=settings)
        except PermissionError as exc:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired OIDC token.",
            )
        return _provision_or_sync_oidc_user(db, claims)

    if settings.APP_ENV.lower() != "development":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Development header auth is disabled outside APP_ENV=development.",
        )

    username = (x_username or "").strip()
    if not username:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing X-Username header.",
        )

    user = db.scalar(select(User).where(User.username == username, User.is_active == True))  # noqa: E712
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Unknown or inactive user '{username}'.",
        )

    role_names = tuple(
        db.scalars(
            select(Role.name)
            .join(UserRole, UserRole.role_id == Role.id)
            .where(UserRole.user_id == user.id)
        ).all()
    )
    return AuthenticatedUser(
        id=user.id,
        username=user.username,
        display_name=user.display_name,
        email=user.email,
        storage_folder=user.storage_folder,
        roles=role_names or (ROLE_ENGINEER,),
    )


def require_roles(*allowed_roles: str) -> Callable[[AuthenticatedUser], AuthenticatedUser]:
    """Dependency enforcing backend RBAC for endpoints."""

    def _dependency(user: AuthenticatedUser = Depends(get_current_user)) -> AuthenticatedUser:
        if not user.has_any_role(*allowed_roles):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Insufficient permissions. Required role: {', '.join(allowed_roles)}.",
            )
        return user

    return _dependency
