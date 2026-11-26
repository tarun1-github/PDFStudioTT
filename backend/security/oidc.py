"""Provider-neutral OIDC / PKCE S256 / JWKS verification module (fail-closed)."""
import base64
import hashlib
import secrets
import time
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlencode

import httpx
import jwt
from jwt import PyJWKClient

from backend.config import Settings, get_settings
from backend.security.auth import ROLE_ADMIN, ROLE_ENGINEER, ROLE_TEAM_LEAD


@dataclass(frozen=True)
class OIDCClaims:
    subject: str
    username: str
    email: str
    display_name: str
    roles: tuple[str, ...]
    exp: int
    nonce: str | None = None


_DISCOVERY_CACHE: dict[str, tuple[float, dict[str, Any]]] = {}
_JWKS_CLIENTS: dict[str, PyJWKClient] = {}


def generate_pkce_pair() -> tuple[str, str]:
    """Generate a RFC 7636 PKCE code_verifier and S256 code_challenge."""
    verifier = base64.urlsafe_b64encode(secrets.token_bytes(32)).rstrip(b"=").decode("ascii")
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
    return verifier, challenge


def fetch_oidc_discovery(issuer: str, timeout: float = 5.0) -> dict[str, Any]:
    """Fetch and cache OIDC provider metadata from .well-known/openid-configuration."""
    if not issuer:
        raise ValueError("OIDC_ISSUER is not configured.")
    now = time.time()
    cached = _DISCOVERY_CACHE.get(issuer)
    if cached and now - cached[0] < 3600:
        return cached[1]
    url = f"{issuer.rstrip('/')}/.well-known/openid-configuration"
    with httpx.Client(timeout=timeout) as client:
        resp = client.get(url)
        resp.raise_for_status()
        doc = resp.json()
    _DISCOVERY_CACHE[issuer] = (now, doc)
    return doc


def build_authorization_url(
    settings: Settings,
    state: str,
    nonce: str,
    code_challenge: str,
    authorization_endpoint: str | None = None,
) -> str:
    """Build OIDC Authorization Code + PKCE S256 redirect URL."""
    endpoint = authorization_endpoint or fetch_oidc_discovery(settings.OIDC_ISSUER)["authorization_endpoint"]
    params = {
        "response_type": "code",
        "client_id": settings.OIDC_CLIENT_ID,
        "redirect_uri": settings.OIDC_REDIRECT_URI,
        "scope": "openid profile email",
        "state": state,
        "nonce": nonce,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
    }
    return f"{endpoint}?{urlencode(params)}"


def map_groups_to_roles(groups: list[str] | tuple[str, ...], settings: Settings) -> tuple[str, ...]:
    """Map configured IdP group identifiers to PDF Studio RBAC roles without privilege escalation."""
    group_set = {str(g).strip() for g in groups if str(g).strip()}
    roles: list[str] = []
    if settings.OIDC_GROUP_ADMIN and settings.OIDC_GROUP_ADMIN in group_set:
        roles.append(ROLE_ADMIN)
    if settings.OIDC_GROUP_TEAM_LEAD and settings.OIDC_GROUP_TEAM_LEAD in group_set:
        roles.append(ROLE_TEAM_LEAD)
    if settings.OIDC_GROUP_ENGINEER and settings.OIDC_GROUP_ENGINEER in group_set:
        roles.append(ROLE_ENGINEER)
    return tuple(roles)


def verify_oidc_jwt(
    token: str,
    settings: Settings | None = None,
    signing_key: Any | None = None,
    expected_nonce: str | None = None,
    algorithms: list[str] | None = None,
) -> OIDCClaims:
    """Verify an OIDC JWT using JWKS (or injected key in tests). Fails closed on any error."""
    cfg = settings or get_settings()
    if not token or not cfg.OIDC_ISSUER or not (cfg.OIDC_AUDIENCE or cfg.OIDC_CLIENT_ID):
        raise ValueError("OIDC issuer/audience or token missing.")

    audience = cfg.OIDC_AUDIENCE or cfg.OIDC_CLIENT_ID
    algs = algorithms or ["RS256", "ES256"]

    if signing_key is None:
        jwks_uri = cfg.OIDC_JWKS_URI or fetch_oidc_discovery(cfg.OIDC_ISSUER)["jwks_uri"]
        jwk_client = _JWKS_CLIENTS.get(jwks_uri)
        if jwk_client is None:
            jwk_client = PyJWKClient(jwks_uri)
            _JWKS_CLIENTS[jwks_uri] = jwk_client
        key = jwk_client.get_signing_key_from_jwt(token).key
    else:
        key = signing_key

    payload = jwt.decode(
        token,
        key=key,
        algorithms=algs,
        audience=audience,
        issuer=cfg.OIDC_ISSUER,
        options={"require": ["exp", "iss", "aud", "sub"]},
    )

    token_nonce = payload.get("nonce")
    if expected_nonce is not None and token_nonce != expected_nonce:
        raise jwt.InvalidTokenError("OIDC nonce mismatch.")

    raw_groups = payload.get(cfg.OIDC_ROLE_CLAIM) or []
    if isinstance(raw_groups, str):
        raw_groups = [raw_groups]
    roles = map_groups_to_roles(raw_groups, cfg)
    if not roles:
        raise PermissionError("No authorized PDF Studio role mapped from IdP group claims.")

    sub = str(payload["sub"])
    username = str(payload.get("preferred_username") or payload.get("email") or sub)
    email = str(payload.get("email") or f"{username}@oidc.local")
    display_name = str(payload.get("name") or username)
    return OIDCClaims(
        subject=sub,
        username=username,
        email=email,
        display_name=display_name,
        roles=roles,
        exp=int(payload["exp"]),
        nonce=token_nonce,
    )
