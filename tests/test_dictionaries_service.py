import pytest

from app.services import dictionaries as svc
from app.models import Branch, Signer


@pytest.mark.asyncio
async def test_branches_create_list_patch(db_session):
    b = await svc.create_branch(db_session, name="Москва", operator="A")
    await db_session.commit()
    assert b.is_active is True

    listed = await svc.list_branches(db_session, only_active=True)
    assert [x.id for x in listed] == [b.id]

    await svc.patch_branch(db_session, branch_id=b.id, is_active=False, name=None, operator="A")
    await db_session.commit()
    listed_active = await svc.list_branches(db_session, only_active=True)
    assert listed_active == []
    listed_all = await svc.list_branches(db_session, only_active=False)
    assert len(listed_all) == 1


@pytest.mark.asyncio
async def test_signers_create_list_patch(db_session):
    s = await svc.create_signer(db_session, last_name="Иванов", first_name="Иван", operator="A")
    await db_session.commit()
    listed = await svc.list_signers(db_session, only_active=True)
    assert [x.id for x in listed] == [s.id]

    await svc.patch_signer(db_session, signer_id=s.id, last_name="Петров",
                           first_name=None, is_active=None, operator="A")
    await db_session.commit()
    refreshed = (await svc.list_signers(db_session, only_active=True))[0]
    assert refreshed.last_name == "Петров"
