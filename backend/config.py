"""Application configuration loaded from .env without exposing secrets."""
import re
from functools import lru_cache
from pathlib import Path
from urllib.parse import quote_plus

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

APP_ROOT = Path(__file__).resolve().parent.parent
ENV_FILE = APP_ROOT / ".env"

_SENSITIVE_CONN_RE = re.compile(
    r"(?i)(PWD|PASSWORD|UID|USER\s*ID)\s*(=|%3D)\s*[^;&\s)]+"
)


def redact_sensitive(text: str) -> str:
    """Redact UID/PWD and encoded connection string credentials from logs/errors."""
    return _SENSITIVE_CONN_RE.sub(r"\1\2***REDACTED***", text)


def parse_odbc_bool(value: str | bool, field_name: str) -> str:
    """Parse yes/no, true/false, 1/0 into ODBC 'yes' or 'no'."""
    if isinstance(value, bool):
        return "yes" if value else "no"
    norm = value.strip().lower()
    if norm in {"yes", "true", "1"}:
        return "yes"
    if norm in {"no", "false", "0"}:
        return "no"
    raise ValueError(
        f"Invalid boolean value '{value}' for {field_name}. Expected yes/no, true/false, or 1/0."
    )


class Settings(BaseSettings):
    """Typed application settings backed by .env and environment variables."""

    model_config = SettingsConfigDict(
        env_file=str(ENV_FILE),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    APP_NAME: str = "PDF Studio"
    APP_ENV: str = "development"

    APP_HOST: str = "0.0.0.0"
    APP_PORT: int = 8501
    API_HOST: str = "127.0.0.1"
    API_PORT: int = 8000

    DB_SERVER: str = "10.106.44.20"
    DB_PORT: int = 1433
    DB_DATABASE: str = "CPDB"
    DB_SCHEMA: str = "pdfstudio"
    DB_USER: str = Field(default="", repr=False)
    DB_PASSWORD: str = Field(default="", repr=False)
    DB_DRIVER: str = "ODBC Driver 18 for SQL Server"
    DB_AUTH: str = "sql"  # "sql" or "windows"
    DB_ENCRYPT: str = "yes"
    DB_TRUST_SERVER_CERTIFICATE: str = "no"
    DB_TIMEOUT: int = 10

    STORAGE_ROOT: Path = Path(r"E:\Projects\PDFStudio\data")
    MAX_UPLOAD_MB: int = 100
    MAX_CONCURRENT_JOBS: int = 3
    JOB_TIMEOUT_SECONDS: int = 300
    JOB_MAX_RETRIES: int = 2
    LOG_LEVEL: str = "INFO"

    # Optional OIDC / SSO (provider-neutral; configured when IdP details are approved)
    OIDC_ENABLED: bool = False
    OIDC_ISSUER: str = ""
    OIDC_CLIENT_ID: str = ""
    OIDC_AUDIENCE: str = ""
    OIDC_JWKS_URI: str = ""
    OIDC_REDIRECT_URI: str = ""
    OIDC_ROLE_CLAIM: str = "groups"
    OIDC_GROUP_ENGINEER: str = ""
    OIDC_GROUP_TEAM_LEAD: str = ""
    OIDC_GROUP_ADMIN: str = ""
    SESSION_TTL_MINUTES: int = 480
    SESSION_COOKIE_SECURE: bool = True

    # Optional local Vision-Model fallback for ambiguous OCR pages (disabled by default)
    VISION_FALLBACK_ENABLED: bool = False
    OLLAMA_BASE_URL: str = ""
    OLLAMA_VISION_MODEL: str = ""

    @property
    def max_upload_bytes(self) -> int:
        return self.MAX_UPLOAD_MB * 1024 * 1024

    @property
    def api_base_url(self) -> str:
        return f"http://{self.API_HOST}:{self.API_PORT}"

    @property
    def db_encrypt_odbc(self) -> str:
        return parse_odbc_bool(self.DB_ENCRYPT, "DB_ENCRYPT")

    @property
    def db_trust_cert_odbc(self) -> str:
        return parse_odbc_bool(self.DB_TRUST_SERVER_CERTIFICATE, "DB_TRUST_SERVER_CERTIFICATE")

    @property
    def tls_mode_label(self) -> str:
        enc = self.db_encrypt_odbc
        tsc = self.db_trust_cert_odbc
        if enc == "yes" and tsc == "no":
            return "Mode A (Encrypted, Strict CA Certificate Validation)"
        if enc == "yes" and tsc == "yes":
            return "Mode B (Encrypted, TrustServerCertificate=yes - Authorized Dev Only)"
        return f"Custom (Encrypt={enc}, TrustServerCertificate={tsc})"

    def build_odbc_connection_string(self) -> str:
        """Build an ODBC Driver 18 connection string for pyodbc."""
        parts = [
            f"DRIVER={{{self.DB_DRIVER}}}",
            f"SERVER={self.DB_SERVER},{self.DB_PORT}",
            f"DATABASE={self.DB_DATABASE}",
            f"Encrypt={self.db_encrypt_odbc}",
            f"TrustServerCertificate={self.db_trust_cert_odbc}",
            f"Connection Timeout={self.DB_TIMEOUT}",
        ]
        if self.DB_AUTH.lower() == "windows":
            parts.append("Trusted_Connection=yes")
        else:
            if not self.DB_USER or not self.DB_PASSWORD:
                raise ValueError(
                    "DB_USER and DB_PASSWORD must be configured in .env when DB_AUTH=sql."
                )
            parts.append(f"UID={self.DB_USER}")
            parts.append(f"PWD={self.DB_PASSWORD}")
        return ";".join(parts) + ";"

    def build_sqlalchemy_url(self) -> str:
        """Build a SQLAlchemy mssql+pyodbc URL (used only when creator is unavailable)."""
        odbc_str = self.build_odbc_connection_string()
        return f"mssql+pyodbc:///?odbc_connect={quote_plus(odbc_str)}"


@lru_cache
def get_settings() -> Settings:
    return Settings()
