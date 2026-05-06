
import pytest
from sqlalchemy import select

from app.models import AuditLog, Envelope
from app.services.audit import write_event


@pytest.mark.asyncio
async def test_write_event_persists_row(db_session):
    # Create an envelope first to satisfy FK constraint
    env = Envelope(barcode="TEST-001", number="001", status="draft", created_by="admin")
    db_session.add(env)
    await db_session.flush()

    await write_event(db_session, envelope_id=env.id, event="create", actor="ramos", payload={"x": 1})
    await db_session.commit()
    rows = (await db_session.execute(select(AuditLog))).scalars().all()
    assert len(rows) == 1
    assert rows[0].event == "create"
    assert rows[0].actor == "ramos"
    assert rows[0].envelope_id == env.id
    assert rows[0].payload == {"x": 1}


@pytest.mark.asyncio
async def test_write_event_default_actor_and_payload(db_session):
    await write_event(db_session, envelope_id=None, event="dictionary_change")
    await db_session.commit()
    row = (await db_session.execute(select(AuditLog))).scalar_one()
    assert row.actor == "system"
    assert row.payload == {}
    assert row.envelope_id is None
