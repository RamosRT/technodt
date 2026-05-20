import logging

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import require_admin
from app.config import get_settings
from app.db import get_session, get_session_factory
from app.deps import get_one_c_client
from app.services.onec_sync import _sync_lock, get_sync_status, run_incremental_sync, run_initial_sync
from app.services.odata import OneCClient

router = APIRouter(prefix="/api/admin/sync", tags=["sync"])
log = logging.getLogger(__name__)


@router.get("/status")
async def sync_status(
    _admin: None = require_admin(),
    session: AsyncSession = Depends(get_session),
):
    return await get_sync_status(session)


@router.post("/initial")
async def start_initial_sync(
    background_tasks: BackgroundTasks,
    _admin: None = require_admin(),
    client: OneCClient = Depends(get_one_c_client),
):
    if _sync_lock.locked():
        raise HTTPException(status_code=409, detail="sync already running")
    settings = get_settings()
    date_from = settings.sync_initial_from_date
    factory = get_session_factory()

    async def _run() -> None:
        if _sync_lock.locked():
            log.warning("initial sync: lock busy, skipping")
            return
        async with _sync_lock:
            async with factory() as session:
                try:
                    await run_initial_sync(client, session, date_from)
                except Exception:
                    log.exception("initial sync failed")

    background_tasks.add_task(_run)
    return {"status": "started", "date_from": str(date_from)}


@router.post("/incremental")
async def start_incremental_sync(
    background_tasks: BackgroundTasks,
    _admin: None = require_admin(),
    client: OneCClient = Depends(get_one_c_client),
):
    if _sync_lock.locked():
        raise HTTPException(status_code=409, detail="sync already running")
    factory = get_session_factory()

    async def _run() -> None:
        if _sync_lock.locked():
            log.warning("incremental sync: lock busy, skipping")
            return
        async with _sync_lock:
            async with factory() as session:
                try:
                    await run_incremental_sync(client, session)
                except Exception:
                    log.exception("incremental sync failed")

    background_tasks.add_task(_run)
    return {"status": "started"}
