from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.config import get_settings
from app.exceptions import AppError, app_error_handler
from app.routers.api import health
from app.services.odata import OneCClient


def get_one_c_client() -> OneCClient:
    """Dependency override target. Real client lives on app.state."""
    raise RuntimeError("OneCClient not initialized — lifespan did not run")


@asynccontextmanager
async def lifespan(app: FastAPI):
    s = get_settings()
    client = OneCClient(
        base_url=s.odata_base_url,
        user=s.odata_admin_user,
        password=s.odata_password,
        timeout=s.odata_timeout_seconds,
    )
    app.state.one_c = client
    app.dependency_overrides[get_one_c_client] = lambda: app.state.one_c
    try:
        yield
    finally:
        await client.aclose()


app = FastAPI(title="Конверт-трек", lifespan=lifespan)
app.add_exception_handler(AppError, app_error_handler)
app.include_router(health.router)
