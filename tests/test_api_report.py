import uuid
from datetime import UTC, date, datetime
from unittest.mock import AsyncMock

import pytest

from app.models import Envelope, EnvelopeDocument, EnvelopeStatus, OneCDocument, OneCMarkLog
from app.services.odata import PROP_REGISTERED
from app.services.operators import ensure_operator
from app.services.report import _ENVELOPE_LOOKUP_BATCH_SIZE, _fetch_envelopes_for_docs


class _EmptyResult:
    def all(self):
        return []


@pytest.mark.asyncio
async def test_envelope_lookup_batches_large_document_sets():
    session = AsyncMock()
    session.execute.return_value = _EmptyResult()
    guids = [uuid.uuid4() for _ in range(_ENVELOPE_LOOKUP_BATCH_SIZE + 1)]

    result = await _fetch_envelopes_for_docs(session, guids)

    assert result == {}
    assert session.execute.await_count == 2


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
async def test_documents_report_csv_export_without_date_filters(client, db_session):
    operator = await ensure_operator(db_session, "report-user", password="1234")
    client.cookies.set("operator_name", operator.username)

    response = await client.get(
        "/api/report/documents?format=csv&page_size=10000&date_from=&date_to="
    )

    assert response.status_code == 200
    assert "text/csv" in response.headers["content-type"]


@pytest.mark.asyncio
async def test_documents_report_only_without_edo(client, db_session):
    operator = await ensure_operator(db_session, "report-user", password="1234")
    edo_guid = uuid.uuid4()
    paper_guid = uuid.uuid4()
    db_session.add_all(
        [
            OneCDocument(
                guid=edo_guid,
                number="000000201",
                print_number="201",
                doc_date=date(2026, 5, 1),
                is_correction=False,
                is_edo=True,
                is_deleted=False,
            ),
            OneCDocument(
                guid=paper_guid,
                number="000000202",
                print_number="202",
                doc_date=date(2026, 5, 2),
                is_correction=False,
                is_edo=False,
                is_deleted=False,
            ),
        ]
    )
    await db_session.commit()
    client.cookies.set("operator_name", operator.username)

    response = await client.get("/api/report/documents?only_without_edo=true")

    assert response.status_code == 200
    numbers = {row["number"] for row in response.json()["items"]}
    assert numbers == {"202"}


@pytest.mark.asyncio
async def test_documents_report_lists_all_envelopes(client, db_session):
    operator = await ensure_operator(db_session, "report-user", password="1234")
    doc_guid = uuid.uuid4()
    env_a = Envelope(number="ТА-100001", barcode="TA100001", status=EnvelopeStatus.sealed, created_by=operator.username)
    env_b = Envelope(number="ТА-100002", barcode="TA100002", status=EnvelopeStatus.sealed, created_by=operator.username)
    db_session.add_all(
        [
            OneCDocument(
                guid=doc_guid,
                number="000000301",
                print_number="301",
                doc_date=date(2026, 5, 10),
                is_correction=False,
                is_deleted=False,
            ),
            env_a,
            env_b,
        ]
    )
    await db_session.flush()
    db_session.add_all(
        [
            EnvelopeDocument(
                envelope_id=env_a.id,
                doc_barcode="111",
                doc_guid=doc_guid,
                doc_entity="Document_СчетФактураВыданный",
                doc_kind="УПД",
                doc_number="301",
                doc_date=date(2026, 5, 10),
                raw_1c_payload={},
            ),
            EnvelopeDocument(
                envelope_id=env_b.id,
                doc_barcode="111",
                doc_guid=doc_guid,
                doc_entity="Document_СчетФактураВыданный",
                doc_kind="УПД",
                doc_number="301",
                doc_date=date(2026, 5, 10),
                raw_1c_payload={},
            ),
        ]
    )
    await db_session.commit()
    client.cookies.set("operator_name", operator.username)

    response = await client.get("/api/report/documents?number=301")

    assert response.status_code == 200
    row = response.json()["items"][0]
    assert set(row["envelope_numbers"]) == {"ТА-100001", "ТА-100002"}
    assert row["envelope_number"] == "ТА-100001, ТА-100002"


@pytest.mark.asyncio
async def test_documents_report_csv_export(client, db_session):
    operator = await ensure_operator(db_session, "report-user", password="1234")
    db_session.add_all(
        [
            OneCDocument(
                guid=uuid.uuid4(),
                number="000000124",
                print_number="124",
                doc_date=date(2026, 5, 20),
                is_correction=True,
                partner_name="АО Клиент",
                is_edo=False,
                is_deleted=False,
            ),
            OneCDocument(
                guid=uuid.uuid4(),
                number="000000125",
                print_number="125",
                doc_date=date(2026, 5, 19),
                is_correction=False,
                partner_name="Second partner",
                is_edo=False,
                is_deleted=False,
            ),
        ]
    )
    await db_session.commit()
    client.cookies.set("operator_name", operator.username)

    response = await client.get("/api/report/documents?format=csv&page_size=1")

    assert response.status_code == 200
    assert "text/csv" in response.headers["content-type"]
    assert 'filename="document-report.csv"' in response.headers["content-disposition"]
    assert "УКД;124;2026-05-20;АО Клиент" in response.text
    assert ";125;2026-05-19;Second partner;" in response.text
