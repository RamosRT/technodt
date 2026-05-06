import asyncio
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import require_admin, require_operator
from app.db import get_session
from app.exceptions import AppError
from app.schemas.printer import PrinterCreate, PrinterListResponse, PrinterOut, PrinterPatch
from app.services import envelopes as envelope_svc
from app.services import printers as printer_svc
from app.services import printing

router = APIRouter(tags=["printers"])
SessionDep = Annotated[AsyncSession, Depends(get_session)]
PrinterIdQuery = Annotated[str, Query(min_length=1)]


@router.get("/api/printers", response_model=PrinterListResponse)
async def list_printers(session: SessionDep, _operator: str = require_operator()):
    return PrinterListResponse(items=await printer_svc.list_printers(session, active_only=True))


@router.get("/api/admin/printers", response_model=PrinterListResponse)
async def admin_list_printers(
    session: SessionDep,
    _admin: None = require_admin(),
):
    return PrinterListResponse(items=await printer_svc.list_printers(session, active_only=False))


@router.post("/api/admin/printers", response_model=PrinterOut, status_code=status.HTTP_201_CREATED)
async def admin_create_printer(
    body: PrinterCreate,
    session: SessionDep,
    _admin: None = require_admin(),
):
    printer = await printer_svc.create_printer(session, body)
    await session.commit()
    return printer_svc.to_schema(printer)


@router.patch("/api/admin/printers/{printer_id}", response_model=PrinterOut)
async def admin_patch_printer(
    printer_id: str,
    body: PrinterPatch,
    session: SessionDep,
    _admin: None = require_admin(),
):
    printer = await printer_svc.patch_printer(session, printer_id, body)
    await session.commit()
    return printer_svc.to_schema(printer)


@router.delete("/api/admin/printers/{printer_id}", status_code=status.HTTP_204_NO_CONTENT)
async def admin_delete_printer(
    printer_id: str,
    session: SessionDep,
    _admin: None = require_admin(),
):
    await printer_svc.delete_printer(session, printer_id)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


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
    printer = await printer_svc.get_printer(session, printer_id, active_only=True)
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
    printer = await printer_svc.get_printer(session, printer_id, active_only=True)
    if printer.kind != "a4":
        raise AppError("Опись доступна только для A4-принтера", status_code=400, code="printer_not_a4")
    await printing.send_inventory_to_a4_printer(session, envelope_id, printer)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
