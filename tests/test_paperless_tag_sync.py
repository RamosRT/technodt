import uuid
from datetime import date
from types import SimpleNamespace
from unittest.mock import AsyncMock

from app.models import OneCDocument
from app.services.paperless_tag_sync import (
    build_archive_path_from_metadata,
    process_paperless_marked_documents,
)


class FakePaperlessClient:
    def __init__(self, *, docs, metadata):
        self.docs = docs
        self.metadata = metadata
        self.patched_tags: list[tuple[int, list[int]]] = []

    async def fetch_document_types(self):
        return {1: "УПД"}

    async def fetch_correspondents(self):
        return {2: "ЗАО СКБ ХРОМАТЭК"}

    async def fetch_documents_with_tag(self, tag_id: int, *, limit: int):
        return self.docs[:limit]

    async def fetch_metadata(self, document_id: int):
        return self.metadata[document_id]

    async def patch_document_tags(self, document_id: int, tags: list[int]):
        self.patched_tags.append((document_id, tags))


def _settings():
    return SimpleNamespace(
        paperless_api_url="http://paperless",
        paperless_api_token="token",
        paperless_mark_tag_id=52,
        paperless_error_tag_id=53,
        paperless_onec_originals_unc_root=r"\\kaz-pc036\Техно-Архив",
        paperless_onec_archive_unc_root="",
        paperless_poll_batch_size=50,
    )


def _doc_row(guid: uuid.UUID) -> OneCDocument:
    return OneCDocument(
        guid=guid,
        number="ТАУТ-0000630",
        print_number="УТ-630",
        doc_date=date(2026, 2, 5),
        is_correction=False,
        partner_name='ЗАО СКБ "Хроматэк"',
        is_edo=False,
        is_deleted=False,
    )


def test_build_archive_path_from_metadata_uses_1c_alias_root():
    path = build_archive_path_from_metadata(
        {
            "has_archive_version": False,
            "media_filename": "2026/февр./УПД/05.02.2026 УПД № УТ-630 ЗАО СКБ -ХРОМАТЭК-.pdf",
        },
        originals_unc_root=r"\\kaz-pc036\Техно-Архив",
    )

    assert path == r"\\kaz-pc036\Техно-Архив\2026\февр.\УПД\05.02.2026 УПД № УТ-630 ЗАО СКБ -ХРОМАТЭК-.pdf"


async def test_process_marked_documents_removes_mark_and_error_tags_on_success(db_session):
    guid = uuid.uuid4()
    db_session.add(_doc_row(guid))
    await db_session.commit()

    paperless = FakePaperlessClient(
        docs=[
            {
                "id": 1997,
                "title": '05.02.2026 УПД № УТ-630 ЗАО СКБ "ХРОМАТЭК"',
                "document_type": 1,
                "created": "2026-02-05",
                "correspondent": 2,
                "original_file_name": "Untitled - 0239.pdf",
                "tags": [52, 53, 10],
            }
        ],
        metadata={
            1997: {
                "has_archive_version": False,
                "media_filename": "2026/февр./УПД/05.02.2026 УПД № УТ-630 ЗАО СКБ -ХРОМАТЭК-.pdf",
            }
        },
    )
    onec = SimpleNamespace(patch_storage_link=AsyncMock(return_value=None))

    result = await process_paperless_marked_documents(db_session, onec, paperless, _settings())

    assert result["counts"] == {"matched": 1}
    assert paperless.patched_tags == [(1997, [10])]
    onec.patch_storage_link.assert_awaited_once()


async def test_process_marked_documents_sets_error_tag_on_failure(db_session):
    paperless = FakePaperlessClient(
        docs=[
            {
                "id": 1997,
                "title": '05.02.2026 УПД № УТ-630 ЗАО СКБ "ХРОМАТЭК"',
                "document_type": 1,
                "created": "2026-02-05",
                "correspondent": 2,
                "original_file_name": "Untitled - 0239.pdf",
                "tags": [52],
            }
        ],
        metadata={
            1997: {
                "has_archive_version": False,
                "media_filename": "2026/февр./УПД/05.02.2026 УПД № УТ-630 ЗАО СКБ -ХРОМАТЭК-.pdf",
            }
        },
    )
    onec = SimpleNamespace(patch_storage_link=AsyncMock(return_value=None))

    result = await process_paperless_marked_documents(db_session, onec, paperless, _settings())

    assert result["counts"] == {"not_matched": 1}
    assert paperless.patched_tags == [(1997, [52, 53])]


async def test_process_marked_documents_defers_when_path_still_merged(db_session):
    paperless = FakePaperlessClient(
        docs=[
            {
                "id": 30076,
                "title": "24.04.2026 УПД № УТ-3486 СОЛЛЕРС АЛАБУГА ООО (merged)",
                "document_type": 1,
                "created": "2026-04-24",
                "correspondent": 2,
                "original_file_name": "30075_29553_merged.pdf",
                "tags": [52],
            }
        ],
        metadata={
            30076: {
                "has_archive_version": False,
                "media_filename": "2025/11/doc (merged).pdf",
            }
        },
    )
    onec = SimpleNamespace(patch_storage_link=AsyncMock(return_value=None))

    result = await process_paperless_marked_documents(db_session, onec, paperless, _settings())

    assert result["counts"] == {"deferred": 1}
    assert paperless.patched_tags == []
    onec.patch_storage_link.assert_not_awaited()


async def test_process_marked_documents_marks_merged_original_when_archive_path_final(db_session):
    guid = uuid.uuid4()
    db_session.add(
        OneCDocument(
            guid=guid,
            number="ТАУТ-0003257",
            print_number="УТ-3257",
            doc_date=date(2026, 4, 20),
            is_correction=False,
            partner_name='ООО "ДОМКОР"',
            is_edo=False,
            is_deleted=False,
        )
    )
    await db_session.commit()

    final_media = (
        "2026/04/20.04.2026 УПД № УТ-3257 Общество с ограниченной ответственностью "
        "Специализированный застройщик -ДОМКОР-_02.pdf"
    )
    paperless = FakePaperlessClient(
        docs=[
            {
                "id": 30100,
                "title": "20.04.2026 УПД № УТ-3257 ДОМКОР",
                "document_type": 1,
                "created": "2026-04-20",
                "correspondent": 2,
                "original_file_name": "29433_29432_merged.pdf",
                "tags": [52],
            }
        ],
        metadata={
            30100: {
                "has_archive_version": False,
                "media_filename": final_media,
            }
        },
    )
    onec = SimpleNamespace(patch_storage_link=AsyncMock(return_value=None))

    result = await process_paperless_marked_documents(db_session, onec, paperless, _settings())

    assert result["counts"] == {"matched": 1}
    assert paperless.patched_tags == [(30100, [])]
    onec.patch_storage_link.assert_awaited_once()
