import uuid
from datetime import date
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.models import OneCDocument
from app.services.odata import PROP_INVOICE_SENT_TO_ACCOUNTING
from app.services.paperless import process_paperless_event


def _doc_row(guid: uuid.UUID, doc_date: date) -> OneCDocument:
    return OneCDocument(
        guid=guid,
        number="ТАУТ-0000630",
        print_number="УТ-630",
        doc_date=doc_date,
        is_correction=False,
        partner_name='ЗАО СКБ "Хроматэк"',
        is_edo=False,
        is_deleted=False,
    )


@pytest.mark.asyncio
async def test_paperless_sets_accounting_mark_when_doc_date_is_in_range(db_session):
    guid = uuid.uuid4()
    db_session.add(_doc_row(guid, date(2026, 2, 5)))
    await db_session.commit()
    onec = SimpleNamespace(
        patch_storage_link=AsyncMock(return_value=None),
        mark_document_boolean=AsyncMock(return_value=None),
    )

    result = await process_paperless_event(
        db_session,
        onec,
        doc_type="УПД",
        doc_date_str="2026-02-05",
        file_name="05.02.2026 УПД № УТ-630 ЗАО СКБ ХРОМАТЭК.pdf",
        original_filename="scan.pdf",
        archive_path=r"\\archive\05.02.2026 УПД № УТ-630.pdf",
        download_url=None,
        accounting_mark_from_date=date(2026, 1, 1),
    )

    assert result["status"] == "matched"
    onec.patch_storage_link.assert_awaited_once()
    onec.mark_document_boolean.assert_awaited_once_with(
        guid,
        "Document_СчетФактураВыданный",
        PROP_INVOICE_SENT_TO_ACCOUNTING,
        True,
    )


@pytest.mark.asyncio
async def test_paperless_skips_accounting_mark_before_configured_date(db_session):
    guid = uuid.uuid4()
    db_session.add(_doc_row(guid, date(2026, 2, 5)))
    await db_session.commit()
    onec = SimpleNamespace(
        patch_storage_link=AsyncMock(return_value=None),
        mark_document_boolean=AsyncMock(return_value=None),
    )

    result = await process_paperless_event(
        db_session,
        onec,
        doc_type="УПД",
        doc_date_str="2026-02-05",
        file_name="05.02.2026 УПД № УТ-630 ЗАО СКБ ХРОМАТЭК.pdf",
        original_filename="scan.pdf",
        archive_path=r"\\archive\05.02.2026 УПД № УТ-630.pdf",
        download_url=None,
        accounting_mark_from_date=date(2026, 3, 1),
    )

    assert result["status"] == "matched"
    onec.patch_storage_link.assert_awaited_once()
    onec.mark_document_boolean.assert_not_awaited()
