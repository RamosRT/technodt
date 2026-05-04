import asyncio
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import require_operator
from app.config import get_settings
from app.db import get_session
from app.exceptions import AppError
from app.schemas.printer import PrinterListResponse
from app.services import envelopes as envelope_svc
from app.services import printers as printer_svc
from app.services import printing

router = APIRouter(tags=["printers"])
SessionDep = Annotated[AsyncSession, Depends(get_session)]
PrinterIdQuery = Annotated[str, Query(min_length=1)]


@router.get("/api/printers", response_model=PrinterListResponse)
async def list_printers(_operator: str = require_operator()):
    return PrinterListResponse(items=printer_svc.list_printers(get_settings()))


@router.post(
    "/api/envelopes/{envelope_id}/print/label/send",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def send_label_to_printer(
    envelope_id: uuid.UUID,
    printer_id: PrinterIdQuery,
    session: SessionDep,
    _operator: str = require_operator(),
):
    printer = printer_svc.get_printer(get_settings(), printer_id)
    if printer.kind != "zpl":
        raise AppError("Этикетка доступна только для ZPL-принтера", status_code=400, code="printer_not_zpl")

    envelope = await envelope_svc.get_by_id(session, envelope_id)
    zpl = printing.render_label_zpl(envelope, dpi=printer.dpi or 200)
    await asyncio.to_thread(printer_svc.send_zpl, printer, zpl)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/api/envelopes/{envelope_id}/print/inventory/send")
async def send_inventory_to_printer(
    envelope_id: uuid.UUID,
    printer_id: PrinterIdQuery,
    session: SessionDep,
    _operator: str = require_operator(),
):
    await envelope_svc.get_by_id(session, envelope_id)
    printer_svc.get_printer(get_settings(), printer_id)
    raise AppError(
        "Печать описи с ТСД пока не настроена",
        status_code=501,
        code="inventory_print_not_implemented",
    )
