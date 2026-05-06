import asyncio
import logging
import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import respx

from app.exceptions import OneCUnavailable
from app.models.envelope_document import EnvelopeDocument
from app.services.odata import (
    MARK_ELIGIBLE_ENTITIES,
    PROP_REGISTERED,
    PROP_SEALED,
    PROP_VERIFIED,
    OneCClient,
)

BASE = "http://1c.example/odata/standard.odata"
PROP_KEY = uuid.UUID("d034a826-4787-11f1-92ca-00155d060d01")
DOC_GUID = uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
ENTITY = "Document_СчетФактураВыданный"
VALUE = datetime(2026, 5, 6, 10, 0, 0, tzinfo=UTC)


@pytest.fixture
def client():
    return OneCClient(base_url=BASE, user="u", password="p", timeout=5)


def test_mark_eligible_entities_excludes_peremeshchenie():
    assert "Document_ПеремещениеТоваров" not in MARK_ELIGIBLE_ENTITIES
    assert "Document_СчетФактураВыданный" in MARK_ELIGIBLE_ENTITIES


def test_prop_constants_have_correct_uuids():
    assert str(PROP_REGISTERED) == "bda8ba09-4787-11f1-92ca-00155d060d01"
    assert str(PROP_SEALED) == "d034a826-4787-11f1-92ca-00155d060d01"
    assert str(PROP_VERIFIED) == "daa0fcae-4787-11f1-92ca-00155d060d01"


@pytest.mark.asyncio
async def test_mark_document_posts_on_success(client):
    with respx.mock(base_url=BASE) as mock:
        route = mock.post(
            url__regex=r".*/InformationRegister_.*",
            params={"$format": "json"},
        ).respond(201)
        await client.mark_document(DOC_GUID, ENTITY, PROP_KEY, VALUE)
    assert route.call_count == 1


@pytest.mark.asyncio
async def test_mark_document_patches_on_duplicate_code_15(client):
    with respx.mock(base_url=BASE) as mock:
        post_route = mock.post(
            url__regex=r".*/InformationRegister_.*",
            params={"$format": "json"},
        ).respond(
            400,
            json={"code": "15", "description": "запись уже существует"},
        )
        patch_route = mock.patch(
            url__regex=r".*/InformationRegister_.*",
            params={"$format": "json"},
        ).respond(200)
        await client.mark_document(DOC_GUID, ENTITY, PROP_KEY, VALUE)
    assert post_route.call_count == 1
    assert patch_route.call_count == 1


@pytest.mark.asyncio
async def test_mark_document_patches_on_nested_odata_error_code_15(client):
    with respx.mock(base_url=BASE) as mock:
        post_route = mock.post(
            url__regex=r".*/InformationRegister_.*",
            params={"$format": "json"},
        ).respond(
            400,
            json={"odata.error": {"code": "15", "message": {"lang": "ru", "value": "duplicate"}}},
        )
        patch_route = mock.patch(
            url__regex=r".*/InformationRegister_.*",
            params={"$format": "json"},
        ).respond(200)
        await client.mark_document(DOC_GUID, ENTITY, PROP_KEY, VALUE)
    assert post_route.call_count == 1
    assert patch_route.call_count == 1


@pytest.mark.asyncio
async def test_mark_document_raises_on_server_error(client):
    with respx.mock(base_url=BASE) as mock:
        mock.post(
            url__regex=r".*/InformationRegister_.*",
            params={"$format": "json"},
        ).respond(500)
        with pytest.raises(OneCUnavailable):
            await client.mark_document(DOC_GUID, ENTITY, PROP_KEY, VALUE)


@pytest.mark.asyncio
async def test_mark_document_raises_on_patch_failure(client):
    with respx.mock(base_url=BASE) as mock:
        mock.post(
            url__regex=r".*/InformationRegister_.*",
            params={"$format": "json"},
        ).respond(400, json={"code": "15"})
        mock.patch(
            url__regex=r".*/InformationRegister_.*",
            params={"$format": "json"},
        ).respond(500)
        with pytest.raises(OneCUnavailable):
            await client.mark_document(DOC_GUID, ENTITY, PROP_KEY, VALUE)


@pytest.mark.asyncio
async def test_fire_seal_marks_skips_peremeshchenie():
    from app.services.onec_marks import fire_seal_marks

    envelope_id = uuid.uuid4()
    doc = MagicMock(spec=EnvelopeDocument)
    doc.doc_entity = "Document_ПеремещениеТоваров"
    doc.doc_guid = DOC_GUID
    doc.added_at = VALUE

    one_c = MagicMock()
    one_c.mark_document = AsyncMock()

    fire_seal_marks(one_c, envelope_id, [doc], VALUE, MagicMock())
    await asyncio.sleep(0)
    one_c.mark_document.assert_not_awaited()


@pytest.mark.asyncio
async def test_fire_seal_marks_disabled_by_flag():
    from app.services.onec_marks import fire_seal_marks

    envelope_id = uuid.uuid4()
    doc = MagicMock(spec=EnvelopeDocument)
    doc.doc_entity = "Document_СчетФактураВыданный"
    doc.doc_guid = DOC_GUID
    doc.added_at = VALUE

    one_c = MagicMock()
    one_c.mark_document = AsyncMock()

    fire_seal_marks(one_c, envelope_id, [doc], VALUE, MagicMock(), enabled=False)
    await asyncio.sleep(0)
    one_c.mark_document.assert_not_awaited()


@pytest.mark.asyncio
async def test_mark_documents_with_retry_succeeds_on_first_attempt():
    from app.services.onec_marks import Mark, _mark_documents_with_retry

    one_c = MagicMock()
    one_c.mark_document = AsyncMock(return_value=None)
    marks = [Mark(uuid.uuid4(), DOC_GUID, ENTITY, PROP_KEY, "Запечатан", VALUE)]

    factory = MagicMock()
    session_mock = MagicMock()
    session_mock.commit = AsyncMock()
    factory.return_value.__aenter__ = AsyncMock(return_value=session_mock)
    factory.return_value.__aexit__ = AsyncMock(return_value=False)

    await _mark_documents_with_retry(one_c, marks, factory)
    one_c.mark_document.assert_awaited_once()
    assert session_mock.add.called
    session_mock.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_mark_documents_with_retry_logs_after_two_failures(caplog):
    from app.services.onec_marks import Mark, _mark_documents_with_retry

    one_c = MagicMock()
    one_c.mark_document = AsyncMock(side_effect=Exception("connection refused"))
    marks = [Mark(uuid.uuid4(), DOC_GUID, ENTITY, PROP_KEY, "Запечатан", VALUE)]

    session_mock = MagicMock()
    session_mock.commit = AsyncMock()
    factory = MagicMock()
    factory.return_value.__aenter__ = AsyncMock(return_value=session_mock)
    factory.return_value.__aexit__ = AsyncMock(return_value=False)

    with patch("app.services.onec_marks.asyncio.sleep", new_callable=AsyncMock):
        with patch("app.services.onec_marks.write_event", new_callable=AsyncMock):
            with caplog.at_level(logging.WARNING):
                await _mark_documents_with_retry(one_c, marks, factory)

    assert "retry failed" in caplog.text.lower() or "failed" in caplog.text.lower()
    assert one_c.mark_document.await_count == 2
    assert session_mock.add.called
    session_mock.commit.assert_awaited_once()
