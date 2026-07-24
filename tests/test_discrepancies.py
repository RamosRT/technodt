import uuid
from datetime import UTC, date, datetime

import pytest
from sqlalchemy import select

from app.exceptions import AppError
from app.models import AuditLog, Envelope, EnvelopeDocument, EnvelopeStatus
from app.services import discrepancies as svc
from app.services.operators import ensure_operator


def _missing_envelope(*, barcode: str = "10001") -> tuple[Envelope, EnvelopeDocument]:
    envelope = Envelope(
        number=f"ТА-{barcode}",
        barcode=barcode.zfill(16),
        status=EnvelopeStatus.verified_with_discrepancy,
        created_by="Отправитель",
        created_at=datetime(2026, 7, 20, 9, 0, tzinfo=UTC),
        sealed_at=datetime(2026, 7, 20, 10, 0, tzinfo=UTC),
        verified_at=datetime(2026, 7, 21, 11, 30, tzinfo=UTC),
        verified_by="Получатель",
    )
    document = EnvelopeDocument(
        doc_barcode=barcode,
        doc_guid=uuid.uuid4(),
        doc_entity="Document_СчетФактураВыданный",
        doc_kind="УПД",
        doc_number=f"УТ-{barcode}",
        doc_date=date(2026, 7, 19),
        raw_1c_payload={"Партнер": {"НаименованиеПолное": "ООО Клиент"}},
    )
    envelope.documents = [document]
    return envelope, document


@pytest.mark.asyncio
async def test_resolve_marks_only_missing_document_and_writes_audit(db_session):
    envelope, document = _missing_envelope()
    db_session.add(envelope)
    await db_session.commit()

    result = await svc.resolve_by_barcode(
        db_session,
        barcode=document.doc_barcode,
        operator="Кладовщик",
    )
    await db_session.commit()

    assert result.id == document.id
    assert document.discrepancy_resolved_at is not None
    assert document.discrepancy_resolved_by == "Кладовщик"
    assert envelope.status is EnvelopeStatus.verified_with_discrepancy
    event = (
        await db_session.execute(
            select(AuditLog).where(AuditLog.event == "discrepancy_resolved")
        )
    ).scalar_one()
    assert event.envelope_id == envelope.id
    assert event.payload["doc_number"] == document.doc_number


@pytest.mark.asyncio
async def test_resolve_rejects_document_without_active_discrepancy(db_session):
    envelope, document = _missing_envelope()
    envelope.status = EnvelopeStatus.verified
    document.scanned_at_verification = datetime(2026, 7, 21, 11, 20, tzinfo=UTC)
    db_session.add(envelope)
    await db_session.commit()

    with pytest.raises(AppError) as exc:
        await svc.resolve_by_barcode(
            db_session,
            barcode=document.doc_barcode,
            operator="Кладовщик",
        )

    assert exc.value.code == "discrepancy_not_found"


@pytest.mark.asyncio
async def test_resolve_rejects_document_already_marked_as_resolved(db_session):
    envelope, document = _missing_envelope()
    db_session.add(envelope)
    await db_session.commit()
    await svc.resolve_by_barcode(
        db_session,
        barcode=document.doc_barcode,
        operator="Кладовщик",
    )
    await db_session.commit()

    with pytest.raises(AppError) as exc:
        await svc.resolve_by_barcode(
            db_session,
            barcode=document.doc_barcode,
            operator="Кладовщик",
        )

    assert exc.value.code == "discrepancy_already_resolved"


@pytest.mark.asyncio
async def test_admin_undo_returns_document_to_active_discrepancy(db_session):
    envelope, document = _missing_envelope()
    db_session.add(envelope)
    await db_session.commit()
    await svc.resolve_by_barcode(
        db_session,
        barcode=document.doc_barcode,
        operator="Кладовщик",
    )
    await db_session.commit()

    await svc.undo_resolution(
        db_session,
        document_id=document.id,
        reason="Отмечен другой документ",
        operator="Администратор",
    )
    await db_session.commit()

    assert document.discrepancy_resolved_at is None
    assert document.discrepancy_resolved_by is None
    event = (
        await db_session.execute(
            select(AuditLog).where(AuditLog.event == "discrepancy_resolution_undo")
        )
    ).scalar_one()
    assert event.payload["reason"] == "Отмечен другой документ"


@pytest.mark.asyncio
async def test_discrepancy_ui_resolve_and_admin_undo(client, db_session):
    await ensure_operator(
        db_session,
        "Администратор",
        bootstrap=True,
        password="1234",
    )
    envelope, document = _missing_envelope(barcode="10002")
    db_session.add(envelope)
    await db_session.commit()
    await client.post(
        "/api/auth/login",
        json={"username": "Администратор", "password": "1234"},
    )

    page = await client.get("/ui/discrepancies")
    resolved = await client.post(
        "/ui/discrepancies/resolve",
        data={"barcode": document.doc_barcode},
    )
    closed_card = await client.get(f"/ui/envelopes/{envelope.id}/card")
    closed_list = await client.get("/ui/envelopes")
    undone = await client.post(
        f"/ui/discrepancies/{document.id}/undo",
        data={"reason": "Ошибочная отметка"},
    )

    assert page.status_code == 200
    assert "Обработка расхождений" in page.text
    assert "Расхождение выявлено" in page.text
    assert envelope.verified_at.strftime("%d.%m.%Y %H:%M") in page.text
    assert "отмечен как сданный" in resolved.text
    assert "Расхождение закрыто" in closed_card.text
    assert "Расхождение закрыто" in closed_list.text
    assert "Отметка для документа" in undone.text
    await db_session.refresh(document)
    assert document.discrepancy_resolved_at is None
