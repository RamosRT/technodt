import uuid
from datetime import datetime

from app.models import OneCDocument
from app.services.paperless import (
    _normalize_partner_name,
    _partner_name_score,
    find_matching_document,
)


def _doc(
    *,
    number: str,
    print_number: str,
    doc_date,
    partner_name: str,
) -> OneCDocument:
    return OneCDocument(
        guid=uuid.uuid4(),
        number=number,
        print_number=print_number,
        doc_date=doc_date,
        is_correction=False,
        partner_name=partner_name,
        is_edo=False,
        is_deleted=False,
    )


def test_normalize_partner_name_removes_legal_form_and_expands_abbreviations():
    assert _normalize_partner_name("ТД СОЮЗСПЕЦОДЕЖДА ООО") == "союзспецодежда"
    assert _normalize_partner_name("ООО «Торговый Дом  «СоюзСпецодежда»") == "союзспецодежда"
    assert _normalize_partner_name("КАП АО") == "казанское авиапредприятие"


def test_partner_name_score_matches_reordered_legal_form():
    assert _partner_name_score(
        "ТАТХИМФАРМПРЕПАРАТЫ АО",
        'АО "Татхимфармпрепараты"',
    ) == 1.0


async def test_find_matching_document_matches_td_abbreviation(db_session):
    db_session.add(
        _doc(
            number="ТАУТ-0000670",
            print_number="УТ-670",
            doc_date=datetime.fromisoformat("2026-02-05").date(),
            partner_name="ООО «Торговый Дом  «СоюзСпецодежда»",
        )
    )
    await db_session.commit()

    match = await find_matching_document(
        db_session,
        doc_date=datetime.fromisoformat("2026-02-05"),
        doc_number="УТ-670",
        correspondent="ТД СОЮЗСПЕЦОДЕЖДА ООО",
    )

    assert match is not None
    assert match.print_number == "УТ-670"


async def test_find_matching_document_matches_known_short_alias(db_session):
    db_session.add(
        _doc(
            number="ТАУТ-0000702",
            print_number="УТ-702",
            doc_date=datetime.fromisoformat("2026-02-05").date(),
            partner_name='АО "Казанское Авиапредприятие"',
        )
    )
    await db_session.commit()

    match = await find_matching_document(
        db_session,
        doc_date=datetime.fromisoformat("2026-02-05"),
        doc_number="УТ-702",
        correspondent="КАП АО",
    )

    assert match is not None
    assert match.print_number == "УТ-702"


async def test_find_matching_document_requires_document_date(db_session):
    db_session.add(
        _doc(
            number="ТАУТ-0000702",
            print_number="УТ-702",
            doc_date=datetime.fromisoformat("2026-02-05").date(),
            partner_name='АО "Казанское Авиапредприятие"',
        )
    )
    await db_session.commit()

    match = await find_matching_document(
        db_session,
        doc_date=datetime.fromisoformat("2026-02-06"),
        doc_number="УТ-702",
        correspondent="КАП АО",
    )

    assert match is None
