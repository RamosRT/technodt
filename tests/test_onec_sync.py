import uuid
from datetime import date
from unittest.mock import AsyncMock

import pytest

from app.models import OneCDocument
from app.services.odata import RealizationSummary
from app.services.onec_sync import run_incremental_sync, run_initial_sync


def _invoice_row(guid: uuid.UUID) -> dict:
    return {
        "Ref_Key": str(guid),
        "Number": "ТАУТ-0006000",
        "ПредставлениеНомера": "УТ-6000",
        "Date": "2026-06-30T00:00:00",
        "Корректировочный": False,
        "DeletionMark": False,
        "ВыставленВЭлектронномВиде": False,
        "ДокументОснование": "33333333-3333-3333-3333-333333333333",
        "ДокументОснование_Type": "StandardODATA.Document_РеализацияТоваровУслуг",
        "Партнер": {"НаименованиеПолное": "ООО Клиент"},
    }


@pytest.mark.asyncio
async def test_initial_sync_stores_related_realization_number(db_session):
    guid = uuid.UUID("22222222-2222-2222-2222-222222222222")
    client = AsyncMock()
    client.fetch_invoices_page.side_effect = [[_invoice_row(guid)], []]
    client.fetch_related_realization.return_value = RealizationSummary(
        number="РТ-6000",
        doc_date=date(2026, 6, 29),
    )

    await run_initial_sync(client, db_session, date(2026, 1, 1))

    stored = await db_session.get(OneCDocument, guid)
    assert stored is not None
    assert stored.related_realization_number == "РТ-6000"


@pytest.mark.asyncio
async def test_incremental_sync_keeps_existing_related_realization_on_lookup_miss(db_session):
    guid = uuid.UUID("22222222-2222-2222-2222-222222222222")
    db_session.add(
        OneCDocument(
            guid=guid,
            number="ТАУТ-0006000",
            print_number="УТ-6000",
            doc_date=date(2026, 6, 30),
            is_correction=False,
            partner_name="ООО Клиент",
            is_edo=False,
            related_realization_number="РТ-OLD",
            is_deleted=False,
        )
    )
    await db_session.commit()
    client = AsyncMock()
    client.get_change_restriction_date.return_value = date(2026, 1, 1)
    client.fetch_invoices_page.side_effect = [[_invoice_row(guid)], []]
    client.fetch_related_realization.return_value = None

    await run_incremental_sync(client, db_session)

    stored = await db_session.get(OneCDocument, guid)
    assert stored is not None
    assert stored.related_realization_number == "РТ-OLD"
