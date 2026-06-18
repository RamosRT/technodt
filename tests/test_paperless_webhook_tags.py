from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from app.services.paperless_tag_sync import apply_paperless_webhook_tags


def _settings():
    return SimpleNamespace(
        paperless_api_url="http://paperless",
        paperless_api_token="token",
        paperless_mark_tag_id=7,
        paperless_error_tag_id=8,
    )


@pytest.mark.asyncio
async def test_webhook_tags_sets_error_on_not_matched():
    client = AsyncMock()
    client.fetch_document.return_value = {"id": 29764, "tags": [7]}
    client.patch_document_tags = AsyncMock()
    client.aclose = AsyncMock()

    with patch(
        "app.services.paperless_tag_sync.PaperlessTagClient",
        return_value=client,
    ):
        out = await apply_paperless_webhook_tags(
            document_id=29764,
            result={"status": "not_matched", "reason": "no_mirror_match"},
            settings=_settings(),
        )

    assert out["status"] == "updated"
    assert 8 in out["tags"]
    client.patch_document_tags.assert_awaited_once_with(29764, [7, 8])


@pytest.mark.asyncio
async def test_webhook_tags_clears_mark_and_error_on_success():
    client = AsyncMock()
    client.fetch_document.return_value = {"id": 1, "tags": [7, 8, 10]}
    client.patch_document_tags = AsyncMock()
    client.aclose = AsyncMock()

    with patch(
        "app.services.paperless_tag_sync.PaperlessTagClient",
        return_value=client,
    ):
        out = await apply_paperless_webhook_tags(
            document_id=1,
            result={"status": "matched"},
            settings=_settings(),
        )

    assert out["tags"] == [10]
    client.patch_document_tags.assert_awaited_once_with(1, [10])


@pytest.mark.asyncio
async def test_webhook_tags_skipped_for_non_invoice():
    out = await apply_paperless_webhook_tags(
        document_id=1,
        result={"status": "skipped"},
        settings=_settings(),
    )
    assert out["status"] == "skipped"
    assert out["reason"] == "not_invoice"


@pytest.mark.asyncio
async def test_webhook_tags_no_document_id():
    out = await apply_paperless_webhook_tags(
        document_id=0,
        result={"status": "not_matched"},
        settings=_settings(),
    )
    assert out["reason"] == "no_document_id"


@pytest.mark.asyncio
async def test_webhook_tags_sets_mark_tag_on_deferred():
    client = AsyncMock()
    client.fetch_document.return_value = {"id": 30076, "tags": [10]}
    client.patch_document_tags = AsyncMock()
    client.aclose = AsyncMock()

    with patch(
        "app.services.paperless_tag_sync.PaperlessTagClient",
        return_value=client,
    ):
        out = await apply_paperless_webhook_tags(
            document_id=30076,
            result={"status": "deferred", "reason": "merged_metadata_pending"},
            settings=_settings(),
        )

    assert out["status"] == "updated"
    assert out["paperless_status"] == "deferred"
    assert 7 in out["tags"]
    assert 10 in out["tags"]
    client.patch_document_tags.assert_awaited_once_with(30076, [10, 7])
