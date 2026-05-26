from typing import Any, Optional

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.db import get_session
from app.deps import get_one_c_client
from app.services.odata import OneCClient
from app.services.paperless import process_paperless_batch, process_paperless_event
from app.services.paperless_tag_sync import (
    apply_paperless_webhook_tags,
    resolve_archive_path_from_paperless,
)

router = APIRouter(prefix="/api/webhooks", tags=["webhooks"])


def _check_api_key(authorization: str = Header(default="")) -> None:
    key = get_settings().paperless_webhook_api_key
    if not key:
        return  # disabled when not configured
    token = authorization.removeprefix("Bearer ").strip()
    if token != key:
        raise HTTPException(status_code=401, detail="Invalid API key")


class PaperlessEvent(BaseModel):
    document_id: Optional[int] = None
    file_name: Optional[str] = None
    doc_type: Optional[str] = None
    created: Optional[str] = None
    correspondent: Optional[str] = None
    download_url: Optional[str] = None
    source_path: Optional[str] = None
    archive_path: Optional[str] = None
    original_filename: Optional[str] = None
    tags: Optional[str] = None


async def _archive_path_for_event(event: PaperlessEvent, settings: Settings) -> str | None:
    """Prefer metadata.media_filename over hook-provided archive_path."""
    if event.document_id:
        resolved = await resolve_archive_path_from_paperless(event.document_id, settings)
        if resolved:
            return resolved
    return event.archive_path


@router.post("/paperless")
async def paperless_post_consume(
    event: PaperlessEvent,
    _: None = Depends(_check_api_key),
    session: AsyncSession = Depends(get_session),
    client: OneCClient = Depends(get_one_c_client),
) -> dict[str, Any]:
    settings = get_settings()
    archive_path = await _archive_path_for_event(event, settings)
    result = await process_paperless_event(
        session,
        client,
        doc_type=event.doc_type,
        doc_date_str=event.created,
        file_name=event.file_name,
        original_filename=event.original_filename,
        correspondent=event.correspondent,
        archive_path=archive_path,
        download_url=event.download_url,
    )
    if event.document_id:
        result["tags"] = await apply_paperless_webhook_tags(
            document_id=event.document_id,
            result=result,
            settings=settings,
        )
    return result


@router.post("/paperless/batch")
async def paperless_batch(
    events: list[PaperlessEvent],
    _: None = Depends(_check_api_key),
    session: AsyncSession = Depends(get_session),
    client: OneCClient = Depends(get_one_c_client),
) -> list[dict[str, Any]]:
    settings = get_settings()
    payload: list[dict[str, Any]] = []
    for ev in events:
        row = ev.model_dump()
        row["archive_path"] = await _archive_path_for_event(ev, settings)
        payload.append(row)
    return await process_paperless_batch(session, client, payload)
