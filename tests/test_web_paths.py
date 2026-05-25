from unittest.mock import MagicMock

from app.web_paths import app_url, resolve_app_root


def test_resolve_app_root_from_qr_base_url(monkeypatch):
    monkeypatch.setenv("QR_BASE_URL", "https://kaz-app01-pub.technoavia.ru/technodt")
    monkeypatch.setenv("ENV", "production")
    from app.config import get_settings

    get_settings.cache_clear()
    request = MagicMock()
    request.headers.get.return_value = None
    assert resolve_app_root(request) == "/technodt"
    assert app_url(request, "/") == "/technodt/"


def test_resolve_app_root_from_forwarded_prefix(monkeypatch):
    monkeypatch.setenv("QR_BASE_URL", "")
    from app.config import get_settings

    get_settings.cache_clear()
    request = MagicMock()
    request.headers.get.return_value = "/technodt"
    assert resolve_app_root(request) == "/technodt"
