import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Branch, Signer
from app.services.audit import write_event


async def list_branches(session: AsyncSession, *, only_active: bool) -> list[Branch]:
    stmt = select(Branch).order_by(Branch.name)
    if only_active:
        stmt = stmt.where(Branch.is_active.is_(True))
    return list((await session.execute(stmt)).scalars().all())


async def create_branch(session: AsyncSession, *, name: str, operator: str) -> Branch:
    b = Branch(name=name)
    session.add(b)
    await session.flush()
    await write_event(session, envelope_id=None, event="dictionary_change", actor=operator,
                      payload={"entity": "branch", "action": "create", "id": str(b.id), "name": name})
    return b


async def patch_branch(session: AsyncSession, *, branch_id: uuid.UUID,
                       is_active: bool | None, name: str | None, operator: str) -> Branch:
    b = (await session.execute(select(Branch).where(Branch.id == branch_id))).scalar_one()
    changes = {}
    if is_active is not None:
        b.is_active = is_active
        changes["is_active"] = is_active
    if name is not None:
        b.name = name
        changes["name"] = name
    await write_event(session, envelope_id=None, event="dictionary_change", actor=operator,
                      payload={"entity": "branch", "action": "patch", "id": str(b.id), "changes": changes})
    return b


async def list_signers(session: AsyncSession, *, only_active: bool) -> list[Signer]:
    stmt = select(Signer).order_by(Signer.last_name, Signer.first_name)
    if only_active:
        stmt = stmt.where(Signer.is_active.is_(True))
    return list((await session.execute(stmt)).scalars().all())


async def create_signer(session: AsyncSession, *, last_name: str, first_name: str, operator: str) -> Signer:
    s = Signer(last_name=last_name, first_name=first_name)
    session.add(s)
    await session.flush()
    await write_event(session, envelope_id=None, event="dictionary_change", actor=operator,
                      payload={"entity": "signer", "action": "create", "id": str(s.id)})
    return s


async def patch_signer(session: AsyncSession, *, signer_id: uuid.UUID,
                       last_name: str | None, first_name: str | None,
                       is_active: bool | None, operator: str) -> Signer:
    s = (await session.execute(select(Signer).where(Signer.id == signer_id))).scalar_one()
    changes: dict = {}
    if last_name is not None:
        s.last_name = last_name; changes["last_name"] = last_name
    if first_name is not None:
        s.first_name = first_name; changes["first_name"] = first_name
    if is_active is not None:
        s.is_active = is_active; changes["is_active"] = is_active
    await write_event(session, envelope_id=None, event="dictionary_change", actor=operator,
                      payload={"entity": "signer", "action": "patch", "id": str(s.id), "changes": changes})
    return s
