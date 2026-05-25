"""URL path prefix when the app is served behind a reverse proxy (e.g. /technodt)."""

from __future__ import annotations

from urllib.parse import urlparse

from starlette.requests import Request

from app.config import get_settings


def resolve_app_root(request: Request) -> str:
    """Return path prefix without trailing slash, e.g. ``/technodt`` or ``''``."""
    prefix = (request.headers.get("X-Forwarded-Prefix") or "").strip().rstrip("/")
    if prefix:
        return prefix
    settings = get_settings()
    if settings.qr_base_url.strip():
        path = urlparse(settings.qr_base_url.strip()).path.rstrip("/")
        if path and path != "/":
            return path
    return ""


def app_url(request: Request, path: str) -> str:
    """Build an absolute app path respecting the proxy prefix."""
    if not path.startswith("/"):
        path = f"/{path}"
    root = resolve_app_root(request)
    return f"{root}{path}" if root else path
