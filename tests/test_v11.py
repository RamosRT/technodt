from datetime import date

import pytest

from app.models import Branch, EnvelopeDocument, EnvelopeStatus, Signer
from app.services import documents as doc_svc
from app.services import envelopes as env_svc
from app.services.operators import ensure_operator, list_operators, patch_operator


@pytest.mark.asyncio
async def test_operator_registry_ensure_list_patch(db_session):
    op = await ensure_operator(db_session, "Админ", bootstrap=True)
    await db_session.commit()

    operators = await list_operators(db_session)
    assert [item.username for item in operators] == ["Админ"]
    assert operators[0].is_admin is True

    patched = await patch_operator(db_session, operator_id=op.id, is_admin=None, is_active=False)
    await db_session.commit()
    assert patched.is_active is False


async def _sealed_envelope(db_session):
    branch = Branch(name="Москва")
    signer_a = Signer(last_name="Иванов", first_name="Иван")
    signer_b = Signer(last_name="Петров", first_name="Петр")
    db_session.add_all([branch, signer_a, signer_b])
    await db_session.flush()

    envelope = await env_svc.create_envelope(db_session, operator="Оператор")
    doc = EnvelopeDocument(
        envelope_id=envelope.id,
        doc_barcode="1",
        doc_guid="00000000-0000-0000-0000-000000000001",
        doc_entity="Document_ПеремещениеТоваров",
        doc_kind="Перемещение товаров",
        doc_number="ПТ-1",
        doc_date=date(2026, 4, 30),
        raw_1c_payload={"Number": "ПТ-1"},
    )
    db_session.add(doc)
    await db_session.flush()
    await env_svc.seal(
        db_session,
        envelope=envelope,
        signer_sender_id=signer_a.id,
        signer_receiver_id=signer_b.id,
        origin_branch_id=branch.id,
        destination_branch_id=None,
        notes=None,
        operator="Оператор",
    )
    await db_session.flush()
    return envelope


@pytest.mark.asyncio
async def test_unseal_returns_sealed_envelope_to_draft(db_session):
    envelope = await _sealed_envelope(db_session)

    await env_svc.unseal(db_session, envelope=envelope, reason="Исправление состава", operator="Админ")
    await db_session.commit()

    assert envelope.status is EnvelopeStatus.draft
    assert envelope.sealed_at is None


@pytest.mark.asyncio
async def test_document_list_summary_counts_in_transit(db_session):
    await _sealed_envelope(db_session)
    await db_session.commit()

    rows, total, summary = await doc_svc.list_documents(db_session)

    assert total == 1
    assert rows[0]["status"] == "in_transit"
    assert summary["total"] == 1
    assert summary["in_transit"] == 1
