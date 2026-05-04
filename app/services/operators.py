import base64
import hashlib
import hmac
import os
import uuid

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Operator

_HASH_PREFIX = "pbkdf2_sha256"
_HASH_ITERATIONS = 210_000


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, _HASH_ITERATIONS)
    return "$".join(
        (
            _HASH_PREFIX,
            str(_HASH_ITERATIONS),
            base64.b64encode(salt).decode("ascii"),
            base64.b64encode(digest).decode("ascii"),
        )
    )


def verify_password(password: str, password_hash: str | None) -> bool:
    if not password_hash:
        return False
    try:
        prefix, iterations_raw, salt_raw, digest_raw = password_hash.split("$", 3)
        if prefix != _HASH_PREFIX:
            return False
        salt = base64.b64decode(salt_raw.encode("ascii"))
        expected = base64.b64decode(digest_raw.encode("ascii"))
        actual = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, int(iterations_raw))
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(actual, expected)


async def ensure_operator(
    session: AsyncSession,
    username: str,
    *,
    bootstrap: bool = False,
    password: str | None = None,
    assigned_zpl_printer_id: str | None = None,
) -> Operator:
    username = username.strip()
    op = (
        await session.execute(select(Operator).where(Operator.username == username))
    ).scalar_one_or_none()
    if op is not None:
        if bootstrap and not op.is_admin:
            op.is_admin = True
        if password is not None:
            op.password_hash = hash_password(password)
        if assigned_zpl_printer_id is not None:
            op.assigned_zpl_printer_id = assigned_zpl_printer_id or None
        if bootstrap or password is not None or assigned_zpl_printer_id is not None:
            await session.flush()
        return op

    op = Operator(
        username=username,
        is_admin=bootstrap,
        password_hash=hash_password(password) if password is not None else None,
        assigned_zpl_printer_id=assigned_zpl_printer_id or None,
    )
    session.add(op)
    try:
        await session.flush()
    except IntegrityError:
        await session.rollback()
        op = (
            await session.execute(select(Operator).where(Operator.username == username))
        ).scalar_one()
        if bootstrap and not op.is_admin:
            op.is_admin = True
            await session.flush()
    return op


async def list_operators(session: AsyncSession) -> list[Operator]:
    result = await session.execute(select(Operator).order_by(Operator.username))
    return list(result.scalars().all())


async def patch_operator(
    session: AsyncSession,
    *,
    operator_id: uuid.UUID,
    is_admin: bool | None,
    is_active: bool | None,
    password: str | None = None,
    assigned_zpl_printer_id: str | None = None,
) -> Operator:
    op = (
        await session.execute(select(Operator).where(Operator.id == operator_id))
    ).scalar_one()
    if is_admin is not None:
        op.is_admin = is_admin
    if is_active is not None:
        op.is_active = is_active
    if password is not None:
        op.password_hash = hash_password(password)
    if assigned_zpl_printer_id is not None:
        op.assigned_zpl_printer_id = assigned_zpl_printer_id or None
    await session.flush()
    return op


async def delete_operator(session: AsyncSession, *, operator_id: uuid.UUID) -> bool:
    op = (
        await session.execute(select(Operator).where(Operator.id == operator_id))
    ).scalar_one_or_none()
    if op is None:
        return False
    await session.delete(op)
    await session.flush()
    return True


async def authenticate_operator(session: AsyncSession, username: str, password: str) -> Operator | None:
    op = (
        await session.execute(select(Operator).where(Operator.username == username.strip()))
    ).scalar_one_or_none()
    if op is None or not op.is_active or not verify_password(password, op.password_hash):
        return None
    return op
