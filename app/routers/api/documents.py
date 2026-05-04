import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import require_operator
from app.db import get_session
from app.parsing import optional_query_date
from app.services.documents import build_documents_csv, list_documents

router = APIRouter(prefix="/api/documents", tags=["documents"])


@router.get("")
async def get_documents(
    date_from_raw: Annotated[str | None, Query(alias="date_from")] = None,
    date_to_raw: Annotated[str | None, Query(alias="date_to")] = None,
    doc_kind: str | None = None,
    status: str | None = None,
    branch_id: str | None = None,
    search: str | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    _operator: str = require_operator(),
    session: AsyncSession = Depends(get_session),
):
    date_from = optional_query_date(date_from_raw)
    date_to = optional_query_date(date_to_raw)
    branch_uuid = uuid.UUID(branch_id) if branch_id else None
    status_value = status or None
    items, total, summary = await list_documents(
        session,
        date_from=date_from,
        date_to=date_to,
        doc_kind=doc_kind,
        status=status_value,
        branch_id=branch_uuid,
        search=search,
        page=page,
        page_size=page_size,
    )
    return {"items": items, "total": total, "summary": summary, "page": page, "page_size": page_size}


@router.get("/export")
async def export_documents(
    date_from_raw: Annotated[str | None, Query(alias="date_from")] = None,
    date_to_raw: Annotated[str | None, Query(alias="date_to")] = None,
    doc_kind: str | None = None,
    status: str | None = None,
    branch_id: str | None = None,
    search: str | None = None,
    _operator: str = require_operator(),
    session: AsyncSession = Depends(get_session),
):
    date_from = optional_query_date(date_from_raw)
    date_to = optional_query_date(date_to_raw)
    branch_uuid = uuid.UUID(branch_id) if branch_id else None
    status_value = status or None
    items, _, _ = await list_documents(
        session,
        date_from=date_from,
        date_to=date_to,
        doc_kind=doc_kind,
        status=status_value,
        branch_id=branch_uuid,
        search=search,
        page=1,
        page_size=10000,
    )
    csv_body = build_documents_csv(items)
    return Response(
        content="\ufeff" + csv_body,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="documents.csv"'},
    )
