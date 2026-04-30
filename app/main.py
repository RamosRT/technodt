from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.config import get_settings
from app.deps import get_one_c_client
from app.exceptions import AppError, app_error_handler
from app.routers.api import health
from app.routers.api import envelopes as envelopes_api
from app.routers.api import dictionaries as dictionaries_api
from app.routers.api import verify as verify_api
from app.routers.api import admin as admin_api
from app.routers.api import operators as operators_api
from app.routers.api import documents as documents_api
from app.routers.api import audit as audit_api
from app.routers.ui import pages as ui_pages
from app.services.odata import OneCClient

_STATIC_DIR = Path(__file__).parent / "web" / "static"


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
app.mount("/static", StaticFiles(directory=str(_STATIC_DIR)), name="static")
app.include_router(health.router)
app.include_router(envelopes_api.router)
app.include_router(dictionaries_api.router)
app.include_router(verify_api.router)
app.include_router(admin_api.router)
app.include_router(operators_api.router)
app.include_router(documents_api.router)
app.include_router(audit_api.router)
app.include_router(ui_pages.router)
