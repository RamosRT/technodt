from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.config import get_settings
from app.deps import get_one_c_client
from app.exceptions import AppError, app_error_handler
from app.routers.api import health
from app.routers.api import envelopes as envelopes_api
from app.routers.api import dictionaries as dictionaries_api
from app.routers.api import verify as verify_api
from app.routers.api import admin as admin_api
from app.services.odata import OneCClient


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
app.include_router(envelopes_api.router)
app.include_router(dictionaries_api.router)
app.include_router(verify_api.router)
app.include_router(admin_api.router)
