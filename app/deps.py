"""Dependency providers extracted from app.main to break circular imports."""
from app.services.odata import OneCClient


def get_one_c_client() -> OneCClient:
    raise RuntimeError("OneCClient not initialized — lifespan did not run")
