import socket

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions import AppError
from app.models import Printer
from app.schemas.printer import PrinterCreate, PrinterOut, PrinterPatch


def _clean(value: str | None) -> str | None:
    if value is None:
        return None
    value = value.strip()
    return value or None


def _validate_printer(printer: PrinterCreate | PrinterPatch, *, current_kind: str | None = None) -> None:
    kind = printer.kind or current_kind
    host = _clean(printer.host) if hasattr(printer, "host") else None
    share_name = _clean(printer.share_name) if hasattr(printer, "share_name") else None
    if kind == "zpl":
        if isinstance(printer, PrinterCreate) and (not host or not printer.port):
            raise AppError("Для ZPL-принтера нужны IP и порт", status_code=400, code="printer_invalid")
    elif kind == "a4":
        if isinstance(printer, PrinterCreate) and not share_name:
            raise AppError("Для A4-принтера нужен Windows share", status_code=400, code="printer_invalid")
    elif kind is not None:
        raise AppError("Неизвестный тип принтера", status_code=400, code="printer_invalid")


def to_schema(printer: Printer) -> PrinterOut:
    return PrinterOut.model_validate(
        {
            "id": printer.id,
            "name": printer.name,
            "kind": printer.kind,
            "is_active": printer.is_active,
            "host": printer.host,
            "port": printer.port,
            "dpi": printer.dpi,
            "share_name": printer.share_name,
        }
    )


async def list_printers(session: AsyncSession, *, active_only: bool = True) -> list[PrinterOut]:
    stmt = select(Printer).order_by(Printer.kind, Printer.name)
    if active_only:
        stmt = stmt.where(Printer.is_active.is_(True))
    rows = (await session.execute(stmt)).scalars().all()
    return [to_schema(row) for row in rows]


async def get_printer(session: AsyncSession, printer_id: str, *, active_only: bool = False) -> Printer:
    stmt = select(Printer).where(Printer.id == printer_id)
    if active_only:
        stmt = stmt.where(Printer.is_active.is_(True))
    printer = (await session.execute(stmt)).scalar_one_or_none()
    if printer is None:
        raise AppError("Принтер не найден", status_code=404, code="printer_not_found")
    return printer


async def create_printer(session: AsyncSession, data: PrinterCreate) -> Printer:
    _validate_printer(data)
    printer = Printer(
        id=data.id.strip(),
        name=data.name.strip(),
        kind=data.kind,
        is_active=data.is_active,
        host=_clean(data.host),
        port=data.port,
        dpi=data.dpi,
        share_name=_clean(data.share_name),
    )
    session.add(printer)
    try:
        await session.flush()
    except IntegrityError as exc:
        await session.rollback()
        raise AppError("Принтер с таким ID уже существует", status_code=409, code="printer_exists") from exc
    return printer


async def patch_printer(session: AsyncSession, printer_id: str, data: PrinterPatch) -> Printer:
    printer = await get_printer(session, printer_id)
    _validate_printer(data, current_kind=printer.kind)
    changes = data.model_dump(exclude_unset=True)
    for key, value in changes.items():
        if key in {"host", "share_name"}:
            value = _clean(value)
        if key == "name" and isinstance(value, str):
            value = value.strip()
        setattr(printer, key, value)
    await session.flush()
    return printer


async def delete_printer(session: AsyncSession, printer_id: str) -> None:
    printer = await get_printer(session, printer_id)
    await session.delete(printer)
    await session.flush()


def send_zpl(printer: Printer | PrinterOut, payload: str, timeout: float = 5.0) -> None:
    if printer.kind != "zpl" or not printer.host or not printer.port:
        raise AppError("Принтер не поддерживает ZPL", status_code=400, code="printer_not_zpl")

    try:
        with socket.create_connection((printer.host, printer.port), timeout=timeout) as conn:
            conn.sendall(payload.encode("utf-8"))
    except OSError as exc:
        raise AppError("Принтер не отвечает", status_code=502, code="printer_unavailable") from exc
