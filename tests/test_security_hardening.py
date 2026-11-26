"""Phase 10 Security & Hardening tests: OIDC JWT, PKCE, RBAC, logout, strict TLS, and secret redaction."""
import time
import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

from backend.config import Settings, get_settings, redact_sensitive
from backend.database.connection import check_database_health, reset_engine
from backend.security.oidc import generate_pkce_pair, verify_oidc_jwt


def _rsa_keypair():
    priv = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    return priv, priv.public_key()


def _oidc_settings() -> Settings:
    return Settings(
        APP_ENV="production",
        OIDC_ENABLED=True,
        OIDC_ISSUER="https://idp.example.internal/tenant",
        OIDC_CLIENT_ID="pdfstudio-client",
        OIDC_AUDIENCE="pdfstudio-client",
        OIDC_GROUP_ENGINEER="grp-eng",
        OIDC_GROUP_TEAM_LEAD="grp-lead",
        OIDC_GROUP_ADMIN="grp-admin",
    )


def test_pkce_s256_generation():
    verifier, challenge = generate_pkce_pair()
    assert len(verifier) >= 43
    assert len(challenge) >= 43
    assert verifier != challenge


def test_oidc_jwt_validation_and_fail_closed():
    priv, pub = _rsa_keypair()
    other_priv, _ = _rsa_keypair()
    cfg = _oidc_settings()
    now = int(time.time())

    # 1. Valid token -> maps Team Lead role
    valid_tok = jwt.encode(
        {
            "sub": "subj-100",
            "preferred_username": "jlee",
            "email": "jlee@example.internal",
            "name": "Jordan Lee",
            "groups": ["grp-lead"],
            "nonce": "n-123",
            "iss": cfg.OIDC_ISSUER,
            "aud": cfg.OIDC_AUDIENCE,
            "exp": now + 300,
        },
        priv,
        algorithm="RS256",
    )
    claims = verify_oidc_jwt(valid_tok, settings=cfg, signing_key=pub, expected_nonce="n-123")
    assert claims.roles == ("Team Lead",)

    # 2. Expired token -> fails closed
    expired_tok = jwt.encode(
        {"sub": "s", "groups": ["grp-eng"], "iss": cfg.OIDC_ISSUER, "aud": cfg.OIDC_AUDIENCE, "exp": now - 60},
        priv,
        algorithm="RS256",
    )
    with pytest.raises(jwt.ExpiredSignatureError):
        verify_oidc_jwt(expired_tok, settings=cfg, signing_key=pub)

    # 3. Invalid issuer -> fails closed
    bad_iss = jwt.encode(
        {"sub": "s", "groups": ["grp-eng"], "iss": "https://evil.invalid", "aud": cfg.OIDC_AUDIENCE, "exp": now + 60},
        priv,
        algorithm="RS256",
    )
    with pytest.raises(jwt.InvalidIssuerError):
        verify_oidc_jwt(bad_iss, settings=cfg, signing_key=pub)

    # 4. Invalid audience -> fails closed
    bad_aud = jwt.encode(
        {"sub": "s", "groups": ["grp-eng"], "iss": cfg.OIDC_ISSUER, "aud": "wrong-app", "exp": now + 60},
        priv,
        algorithm="RS256",
    )
    with pytest.raises(jwt.InvalidAudienceError):
        verify_oidc_jwt(bad_aud, settings=cfg, signing_key=pub)

    # 5. Invalid signature -> fails closed
    bad_sig = jwt.encode(
        {"sub": "s", "groups": ["grp-eng"], "iss": cfg.OIDC_ISSUER, "aud": cfg.OIDC_AUDIENCE, "exp": now + 60},
        other_priv,
        algorithm="RS256",
    )
    with pytest.raises(jwt.InvalidSignatureError):
        verify_oidc_jwt(bad_sig, settings=cfg, signing_key=pub)

    # 6. Nonce mismatch -> fails closed
    with pytest.raises(jwt.InvalidTokenError):
        verify_oidc_jwt(valid_tok, settings=cfg, signing_key=pub, expected_nonce="wrong-nonce")

    # 7. Unmapped group -> fails closed (prevents privilege escalation)
    no_role_tok = jwt.encode(
        {"sub": "s", "groups": ["unrelated-group"], "iss": cfg.OIDC_ISSUER, "aud": cfg.OIDC_AUDIENCE, "exp": now + 60},
        priv,
        algorithm="RS256",
    )
    with pytest.raises(PermissionError):
        verify_oidc_jwt(no_role_tok, settings=cfg, signing_key=pub)


def test_production_rejects_dev_header_and_logout_clears_cookie(isolated_env, monkeypatch):
    client = isolated_env["client"]

    # Logout clears session cookie
    res_out = client.post("/api/auth/logout")
    assert res_out.status_code == 200
    assert res_out.json()["status"] == "logged_out"

    # Production mode rejects X-Username
    monkeypatch.setenv("APP_ENV", "production")
    get_settings.cache_clear()
    res_prod = client.get("/api/files/documents", headers={"X-Username": "engineer1"})
    assert res_prod.status_code == 401
    get_settings.cache_clear()


def test_strict_tls_fails_closed_without_ca_and_redacts_secrets(monkeypatch):
    monkeypatch.setenv("DB_ENCRYPT", "yes")
    monkeypatch.setenv("DB_TRUST_SERVER_CERTIFICATE", "no")
    get_settings.cache_clear()
    reset_engine()

    health = check_database_health()
    assert health["connected"] is False
    assert "Mode A" in health["tls_mode"]
    pwd = get_settings().DB_PASSWORD
    if pwd:
        assert pwd not in (health.get("error") or "")

    sample = "DRIVER={ODBC Driver 18};UID=myuser;PWD=SuperSecret!123;Encrypt=yes;"
    redacted = redact_sensitive(sample)
    assert "SuperSecret!123" not in redacted
    assert "myuser" not in redacted
    reset_engine()
    get_settings.cache_clear()
