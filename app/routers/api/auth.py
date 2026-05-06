from typing import Annotated
from urllib.parse import quote, unquote

from fastapi import APIRouter, Cookie, Depends, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db import get_session
from app.exceptions import OperatorRequired
from app.models import Operator
from app.schemas.auth import LoginRequest, LoginResponse, MeResponse
from app.services.operators import authenticate_operator, ensure_operator, verify_password

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _is_bootstrap_admin(name: str) -> bool:
    settings = get_settings()
    admin_login = settings.admin_login.strip().casefold()
    return bool(admin_login) and name.strip().casefold() == admin_login


async def _get_operator(session: AsyncSession, name: str) -> Operator:
    op = await ensure_operator(session, name, bootstrap=_is_bootstrap_admin(name))
    if not op.is_active:
        raise OperatorRequired("Оператор деактивирован")
    return op


@router.post("/login", response_model=LoginResponse)
async def login(
    body: LoginRequest,
    response: Response,
    session: Annotated[AsyncSession, Depends(get_session)],
):
    name = body.username.strip()
    if not name:
        raise OperatorRequired("Введите логин")

    settings = get_settings()
    if _is_bootstrap_admin(name):
        op = await ensure_operator(
            session,
            name,
            bootstrap=True,
            password=settings.admin_password if settings.admin_password else None,
        )
        if not verify_password(body.password, op.password_hash):
            raise OperatorRequired("Неверный логин или пароль")
    else:
        op = await authenticate_operator(session, name, body.password)
        if op is None:
            raise OperatorRequired("Неверный логин или пароль")
    await session.commit()

    response.set_cookie(
        "operator_name",
        quote(name),
        max_age=settings.auth_cookie_max_age_seconds,
        httponly=True,
        samesite="lax",
    )
    return LoginResponse(
        ok=True,
        operator=name,
        assigned_zpl_printer_id=op.assigned_zpl_printer_id,
        assigned_a4_printer_id=op.assigned_a4_printer_id,
    )


@router.get("/me", response_model=MeResponse)
async def me(
    session: Annotated[AsyncSession, Depends(get_session)],
    operator_name: str | None = Cookie(default=None),
):
    if not operator_name:
        raise OperatorRequired("Требуется авторизация")

    name = unquote(operator_name).strip()
    if not name:
        raise OperatorRequired("Требуется авторизация")

    op = await _get_operator(session, name)
    await session.commit()
    return MeResponse(operator=name, is_admin=op.is_admin)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(response: Response):
    response.delete_cookie("operator_name")
    return None
