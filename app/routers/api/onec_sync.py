# app/routers/api/onec_sync.py
from datetime import date

from fastapi import APIRouter, BackgroundTasks, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import require_admin
from app.config import get_settings
from app.db import get_session
from app.deps import get_one_c_client
from app.services.onec_sync import get_sync_status, run_incremental_sync, run_initial_sync
from app.services.odata import OneCClient

router = APIRouter(prefix="/api/admin/sync", tags=["sync"])


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
    session: AsyncSession = Depends(get_session),
    client: OneCClient = Depends(get_one_c_client),
):
    settings = get_settings()
    date_from = date.fromisoformat(settings.sync_initial_from_date)

    async def _run() -> None:
        await run_initial_sync(client, session, date_from)

    background_tasks.add_task(_run)
    return {"status": "started", "date_from": str(date_from)}


@router.post("/incremental")
async def start_incremental_sync(
    background_tasks: BackgroundTasks,
    _admin: None = require_admin(),
    session: AsyncSession = Depends(get_session),
    client: OneCClient = Depends(get_one_c_client),
):
    async def _run() -> None:
        await run_incremental_sync(client, session)

    background_tasks.add_task(_run)
    return {"status": "started"}
