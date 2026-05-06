"""Background 1C timestamp marking."""

import asyncio
import logging
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from app.models.envelope_document import EnvelopeDocument
from app.models.onec_mark_log import OneCMarkLog
from app.services.audit import write_event
from app.services.odata import (
    MARK_ELIGIBLE_ENTITIES,
    PROP_REGISTERED,
    PROP_SEALED,
    PROP_VERIFIED,
    OneCClient,
)

log = logging.getLogger(__name__)


class _SessionFactory(Protocol):
    def __call__(self): ...


@dataclass(frozen=True)
class Mark:
    envelope_id: uuid.UUID | None
    doc_guid: uuid.UUID
    doc_entity: str
    property_key: uuid.UUID
    property_name: str
    value: datetime


async def _send_marks(one_c: OneCClient, marks: list[Mark]) -> list[BaseException | None]:
    results = await asyncio.gather(
        *[
            one_c.mark_document(mark.doc_guid, mark.doc_entity, mark.property_key, mark.value)
            for mark in marks
        ],
        return_exceptions=True,
    )
    return [result if isinstance(result, BaseException) else None for result in results]


async def _write_mark_logs(
    session_factory: _SessionFactory,
    successes: list[Mark],
    failures: list[tuple[Mark, BaseException]],
) -> None:
    if not successes and not failures:
        return
    async with session_factory() as session:
        for mark in successes:
            session.add(
                OneCMarkLog(
                    envelope_id=mark.envelope_id,
                    doc_guid=mark.doc_guid,
                    doc_entity=mark.doc_entity,
                    property_key=mark.property_key,
                    property_name=mark.property_name,
                    status="success",
                    error=None,
                )
            )
        for mark, exc in failures:
            session.add(
                OneCMarkLog(
                    envelope_id=mark.envelope_id,
                    doc_guid=mark.doc_guid,
                    doc_entity=mark.doc_entity,
                    property_key=mark.property_key,
                    property_name=mark.property_name,
                    status="failed",
                    error=str(exc),
                )
            )
            await write_event(
                session,
                envelope_id=mark.envelope_id,
                event="onec_mark_failed",
                actor="system",
                payload={
                    "doc_guid": str(mark.doc_guid),
                    "doc_entity": mark.doc_entity,
                    "property_key": str(mark.property_key),
                    "property_name": mark.property_name,
                    "error": str(exc),
                },
            )
        await session.commit()


async def _mark_documents_with_retry(
    one_c: OneCClient,
    marks: list[Mark],
    session_factory: _SessionFactory,
) -> None:
    first_results = await _send_marks(one_c, marks)
    successes = [mark for mark, exc in zip(marks, first_results, strict=True) if exc is None]
    failed = [(mark, exc) for mark, exc in zip(marks, first_results, strict=True) if exc is not None]

    if not failed:
        await _write_mark_logs(session_factory, successes, [])
        return

    log.warning("1C marks first attempt failed for %s mark(s); retrying in 5s", len(failed))
    await asyncio.sleep(5)

    retry_marks = [mark for mark, _ in failed]
    retry_results = await _send_marks(one_c, retry_marks)
    retry_successes = [
        mark for mark, exc in zip(retry_marks, retry_results, strict=True) if exc is None
    ]
    retry_failed = [
        (mark, exc) for mark, exc in zip(retry_marks, retry_results, strict=True) if exc is not None
    ]
    if retry_failed:
        log.warning("1C marks retry failed for %s mark(s)", len(retry_failed))
    await _write_mark_logs(session_factory, successes + retry_successes, retry_failed)


def fire_seal_marks(
    one_c: OneCClient,
    envelope_id: uuid.UUID,
    docs: list[EnvelopeDocument],
    sealed_at: datetime,
    session_factory: _SessionFactory,
    *,
    enabled: bool = True,
) -> None:
    if not enabled:
        return
    eligible = [doc for doc in docs if doc.doc_entity in MARK_ELIGIBLE_ENTITIES]
    if not eligible:
        return
    marks: list[Mark] = []
    for doc in eligible:
        marks.append(
            Mark(
                envelope_id,
                doc.doc_guid,
                doc.doc_entity,
                PROP_REGISTERED,
                "Зарегистрирован",
                doc.added_at,
            )
        )
        marks.append(
            Mark(
                envelope_id,
                doc.doc_guid,
                doc.doc_entity,
                PROP_SEALED,
                "Запечатан",
                sealed_at,
            )
        )
    asyncio.create_task(_mark_documents_with_retry(one_c, marks, session_factory))


def fire_verify_marks(
    one_c: OneCClient,
    envelope_id: uuid.UUID,
    docs: list[EnvelopeDocument],
    verified_at: datetime,
    session_factory: _SessionFactory,
    *,
    enabled: bool = True,
) -> None:
    if not enabled:
        return
    eligible = [
        doc
        for doc in docs
        if doc.doc_entity in MARK_ELIGIBLE_ENTITIES and doc.scanned_at_verification is not None
    ]
    if not eligible:
        return
    marks = [
        Mark(
            envelope_id,
            doc.doc_guid,
            doc.doc_entity,
            PROP_VERIFIED,
            "Проверен",
            verified_at,
        )
        for doc in eligible
    ]
    asyncio.create_task(_mark_documents_with_retry(one_c, marks, session_factory))
