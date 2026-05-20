from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import require_operator
from app.db import get_session
from app.schemas.report import ReportDocumentRow, ReportResponse
from app.services.report import list_report_documents

router = APIRouter(prefix="/api/report", tags=["report"])


@router.get("/documents", response_model=ReportResponse)
async def documents_report(
    _op: str = require_operator(),
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    partner: Optional[str] = Query(None),
    number: Optional[str] = Query(None),
    only_archived: bool = Query(False),
    only_without_envelope: bool = Query(False),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    session: AsyncSession = Depends(get_session),
):
    items, total = await list_report_documents(
        session,
        date_from=date_from,
        date_to=date_to,
        partner_search=partner,
        number_search=number,
        only_archived=only_archived,
        only_without_envelope=only_without_envelope,
        page=page,
        page_size=page_size,
    )
    return ReportResponse(
        items=[ReportDocumentRow(**item) for item in items],
        total=total,
        page=page,
        page_size=page_size,
    )
