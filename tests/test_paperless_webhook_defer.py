from unittest.mock import AsyncMock, patch

import pytest


@pytest.mark.asyncio
async def test_webhook_defers_merged_invoice_without_onec_patch(client):
    tag_result = {"status": "updated", "paperless_status": "deferred", "tags": [52]}

    with (
        patch(
            "app.routers.api.webhooks.resolve_archive_path_from_paperless",
            new=AsyncMock(
                return_value=r"\\kaz-pc036\Техно-Архив\2025\11\doc (merged).pdf",
            ),
        ),
        patch(
            "app.routers.api.webhooks.apply_paperless_webhook_tags",
            new=AsyncMock(return_value=tag_result),
        ) as apply_tags,
        patch(
            "app.routers.api.webhooks.process_paperless_event",
            new=AsyncMock(),
        ) as process_event,
    ):
        resp = await client.post(
            "/api/webhooks/paperless",
            json={
                "document_id": 30076,
                "doc_type": "УПД",
                "created": "2026-04-24",
                "file_name": "24.04.2026 УПД № УТ-3486 СОЛЛЕРС АЛАБУГА ООО (merged)",
                "original_filename": "30075_29553_merged.pdf",
            },
        )

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "deferred"
    assert body["reason"] == "merged_metadata_pending"
    assert body["tags"] == tag_result
    process_event.assert_not_awaited()
    apply_tags.assert_awaited_once()
    call_kwargs = apply_tags.await_args.kwargs
    assert call_kwargs["document_id"] == 30076
    assert call_kwargs["result"]["status"] == "deferred"
