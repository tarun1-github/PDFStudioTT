"""Authentication and OIDC session management endpoints."""
import secrets
from fastapi import APIRouter, Depends, HTTPException, Response, status

from backend.config import get_settings
from backend.security.auth import AuthenticatedUser, SESSION_COOKIE_NAME, get_current_user
from backend.security.oidc import build_authorization_url, generate_pkce_pair

router = APIRouter(prefix="/api/auth", tags=["Authentication"])


@router.get("/session")
def get_session_info(user: AuthenticatedUser = Depends(get_current_user)) -> dict:
    return {
        "username": user.username,
        "display_name": user.display_name,
        "roles": list(user.roles),
    }


@router.get("/login-url")
def get_oidc_login_url() -> dict:
    settings = get_settings()
    if not settings.OIDC_ENABLED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="OIDC is disabled in the current configuration.",
        )
    verifier, challenge = generate_pkce_pair()
    state = secrets.token_urlsafe(24)
    nonce = secrets.token_urlsafe(24)
    url = build_authorization_url(settings, state=state, nonce=nonce, code_challenge=challenge)
    return {"authorization_url": url, "state": state, "nonce": nonce, "code_verifier": verifier}


@router.post("/logout")
def logout(response: Response) -> dict[str, str]:
    settings = get_settings()
    response.delete_cookie(
        key=SESSION_COOKIE_NAME,
        httponly=True,
        secure=settings.SESSION_COOKIE_SECURE,
        samesite="lax",
    )
    return {"status": "logged_out"}
