import uuid
from datetime import date as _date
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import select

from app.models import AuditLog, Envelope, EnvelopeDocument, EnvelopeStatus
from app.services import envelopes as svc
from app.services.odata import NormalizedDocument


# ---------------------------------------------------------------------------
# Task 15: create_envelope
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_envelope_returns_draft_with_codes(db_session):
    env = await svc.create_envelope(db_session, operator="Иван")
    await db_session.commit()
    assert env.status == EnvelopeStatus.draft
    assert env.created_by == "Иван"
    assert env.number.startswith("ТА-")
    assert env.barcode and env.barcode.isdigit()
    assert env.number == f"ТА-{env.barcode}"

    saved = (await db_session.execute(select(Envelope))).scalar_one()
    assert saved.id == env.id

    audits = (await db_session.execute(select(AuditLog))).scalars().all()
    assert len(audits) == 1
    assert audits[0].event == "create"
    assert audits[0].actor == "Иван"
    assert audits[0].envelope_id == env.id


@pytest.mark.asyncio
async def test_create_envelope_discards_previous_empty_drafts_for_operator(db_session):
    old = await svc.create_envelope(db_session, operator="Иван")
    await db_session.commit()

    new = await svc.create_envelope(db_session, operator="Иван")
    await db_session.commit()

    envelopes = (await db_session.execute(select(Envelope))).scalars().all()
    audits = (await db_session.execute(select(AuditLog))).scalars().all()
    assert [env.id for env in envelopes] == [new.id]
    assert old.id != new.id
    assert len(audits) == 1
    assert audits[0].envelope_id == new.id


# ---------------------------------------------------------------------------
# Task 16: get_by_id, get_by_barcode
# ---------------------------------------------------------------------------

from app.exceptions import EnvelopeNotFound


@pytest.mark.asyncio
async def test_get_by_id_returns_envelope(db_session):
    env = await svc.create_envelope(db_session, operator="A")
    await db_session.commit()
    fetched = await svc.get_by_id(db_session, env.id)
    assert fetched.id == env.id


@pytest.mark.asyncio
async def test_get_by_id_not_found_raises(db_session):
    import uuid as _u
    with pytest.raises(EnvelopeNotFound):
        await svc.get_by_id(db_session, _u.uuid4())


@pytest.mark.asyncio
async def test_get_by_barcode_returns_envelope(db_session):
    env = await svc.create_envelope(db_session, operator="A")
    await db_session.commit()
    fetched = await svc.get_by_barcode(db_session, env.barcode)
    assert fetched.id == env.id


@pytest.mark.asyncio
async def test_get_by_barcode_not_found_raises(db_session):
    with pytest.raises(EnvelopeNotFound):
        await svc.get_by_barcode(db_session, "0000000000000000")


# ---------------------------------------------------------------------------
# Task 17: add_document
# ---------------------------------------------------------------------------


def _normalized_peremeshchenie() -> NormalizedDocument:
    return NormalizedDocument(
        entity="Document_ПеремещениеТоваров",
        doc_kind="Перемещение товаров",
        doc_number="ПЕР-000123",
        doc_date=_date(2026, 4, 20),
        related_realization_ref=None,
        raw_payload={"Number": "ПЕР-000123", "Date": "2026-04-20T00:00:00"},
    )


@pytest.mark.asyncio
async def test_add_document_happy_path(db_session):
    env = await svc.create_envelope(db_session, operator="A")
    await db_session.commit()

    one_c = AsyncMock()
    one_c.lookup_document_with_related.return_value = _normalized_peremeshchenie()

    barcode = str(int.from_bytes(uuid.UUID("11111111-1111-1111-1111-111111111111").bytes, "big"))
    doc = await svc.add_document(db_session, envelope=env, barcode=barcode,
                                  operator="A", one_c=one_c)
    await db_session.commit()
    assert doc.doc_kind == "Перемещение товаров"
    assert doc.doc_number == "ПЕР-000123"
    assert doc.doc_barcode == barcode
    assert doc.raw_1c_payload == {"Number": "ПЕР-000123", "Date": "2026-04-20T00:00:00"}


@pytest.mark.asyncio
async def test_add_document_rejects_when_envelope_sealed(db_session):
    env = await svc.create_envelope(db_session, operator="A")
    env.status = EnvelopeStatus.sealed
    await db_session.commit()
    one_c = AsyncMock()
    from app.exceptions import EnvelopeNotDraft
    with pytest.raises(EnvelopeNotDraft):
        await svc.add_document(db_session, envelope=env, barcode="123", operator="A", one_c=one_c)


@pytest.mark.asyncio
async def test_add_document_rejects_invalid_barcode(db_session):
    env = await svc.create_envelope(db_session, operator="A")
    await db_session.commit()
    one_c = AsyncMock()
    from app.exceptions import BarcodeError
    with pytest.raises(BarcodeError):
        await svc.add_document(db_session, envelope=env, barcode="abc", operator="A", one_c=one_c)


@pytest.mark.asyncio
async def test_add_document_duplicate_raises_already_in_envelope(db_session):
    env = await svc.create_envelope(db_session, operator="A")
    await db_session.commit()
    one_c = AsyncMock()
    one_c.lookup_document_with_related.return_value = _normalized_peremeshchenie()
    barcode = str(int.from_bytes(uuid.UUID("11111111-1111-1111-1111-111111111111").bytes, "big"))
    await svc.add_document(db_session, envelope=env, barcode=barcode, operator="A", one_c=one_c)
    await db_session.commit()
    from app.exceptions import DocumentAlreadyInEnvelope
    with pytest.raises(DocumentAlreadyInEnvelope):
        await svc.add_document(db_session, envelope=env, barcode=barcode, operator="A", one_c=one_c)


# ---------------------------------------------------------------------------
# Task 18: remove_document
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_remove_document_happy(db_session):
    env = await svc.create_envelope(db_session, operator="A")
    await db_session.commit()
    one_c = AsyncMock()
    one_c.lookup_document_with_related.return_value = _normalized_peremeshchenie()
    bc = str(int.from_bytes(uuid.UUID("11111111-1111-1111-1111-111111111111").bytes, "big"))
    doc = await svc.add_document(db_session, envelope=env, barcode=bc, operator="A", one_c=one_c)
    await db_session.commit()
    await svc.remove_document(db_session, envelope=env, doc_id=doc.id, operator="A")
    await db_session.commit()
    docs = (await db_session.execute(select(EnvelopeDocument))).scalars().all()
    assert docs == []


@pytest.mark.asyncio
async def test_remove_document_when_sealed_raises(db_session):
    env = await svc.create_envelope(db_session, operator="A")
    env.status = EnvelopeStatus.sealed
    await db_session.commit()
    from app.exceptions import EnvelopeNotDraft
    with pytest.raises(EnvelopeNotDraft):
        await svc.remove_document(db_session, envelope=env, doc_id=uuid.uuid4(), operator="A")


# ---------------------------------------------------------------------------
# Task 19: seal
# ---------------------------------------------------------------------------

from app.models import Branch, Signer


async def _make_dictionary(db_session):
    b1 = Branch(name="Москва"); b2 = Branch(name="Казань")
    s1 = Signer(last_name="Иванов", first_name="Иван")
    s2 = Signer(last_name="Петров", first_name="Пётр")
    db_session.add_all([b1, b2, s1, s2])
    await db_session.flush()
    return b1, b2, s1, s2


@pytest.mark.asyncio
async def test_seal_happy(db_session):
    env = await svc.create_envelope(db_session, operator="A")
    one_c = AsyncMock()
    one_c.lookup_document_with_related.return_value = _normalized_peremeshchenie()
    bc = str(int.from_bytes(uuid.UUID("11111111-1111-1111-1111-111111111111").bytes, "big"))
    await svc.add_document(db_session, envelope=env, barcode=bc, operator="A", one_c=one_c)
    b1, b2, s1, s2 = await _make_dictionary(db_session)
    await db_session.commit()

    sealed = await svc.seal(
        db_session, envelope=env,
        signer_sender_id=s1.id, signer_receiver_id=s2.id,
        origin_branch_id=b1.id, destination_branch_id=None,
        notes="хрупкое",
        operator="A",
    )
    await db_session.commit()
    assert sealed.status == EnvelopeStatus.sealed
    assert sealed.sealed_at is not None
    assert sealed.signer_sender_id == s1.id
    assert sealed.notes == "хрупкое"


@pytest.mark.asyncio
async def test_seal_rejects_empty_envelope(db_session):
    env = await svc.create_envelope(db_session, operator="A")
    b1, b2, s1, s2 = await _make_dictionary(db_session)
    await db_session.commit()
    from app.exceptions import InvalidSealPayload
    with pytest.raises(InvalidSealPayload):
        await svc.seal(db_session, envelope=env,
                       signer_sender_id=s1.id, signer_receiver_id=s2.id,
                       origin_branch_id=b1.id, destination_branch_id=None,
                       notes=None, operator="A")


@pytest.mark.asyncio
async def test_seal_rejects_inactive_signer(db_session):
    env = await svc.create_envelope(db_session, operator="A")
    one_c = AsyncMock()
    one_c.lookup_document_with_related.return_value = _normalized_peremeshchenie()
    bc = str(int.from_bytes(uuid.UUID("11111111-1111-1111-1111-111111111111").bytes, "big"))
    await svc.add_document(db_session, envelope=env, barcode=bc, operator="A", one_c=one_c)
    b1, b2, s1, s2 = await _make_dictionary(db_session)
    s1.is_active = False
    await db_session.commit()
    from app.exceptions import InvalidSealPayload
    with pytest.raises(InvalidSealPayload):
        await svc.seal(db_session, envelope=env,
                       signer_sender_id=s1.id, signer_receiver_id=s2.id,
                       origin_branch_id=b1.id, destination_branch_id=None,
                       notes=None, operator="A")


@pytest.mark.asyncio
async def test_seal_already_sealed_raises_not_draft(db_session):
    env = await svc.create_envelope(db_session, operator="A")
    env.status = EnvelopeStatus.sealed
    b1, b2, s1, s2 = await _make_dictionary(db_session)
    await db_session.commit()
    from app.exceptions import EnvelopeNotDraft
    with pytest.raises(EnvelopeNotDraft):
        await svc.seal(db_session, envelope=env,
                       signer_sender_id=s1.id, signer_receiver_id=s2.id,
                       origin_branch_id=b1.id, destination_branch_id=None,
                       notes=None, operator="A")
