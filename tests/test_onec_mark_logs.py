import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models import OneCMarkLog
from app.services.onec_marks import Mark, _mark_documents_with_retry
from app.services.operators import ensure_operator

DOC_GUID = uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
ENTITY = "Document_СчетФактураВыданный"
PROP_KEY = uuid.UUID("d034a826-4787-11f1-92ca-00155d060d01")
VALUE = datetime(2026, 5, 6, 10, 0, 0, tzinfo=timezone.utc)


@pytest.mark.asyncio
async def test_mark_documents_with_retry_persists_success(test_engine):
    one_c = MagicMock()
    one_c.mark_document = AsyncMock(return_value=None)
    factory = async_sessionmaker(test_engine, expire_on_commit=False, class_=AsyncSession)
    mark = Mark(None, DOC_GUID, ENTITY, PROP_KEY, "Запечатан", VALUE)

    await _mark_documents_with_retry(one_c, [mark], factory)

    async with factory() as session:
        rows = (await session.execute(select(OneCMarkLog))).scalars().all()

    assert len(rows) == 1
    assert rows[0].status == "success"
    assert rows[0].property_name == "Запечатан"
    assert rows[0].doc_guid == DOC_GUID


@pytest.mark.asyncio
async def test_mark_documents_with_retry_persists_failure_after_retry(test_engine):
    one_c = MagicMock()
    one_c.mark_document = AsyncMock(side_effect=Exception("connection refused"))
    factory = async_sessionmaker(test_engine, expire_on_commit=False, class_=AsyncSession)
    mark = Mark(None, DOC_GUID, ENTITY, PROP_KEY, "Проверен", VALUE)

    with patch("app.services.onec_marks.asyncio.sleep", new_callable=AsyncMock):
        await _mark_documents_with_retry(one_c, [mark], factory)

    async with factory() as session:
        rows = (await session.execute(select(OneCMarkLog))).scalars().all()

    assert len(rows) == 1
    assert rows[0].status == "failed"
    assert rows[0].property_name == "Проверен"
    assert "connection refused" in (rows[0].error or "")


@pytest.mark.asyncio
async def test_admin_page_shows_onec_marks_section(client, db_session):
    await ensure_operator(db_session, "Admin", bootstrap=True)
    db_session.add(
        OneCMarkLog(
            envelope_id=None,
            doc_guid=DOC_GUID,
            doc_entity=ENTITY,
            property_key=PROP_KEY,
            property_name="Запечатан",
            status="failed",
            error="Ошибка 1С",
        )
    )
    await db_session.commit()
    client.cookies.set("operator_name", "Admin")

    response = await client.get("/ui/admin")

    assert response.status_code == 200
    assert "Отметки в 1С" in response.text
    assert "Ошибка 1С" in response.text
    assert "Запечатан" in response.text
