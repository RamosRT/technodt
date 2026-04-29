from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import require_admin
from app.config import get_settings
from app.db import get_session

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
