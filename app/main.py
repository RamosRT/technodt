import logging
from contextlib import asynccontextmanager
from pathlib import Path

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.config import get_settings
from app.db import get_session_factory
from app.deps import get_one_c_client
from app.exceptions import AppError, app_error_handler
from app.routers.api import admin as admin_api
from app.routers.api import audit as audit_api
from app.routers.api import auth as auth_api
from app.routers.api import dictionaries as dictionaries_api
from app.routers.api import documents as documents_api
from app.routers.api import envelopes as envelopes_api
from app.routers.api import health
from app.routers.api import onec_sync as onec_sync_api
from app.routers.api import operators as operators_api
from app.routers.api import report as report_api
from app.routers.api import printers as printers_api
from app.routers.api import verify as verify_api
from app.routers.api import webhooks as webhooks_api
from app.routers.ui import pages as ui_pages
from app.services.odata import OneCClient
from app.services.onec_sync import _sync_lock, run_incremental_sync

_STATIC_DIR = Path(__file__).parent / "web" / "static"

log = logging.getLogger(__name__)


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

    scheduler = None
    if s.sync_schedule_hours > 0:
        scheduler = AsyncIOScheduler()

        async def _scheduled_sync() -> None:
            if _sync_lock.locked():
                log.warning("scheduled sync: lock busy, skipping")
                return
            async with _sync_lock:
                factory = get_session_factory()
                async with factory() as session:
                    try:
                        await run_incremental_sync(client, session)
                    except Exception as exc:
                        log.error("scheduled incremental sync failed: %s", exc)

        scheduler.add_job(
            _scheduled_sync,
            "interval",
            hours=s.sync_schedule_hours,
            id="incremental_sync",
            max_instances=1,
            coalesce=True,
            misfire_grace_time=300,
        )
        scheduler.start()
        app.state.scheduler = scheduler

    try:
        yield
    finally:
        if scheduler is not None:
            scheduler.shutdown(wait=False)
        await client.aclose()


app = FastAPI(title="Конверт-трек", lifespan=lifespan)
app.add_exception_handler(AppError, app_error_handler)
app.mount("/static", StaticFiles(directory=str(_STATIC_DIR)), name="static")
app.include_router(health.router)
app.include_router(auth_api.router)
app.include_router(envelopes_api.router)
app.include_router(dictionaries_api.router)
app.include_router(verify_api.router)
app.include_router(admin_api.router)
app.include_router(operators_api.router)
app.include_router(documents_api.router)
app.include_router(audit_api.router)
app.include_router(printers_api.router)
app.include_router(onec_sync_api.router)
app.include_router(report_api.router)
app.include_router(webhooks_api.router)
app.include_router(ui_pages.router)
