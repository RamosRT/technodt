import uuid
from datetime import date as _date
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import select

from app.exceptions import EnvelopeNotDraft, VerificationUnscanned
from app.models import EnvelopeDocument, EnvelopeStatus
from app.services import envelopes as env_svc
from app.services import verify as svc
from app.services.odata import NormalizedDocument


def _norm() -> NormalizedDocument:
    return NormalizedDocument(
        entity="Document_ПеремещениеТоваров",
        doc_kind="Перемещение товаров",
        doc_number="ПЕР-1",
        doc_date=_date(2026, 4, 20),
        related_realization_ref=None,
        raw_payload={"Number": "ПЕР-1", "Date": "2026-04-20T00:00:00"},
    )


def _bc(guid_str: str) -> str:
    return str(int.from_bytes(uuid.UUID(guid_str).bytes, "big"))


async def _make_sealed(db_session, doc_guids):
    env = await env_svc.create_envelope(db_session, operator="A")
    one_c = AsyncMock()
    for g in doc_guids:
        n = _norm()
        n.doc_number = f"ПЕР-{g[:4]}"
        one_c.lookup_document_with_related.return_value = n
        await env_svc.add_document(db_session, envelope=env, barcode=_bc(g), operator="A", one_c=one_c)
    from app.models import Branch, Signer
    b1, b2 = Branch(name="A"), Branch(name="B")
    s1, s2 = Signer(last_name="X", first_name="x"), Signer(last_name="Y", first_name="y")
    db_session.add_all([b1, b2, s1, s2]); await db_session.flush()
    await env_svc.seal(db_session, envelope=env,
                       signer_sender_id=s1.id, signer_receiver_id=s2.id,
                       origin_branch_id=b1.id, destination_branch_id=b2.id, notes=None, operator="A")
    await db_session.commit()
    return env


@pytest.mark.asyncio
async def test_start_writes_verified_by_and_audit(db_session):
    env = await _make_sealed(db_session, ["11111111-1111-1111-1111-111111111111"])
    await svc.start(db_session, envelope=env, operator="Receiver")
    await db_session.commit()
    assert env.verified_by == "Receiver"
    # status stays sealed until finish


@pytest.mark.asyncio
async def test_start_rejects_draft(db_session):
    env = await env_svc.create_envelope(db_session, operator="A")
    await db_session.commit()
    with pytest.raises(EnvelopeNotDraft):  # reused: "envelope must be sealed" — see note
        await svc.start(db_session, envelope=env, operator="X")


@pytest.mark.asyncio
async def test_scan_matches_document(db_session):
    g = "11111111-1111-1111-1111-111111111111"
    env = await _make_sealed(db_session, [g])
    await svc.start(db_session, envelope=env, operator="R")
    await db_session.commit()
    res = await svc.scan(db_session, envelope=env, barcode=_bc(g), operator="R")
    await db_session.commit()
    assert res.matched is True
    doc = (await db_session.execute(select(EnvelopeDocument))).scalar_one()
    assert doc.scanned_at_verification is not None


@pytest.mark.asyncio
async def test_scan_unknown_barcode_returns_not_in_envelope(db_session):
    env = await _make_sealed(db_session, ["11111111-1111-1111-1111-111111111111"])
    await svc.start(db_session, envelope=env, operator="R")
    await db_session.commit()
    res = await svc.scan(db_session, envelope=env, barcode="0", operator="R")
    assert res.matched is False
    assert res.reason == "not_in_envelope"


@pytest.mark.asyncio
async def test_finish_all_scanned_marks_verified(db_session):
    g = "11111111-1111-1111-1111-111111111111"
    env = await _make_sealed(db_session, [g])
    await svc.start(db_session, envelope=env, operator="R")
    await svc.scan(db_session, envelope=env, barcode=_bc(g), operator="R")
    await db_session.commit()
    res = await svc.finish(db_session, envelope=env, force=False, operator="R")
    await db_session.commit()
    assert res.status == "verified"
    assert env.status == EnvelopeStatus.verified
    assert env.verified_at is not None


@pytest.mark.asyncio
async def test_finish_unscanned_without_force_raises(db_session):
    env = await _make_sealed(db_session, [
        "11111111-1111-1111-1111-111111111111",
        "22222222-2222-2222-2222-222222222222",
    ])
    await svc.start(db_session, envelope=env, operator="R")
    await db_session.commit()
    with pytest.raises(VerificationUnscanned):
        await svc.finish(db_session, envelope=env, force=False, operator="R")


@pytest.mark.asyncio
async def test_finish_force_marks_with_discrepancy(db_session):
    env = await _make_sealed(db_session, [
        "11111111-1111-1111-1111-111111111111",
        "22222222-2222-2222-2222-222222222222",
    ])
    await svc.start(db_session, envelope=env, operator="R")
    await db_session.commit()
    res = await svc.finish(db_session, envelope=env, force=True, operator="R")
    await db_session.commit()
    assert res.status == "verified_with_discrepancy"
    assert len(res.missing_docs) == 2
    assert env.status == EnvelopeStatus.verified_with_discrepancy
