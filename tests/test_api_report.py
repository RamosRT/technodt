import uuid
from datetime import UTC, date, datetime

import pytest

from app.models import Envelope, EnvelopeDocument, EnvelopeStatus, OneCDocument, OneCMarkLog
from app.services.odata import PROP_REGISTERED
from app.services.operators import ensure_operator


@pytest.mark.asyncio
async def test_documents_report_returns_local_document_and_success_mark(client, db_session):
    operator = await ensure_operator(db_session, "report-user", password="1234")
    doc_guid = uuid.uuid4()
    envelope = Envelope(
        number="ТА-100001",
        barcode="TA100001",
        status=EnvelopeStatus.sealed,
        created_by=operator.username,
        sealed_at=datetime(2026, 5, 20, 8, 30, tzinfo=UTC),
    )
    db_session.add_all(
        [
            OneCDocument(
                guid=doc_guid,
                number="000000123",
                print_number="123",
                doc_date=date(2026, 5, 19),
                is_correction=False,
                partner_name="ООО Тест",
                is_edo=True,
                is_deleted=False,
            ),
            envelope,
        ]
    )
    await db_session.flush()
    db_session.add_all(
        [
            EnvelopeDocument(
                envelope_id=envelope.id,
                doc_barcode="1234567890",
                doc_guid=doc_guid,
                doc_entity="Document_СчетФактураВыданный",
                doc_kind="УПД",
                doc_number="123",
                doc_date=date(2026, 5, 19),
                raw_1c_payload={},
            ),
            OneCMarkLog(
                envelope_id=envelope.id,
                doc_guid=doc_guid,
                doc_entity="Document_СчетФактураВыданный",
                property_key=PROP_REGISTERED,
                property_name="ДатаРегистрации",
                status="success",
            ),
        ]
    )
    await db_session.commit()
    client.cookies.set("operator_name", operator.username)

    response = await client.get("/api/report/documents")

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 1
    row = payload["items"][0]
    assert row["number"] == "123"
    assert row["partner_name"] == "ООО Тест"
    assert row["envelope_number"] == "ТА-100001"
    assert row["mark_registered_at"] is not None


@pytest.mark.asyncio
async def test_documents_report_csv_export(client, db_session):
    operator = await ensure_operator(db_session, "report-user", password="1234")
    db_session.add(
        OneCDocument(
            guid=uuid.uuid4(),
            number="000000124",
            print_number="124",
            doc_date=date(2026, 5, 20),
            is_correction=True,
            partner_name="АО Клиент",
            is_edo=False,
            is_deleted=False,
        )
    )
    await db_session.commit()
    client.cookies.set("operator_name", operator.username)

    response = await client.get("/api/report/documents?format=csv&page_size=10000")

    assert response.status_code == 200
    assert "text/csv" in response.headers["content-type"]
    assert 'filename="document-report.csv"' in response.headers["content-disposition"]
    assert "УКД;124;2026-05-20;АО Клиент" in response.text
