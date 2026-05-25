from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import require_operator
from app.db import get_session
from app.parsing import optional_query_date
from app.schemas.report import ReportDocumentRow, ReportResponse
from app.services.report import build_report_documents_csv, list_report_documents

router = APIRouter(prefix="/api/report", tags=["report"])


@router.get("/documents", response_model=ReportResponse)
async def documents_report(
    _op: Annotated[str, require_operator()],
    session: Annotated[AsyncSession, Depends(get_session)],
    date_from_raw: Annotated[str | None, Query(alias="date_from")] = None,
    date_to_raw: Annotated[str | None, Query(alias="date_to")] = None,
    partner: Annotated[str | None, Query()] = None,
    number: Annotated[str | None, Query()] = None,
    only_archived: Annotated[bool, Query()] = False,
    only_without_envelope: Annotated[bool, Query()] = False,
    only_without_edo: Annotated[bool, Query()] = False,
    format: Annotated[str, Query(pattern="^(json|csv)$")] = "json",
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=10000)] = 50,
):
    date_from = optional_query_date(date_from_raw)
    date_to = optional_query_date(date_to_raw)
    items, total = await list_report_documents(
        session,
        date_from=date_from,
        date_to=date_to,
        partner_search=partner,
        number_search=number,
        only_archived=only_archived,
        only_without_envelope=only_without_envelope,
        only_without_edo=only_without_edo,
        page=page,
        page_size=page_size,
    )
    if format == "csv":
        csv_body = build_report_documents_csv(items)
        return Response(
            content="\ufeff" + csv_body,
            media_type="text/csv; charset=utf-8",
            headers={"Content-Disposition": 'attachment; filename="document-report.csv"'},
        )
    return ReportResponse(
        items=[ReportDocumentRow(**item) for item in items],
        total=total,
        page=page,
        page_size=page_size,
    )
