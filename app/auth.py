from urllib.parse import unquote

from fastapi import Cookie, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db import get_session
from app.exceptions import AdminTokenInvalid, OperatorRequired
from app.models import Operator
from app.services.operators import ensure_operator


def require_operator():
    async def dep(
        operator_name: str | None = Cookie(default=None),
        session: AsyncSession = Depends(get_session),
    ) -> str:
        if not operator_name:
            raise OperatorRequired("Введите имя оператора")

        name = unquote(operator_name).strip()
        if not name:
            raise OperatorRequired("Введите имя оператора")

        settings = get_settings()
        is_bootstrap = bool(settings.bootstrap_admin) and name == settings.bootstrap_admin
        op = await ensure_operator(session, name, bootstrap=is_bootstrap)
        if not op.is_active:
            raise OperatorRequired("Оператор деактивирован")
        return name

    return Depends(dep)


def require_admin():
    async def dep(
        operator_name: str | None = Cookie(default=None),
        session: AsyncSession = Depends(get_session),
    ) -> None:
        if not operator_name:
            raise AdminTokenInvalid("Требуется авторизация администратора")

        name = unquote(operator_name).strip()
        settings = get_settings()
        if settings.bootstrap_admin and name == settings.bootstrap_admin:
            op = await ensure_operator(session, name, bootstrap=True)
        else:
            op = (
                await session.execute(
                    select(Operator).where(
                        Operator.username == name,
                        Operator.is_admin.is_(True),
                        Operator.is_active.is_(True),
                    )
                )
            ).scalar_one_or_none()

        if op is None or not op.is_admin or not op.is_active:
            raise AdminTokenInvalid("Нет прав администратора")

    return Depends(dep)


async def get_is_admin(
    operator_name: str | None = Cookie(default=None),
    session: AsyncSession = Depends(get_session),
) -> bool:
    if not operator_name:
        return False

    name = unquote(operator_name).strip()
    settings = get_settings()
    if settings.bootstrap_admin and name == settings.bootstrap_admin:
        op = await ensure_operator(session, name, bootstrap=True)
        return op.is_active

    op = (
        await session.execute(
            select(Operator).where(
                Operator.username == name,
                Operator.is_admin.is_(True),
                Operator.is_active.is_(True),
            )
        )
    ).scalar_one_or_none()
    return op is not None
