from fastapi import Cookie, Header

from app.config import get_settings
from app.exceptions import AdminTokenInvalid, OperatorRequired


def require_operator():
    async def dep(operator_name: str | None = Cookie(default=None)) -> str:
        if not operator_name:
            raise OperatorRequired("Введите имя оператора")
        return operator_name

    from fastapi import Depends
    return Depends(dep)


def require_admin():
    async def dep(x_admin_token: str | None = Header(default=None)) -> None:
        expected = get_settings().admin_token
        if not x_admin_token or x_admin_token != expected:
            raise AdminTokenInvalid("Неверный токен администратора")

    from fastapi import Depends
    return Depends(dep)
