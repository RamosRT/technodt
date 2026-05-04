import json
import socket

from pydantic import ValidationError

from app.config import Settings
from app.exceptions import AppError
from app.schemas.printer import PrinterOut


def list_printers(settings: Settings) -> list[PrinterOut]:
    try:
        raw = json.loads(settings.printers_json or "[]")
        if not isinstance(raw, list):
            raise ValueError("PRINTERS_JSON must contain a list")
        return [PrinterOut.model_validate(item) for item in raw]
    except (json.JSONDecodeError, TypeError, ValueError, ValidationError) as exc:
        raise AppError(
            "Некорректная конфигурация принтеров",
            status_code=500,
            code="printer_config_invalid",
        ) from exc


def get_printer(settings: Settings, printer_id: str) -> PrinterOut:
    for printer in list_printers(settings):
        if printer.id == printer_id:
            return printer
    raise AppError("Принтер не найден", status_code=404, code="printer_not_found")


def send_zpl(printer: PrinterOut, payload: str, timeout: float = 5.0) -> None:
    if printer.kind != "zpl" or not printer.host or not printer.port:
        raise AppError("Принтер не поддерживает ZPL", status_code=400, code="printer_not_zpl")

    try:
        with socket.create_connection((printer.host, printer.port), timeout=timeout) as conn:
            conn.sendall(payload.encode("utf-8"))
    except OSError as exc:
        raise AppError("Принтер не отвечает", status_code=502, code="printer_unavailable") from exc
