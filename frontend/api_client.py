"""HTTP client wrapper for communicating with the PDF Studio FastAPI backend."""
import os
from typing import Any

import httpx
import streamlit as st


def get_api_base_url() -> str:
    host = os.getenv("API_HOST", "127.0.0.1")
    port = os.getenv("API_PORT", "8010")
    return f"http://{host}:{port}"


def _headers() -> dict[str, str]:
    username = st.session_state.get("active_username", "engineer1")
    return {"X-Username": username}


def api_get(path: str, params: dict[str, Any] | None = None, timeout: float = 15.0) -> Any:
    url = f"{get_api_base_url()}{path}"
    with httpx.Client(timeout=timeout) as client:
        resp = client.get(url, headers=_headers(), params=params)
        resp.raise_for_status()
        return resp.json()


def api_post(path: str, json_body: dict[str, Any] | None = None, timeout: float = 120.0) -> Any:
    url = f"{get_api_base_url()}{path}"
    with httpx.Client(timeout=timeout) as client:
        resp = client.post(url, headers=_headers(), json=json_body)
        resp.raise_for_status()
        return resp.json()


def api_patch(path: str, json_body: dict[str, Any], timeout: float = 30.0) -> Any:
    url = f"{get_api_base_url()}{path}"
    with httpx.Client(timeout=timeout) as client:
        resp = client.patch(url, headers=_headers(), json=json_body)
        resp.raise_for_status()
        return resp.json()


def api_put(path: str, json_body: dict[str, Any], timeout: float = 30.0) -> Any:
    url = f"{get_api_base_url()}{path}"
    with httpx.Client(timeout=timeout) as client:
        resp = client.put(url, headers=_headers(), json=json_body)
        resp.raise_for_status()
        return resp.json()


def api_upload_file(filename: str, content: bytes, content_type: str = "application/octet-stream") -> dict:
    url = f"{get_api_base_url()}/api/files/upload"
    with httpx.Client(timeout=60.0) as client:
        resp = client.post(
            url,
            headers=_headers(),
            files={"file": (filename, content, content_type)},
        )
        resp.raise_for_status()
        return resp.json()


def api_download_bytes(path: str) -> bytes:
    url = f"{get_api_base_url()}{path}"
    with httpx.Client(timeout=60.0) as client:
        resp = client.get(url, headers=_headers())
        resp.raise_for_status()
        return resp.content
