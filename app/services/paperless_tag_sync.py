import asyncio
import logging
from collections import Counter
from typing import Any

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.services.odata import OneCClient
from app.services.paperless import process_paperless_event
from app.services.paperless_paths import build_archive_path_from_metadata, is_merged_pending

log = logging.getLogger(__name__)

DEFAULT_INVOICE_TYPES = frozenset({"упд", "укд", "упд/укд"})
_paperless_tag_lock = asyncio.Lock()

# Re-export for tests and scripts that import from this module.
__all__ = [
    "PaperlessTagClient",
    "apply_paperless_webhook_tags",
    "build_archive_path_from_metadata",
    "is_merged_pending",
    "process_paperless_marked_documents",
    "resolve_archive_path_from_paperless",
]


class PaperlessTagClient:
    def __init__(self, *, base_url: str, token: str, timeout: float = 30) -> None:
        self._client = httpx.AsyncClient(
            base_url=base_url.rstrip("/"),
            headers={"Authorization": f"Token {token}"},
            timeout=timeout,
        )

    async def aclose(self) -> None:
        await self._client.aclose()

    async def _get_all(self, path: str, *, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        page = 1
        rows: list[dict[str, Any]] = []
        while True:
            query = {"page": page, "page_size": 200}
            if params:
                query.update(params)
            resp = await self._client.get(path, params=query)
            resp.raise_for_status()
            data = resp.json()
            rows.extend(data.get("results", []))
            if not data.get("next"):
                break
            page += 1
        return rows

    async def fetch_document_types(self) -> dict[int, str]:
        return {
            int(item["id"]): str(item["name"])
            for item in await self._get_all("/api/document_types/")
            if item.get("id") is not None
        }

    async def fetch_correspondents(self) -> dict[int, str]:
        return {
            int(item["id"]): str(item["name"])
            for item in await self._get_all("/api/correspondents/")
            if item.get("id") is not None
        }

    async def fetch_documents_with_tag(self, tag_id: int, *, limit: int) -> list[dict[str, Any]]:
        rows = await self._get_all("/api/documents/", params={"tags__id": tag_id, "ordering": "-created"})
        return rows[:limit]

    async def fetch_document(self, document_id: int) -> dict[str, Any]:
        resp = await self._client.get(f"/api/documents/{document_id}/")
        resp.raise_for_status()
        return resp.json()

    async def fetch_metadata(self, document_id: int) -> dict[str, Any]:
        resp = await self._client.get(f"/api/documents/{document_id}/metadata/")
        resp.raise_for_status()
        return resp.json()

    async def patch_document_tags(self, document_id: int, tags: list[int]) -> None:
        resp = await self._client.patch(f"/api/documents/{document_id}/", json={"tags": tags})
        resp.raise_for_status()


async def resolve_archive_path_from_paperless(
    document_id: int | None,
    settings: Settings,
    *,
    client: PaperlessTagClient | None = None,
) -> str:
    """Fetch Paperless metadata and build UNC path for 1C kzvСсылкаНаКопию."""
    if not document_id or document_id <= 0:
        return ""
    if not settings.paperless_api_url or not settings.paperless_api_token:
        log.warning(
            "cannot resolve Paperless archive path: API not configured (document_id=%s)",
            document_id,
        )
        return ""
    if not settings.paperless_onec_originals_unc_root:
        log.warning(
            "cannot resolve Paperless archive path: PAPERLESS_ONEC_ORIGINALS_UNC_ROOT missing"
        )
        return ""

    owns_client = client is None
    if owns_client:
        client = PaperlessTagClient(
            base_url=settings.paperless_api_url,
            token=settings.paperless_api_token,
        )
    try:
        metadata = await client.fetch_metadata(document_id)
        return build_archive_path_from_metadata(
            metadata,
            originals_unc_root=settings.paperless_onec_originals_unc_root,
            archive_unc_root=settings.paperless_onec_archive_unc_root,
        )
    except Exception:
        log.exception("failed to fetch Paperless metadata for document_id=%s", document_id)
        return ""
    finally:
        if owns_client and client is not None:
            await client.aclose()


def _int_or_none(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _name_from_id(value: Any, mapping: dict[int, str]) -> str:
    item_id = _int_or_none(value)
    return mapping.get(item_id, "") if item_id is not None else ""


def _without_tag(tags: list[int], tag_id: int) -> list[int]:
    return [item for item in tags if item != tag_id]


def _with_tag(tags: list[int], tag_id: int) -> list[int]:
    return tags if tag_id in tags else [*tags, tag_id]


def _document_tags(doc: dict[str, Any]) -> list[int]:
    tags = []
    for value in doc.get("tags") or []:
        tag_id = _int_or_none(value)
        if tag_id is not None:
            tags.append(tag_id)
    return tags


def _tags_after_success(tags: list[int], settings: Settings) -> list[int]:
    return _without_tag(
        _without_tag(tags, settings.paperless_mark_tag_id),
        settings.paperless_error_tag_id,
    )


def _tags_after_failure(tags: list[int], settings: Settings) -> list[int]:
    return _with_tag(tags, settings.paperless_error_tag_id)


def _tags_after_deferred(tags: list[int], settings: Settings) -> list[int]:
    """Queue merged document for tag-sync; clear error tag if present."""
    return _with_tag(
        _without_tag(tags, settings.paperless_error_tag_id),
        settings.paperless_mark_tag_id,
    )


# Post-consume webhook sets the error tag when 1C marking did not complete.
WEBHOOK_FAILURE_STATUSES = frozenset({"not_matched", "onec_patch_failed", "no_storage_path"})


async def apply_paperless_webhook_tags(
    *,
    document_id: int,
    result: dict[str, Any],
    settings: Settings,
) -> dict[str, Any]:
    """Update Paperless tags after post-consume webhook processing."""
    if not settings.paperless_api_url or not settings.paperless_api_token:
        return {"status": "skipped", "reason": "paperless_api_not_configured"}
    if document_id <= 0:
        return {"status": "skipped", "reason": "no_document_id"}

    processing_status = result.get("status")
    if processing_status == "skipped":
        return {"status": "skipped", "reason": "not_invoice"}
    if processing_status not in ("matched", "deferred", *WEBHOOK_FAILURE_STATUSES):
        return {"status": "skipped", "reason": f"unknown_result_{processing_status!r}"}

    client = PaperlessTagClient(
        base_url=settings.paperless_api_url,
        token=settings.paperless_api_token,
    )
    try:
        doc = await client.fetch_document(document_id)
        current_tags = _document_tags(doc)
        if processing_status == "matched":
            new_tags = _tags_after_success(current_tags, settings)
        elif processing_status == "deferred":
            new_tags = _tags_after_deferred(current_tags, settings)
        else:
            new_tags = _tags_after_failure(current_tags, settings)
        if new_tags != current_tags:
            await client.patch_document_tags(document_id, new_tags)
        return {
            "status": "updated",
            "paperless_status": processing_status,
            "tags": new_tags,
        }
    except Exception as exc:
        log.exception(
            "failed to update Paperless tags after webhook: document_id=%s result=%s",
            document_id,
            processing_status,
        )
        return {"status": "error", "error": str(exc)}
    finally:
        await client.aclose()


async def process_paperless_marked_documents(
    session: AsyncSession,
    onec_client: OneCClient,
    paperless_client: PaperlessTagClient,
    settings: Settings,
) -> dict[str, Any]:
    if not settings.paperless_api_url or not settings.paperless_api_token:
        return {
            "status": "disabled",
            "reason": "Paperless API URL/token are not configured",
        }

    if not settings.paperless_onec_originals_unc_root:
        return {
            "status": "disabled",
            "reason": "PAPERLESS_ONEC_ORIGINALS_UNC_ROOT is not configured",
        }

    type_map = await paperless_client.fetch_document_types()
    docs = await paperless_client.fetch_documents_with_tag(
        settings.paperless_mark_tag_id,
        limit=max(settings.paperless_poll_batch_size, 1),
    )

    counts: Counter[str] = Counter()
    items: list[dict[str, Any]] = []
    for doc in docs:
        document_id = _int_or_none(doc.get("id"))
        if document_id is None:
            counts["skipped"] += 1
            continue

        tags = _document_tags(doc)
        doc_type = _name_from_id(doc.get("document_type"), type_map)
        if doc_type.strip().lower() not in DEFAULT_INVOICE_TYPES:
            counts["skipped"] += 1
            items.append({"document_id": document_id, "status": "skipped", "reason": f"type={doc_type!r}"})
            continue

        metadata = await paperless_client.fetch_metadata(document_id)
        archive_path = build_archive_path_from_metadata(
            metadata,
            originals_unc_root=settings.paperless_onec_originals_unc_root,
            archive_unc_root=settings.paperless_onec_archive_unc_root,
        )
        if is_merged_pending(
            original_filename=doc.get("original_file_name"),
            archive_path=archive_path,
            file_name=doc.get("title"),
        ):
            counts["deferred"] += 1
            items.append(
                {
                    "document_id": document_id,
                    "status": "deferred",
                    "reason": "merged_metadata_pending",
                }
            )
            continue

        event = {
            "doc_type": doc_type,
            "doc_date_str": doc.get("created") or doc.get("created_date"),
            "file_name": doc.get("title") or "",
            "original_filename": doc.get("original_file_name") or "",
            "archive_path": archive_path,
            "download_url": f"{settings.paperless_api_url.rstrip('/')}/api/documents/{document_id}/download/",
        }

        try:
            result = await process_paperless_event(
                session,
                onec_client,
                raise_on_patch_error=True,
                accounting_mark_from_date=getattr(
                    settings, "paperless_accounting_mark_from_date", None
                ),
                **event,
            )
            if result.get("status") == "matched":
                new_tags = _tags_after_success(tags, settings)
                await paperless_client.patch_document_tags(document_id, new_tags)
                counts["matched"] += 1
            else:
                new_tags = _tags_after_failure(tags, settings)
                await paperless_client.patch_document_tags(document_id, new_tags)
                counts[str(result.get("status", "not_matched"))] += 1
            items.append({"document_id": document_id, "status": result.get("status"), "result": result})
        except Exception as exc:
            log.exception("Paperless tagged document processing failed: document_id=%s", document_id)
            new_tags = _tags_after_failure(tags, settings)
            try:
                await paperless_client.patch_document_tags(document_id, new_tags)
            except Exception:
                log.exception("failed to set Paperless error tag: document_id=%s", document_id)
            counts["error"] += 1
            items.append({"document_id": document_id, "status": "error", "error": str(exc)})

    return {
        "status": "done",
        "total": len(docs),
        "counts": dict(sorted(counts.items())),
        "items": items,
    }
