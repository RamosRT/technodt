import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import require_admin
from app.db import get_session
from app.schemas.operator import OperatorCreate, OperatorOut, OperatorPatch
from app.services import printing
from app.services.operators import delete_operator, ensure_operator, list_operators, patch_operator

router = APIRouter(prefix="/api/operators", tags=["operators"])


def _mm_to_dots(mm: int, dpi: int = 200) -> int:
    return round(mm / 25.4 * dpi)


def _zpl_text(value: str) -> str:
    return value.replace("^", " ").replace("~", " ")


@router.get("", response_model=list[OperatorOut])
async def get_operators(
    _admin: None = require_admin(),
    session: AsyncSession = Depends(get_session),
):
    return await list_operators(session)


@router.post("", response_model=OperatorOut, status_code=status.HTTP_201_CREATED)
async def create_operator(
    body: OperatorCreate,
    _admin: None = require_admin(),
    session: AsyncSession = Depends(get_session),
):
    op = await ensure_operator(
        session,
        body.username,
        bootstrap=body.is_admin,
        password=body.password,
        assigned_zpl_printer_id=body.assigned_zpl_printer_id,
    )
    await session.commit()
    return op


@router.patch("/{operator_id}", response_model=OperatorOut)
async def update_operator(
    operator_id: uuid.UUID,
    body: OperatorPatch,
    _admin: None = require_admin(),
    session: AsyncSession = Depends(get_session),
):
    op = await patch_operator(
        session,
        operator_id=operator_id,
        password=body.password,
        is_admin=body.is_admin,
        is_active=body.is_active,
        assigned_zpl_printer_id=body.assigned_zpl_printer_id,
    )
    await session.commit()
    return op


@router.delete("/{operator_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_operator(
    operator_id: uuid.UUID,
    _admin: None = require_admin(),
    session: AsyncSession = Depends(get_session),
):
    deleted = await delete_operator(session, operator_id=operator_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Оператор не найден")
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{operator_id}/auth-label.zpl")
async def operator_auth_label_zpl(
    operator_id: uuid.UUID,
    server_url: str = Query(..., min_length=1),
    password: str = Query(..., min_length=4, max_length=4, pattern=r"^\d{4}$"),
    _admin: None = require_admin(),
    session: AsyncSession = Depends(get_session),
):
    operators = await list_operators(session)
    op = next((item for item in operators if item.id == operator_id), None)
    if op is None:
        return Response("Оператор не найден", status_code=404)
    payload = _zpl_text(f"KTLOGIN|{server_url.strip()}|{op.username}|{password}")
    zpl = "\n".join(
        (
            "^XA",
            f"^PW{_mm_to_dots(100)}",
            f"^LL{_mm_to_dots(50)}",
            "^CI28",
            "^FO24,24^BQN,2,7^FDLA," + payload + "^FS",
            "^FO300,36^A0N,28,28^FDВход ТСД^FS",
            f"^FO300,76^A0N,24,24^FD{_zpl_text(op.username[:24])}^FS",
            "^FO300,116^A0N,20,20^FDСканируйте на экране входа^FS",
            "^XZ",
        )
    )
    return Response(zpl, media_type="application/octet-stream")


@router.get("/{operator_id}/auth-label.pdf")
async def operator_auth_label_pdf(
    operator_id: uuid.UUID,
    server_url: str = Query(..., min_length=1),
    password: str = Query(..., min_length=4, max_length=4, pattern=r"^\d{4}$"),
    _admin: None = require_admin(),
    session: AsyncSession = Depends(get_session),
):
    operators = await list_operators(session)
    op = next((item for item in operators if item.id == operator_id), None)
    if op is None:
        return Response("Оператор не найден", status_code=404)
    pdf = await printing.render_operator_auth_label_pdf(
        server_url=server_url,
        username=op.username,
        password=password,
    )
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": 'inline; filename="auth-label.pdf"'},
    )
