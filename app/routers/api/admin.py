from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import require_admin
from app.config import Settings, get_settings
from app.db import get_session
from app.deps import get_one_c_client
from app.services.odata import OneCClient
from app.services.paperless_tag_sync import (
    PaperlessTagClient,
    _paperless_tag_lock,
    process_paperless_marked_documents,
)

router = APIRouter(prefix="/api/admin", tags=["admin"])


class ResetRequest(BaseModel):
    confirm: str = ""


@router.post("/reset")
async def admin_reset(
    body: ResetRequest,
    _admin: None = require_admin(),
    session: AsyncSession = Depends(get_session),
):
    if get_settings().env == "production":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    if body.confirm != "I_KNOW_WHAT_I_DO":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="confirm phrase missing")
    for tbl in ("audit_log", "envelope_documents", "envelopes", "signers", "branches"):
        await session.execute(text(f"TRUNCATE TABLE {tbl} RESTART IDENTITY CASCADE"))
    await session.commit()
    return {"reset": True}


@router.post("/paperless/tag-sync")
async def admin_paperless_tag_sync(
    _admin: None = require_admin(),
    session: AsyncSession = Depends(get_session),
    client: OneCClient = Depends(get_one_c_client),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    """Run Paperless mark-tag processing synchronously and return per-document results."""
    if not settings.paperless_api_url or not settings.paperless_api_token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="PAPERLESS_API_URL / PAPERLESS_API_TOKEN are not configured",
        )
    if not settings.paperless_onec_originals_unc_root:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="PAPERLESS_ONEC_ORIGINALS_UNC_ROOT is not configured",
        )
    if _paperless_tag_lock.locked():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Paperless tag sync is already running",
        )

    async with _paperless_tag_lock:
        paperless_client = PaperlessTagClient(
            base_url=settings.paperless_api_url,
            token=settings.paperless_api_token,
        )
        try:
            return await process_paperless_marked_documents(
                session,
                client,
                paperless_client,
                settings,
            )
        finally:
            await paperless_client.aclose()
