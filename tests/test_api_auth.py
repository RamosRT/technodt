import pytest

from app.services.operators import ensure_operator


@pytest.mark.asyncio
async def test_login_sets_cookie(client, db_session):
    await ensure_operator(db_session, "Иванов", password="1234")
    await db_session.commit()
    r = await client.post("/api/auth/login", json={"username": "Иванов", "password": "1234"})

    assert r.status_code == 200
    assert r.json() == {
        "ok": True,
        "operator": "Иванов",
        "assigned_zpl_printer_id": None,
        "assigned_a4_printer_id": None,
    }
    assert "operator_name" in client.cookies


@pytest.mark.asyncio
async def test_login_does_not_register_unknown_operator(client):
    r = await client.post("/api/auth/login", json={"username": "Новый", "password": "1234"})

    assert r.status_code == 401
    assert r.json()["code"] == "operator_required"


@pytest.mark.asyncio
async def test_me_returns_operator_with_valid_cookie(client, db_session):
    await ensure_operator(db_session, "Петров", password="1234")
    await db_session.commit()
    await client.post("/api/auth/login", json={"username": "Петров", "password": "1234"})

    r = await client.get("/api/auth/me")

    assert r.status_code == 200
    assert r.json() == {"operator": "Петров", "is_admin": False}


@pytest.mark.asyncio
async def test_me_returns_401_without_cookie(client):
    r = await client.get("/api/auth/me")

    assert r.status_code == 401
    assert r.json()["code"] == "operator_required"


@pytest.mark.asyncio
async def test_inactive_operator_cannot_login(client, db_session):
    op = await ensure_operator(db_session, "Сидоров", password="1234")
    op.is_active = False
    await db_session.commit()

    r = await client.post("/api/auth/login", json={"username": "Сидоров", "password": "1234"})

    assert r.status_code == 401
    assert r.json()["code"] == "operator_required"


@pytest.mark.asyncio
async def test_login_reports_bootstrap_admin(client, monkeypatch):
    monkeypatch.setenv("BOOTSTRAP_ADMIN", "Главный")
    from app.config import get_settings

    get_settings.cache_clear()
    try:
        await client.post("/api/auth/login", json={"username": "Главный", "password": "0000"})
        r = await client.get("/api/auth/me")
    finally:
        get_settings.cache_clear()

    assert r.status_code == 200
    assert r.json() == {"operator": "Главный", "is_admin": True}


@pytest.mark.asyncio
async def test_logout_clears_cookie(client, db_session):
    await ensure_operator(db_session, "Иванов", password="1234")
    await db_session.commit()
    await client.post("/api/auth/login", json={"username": "Иванов", "password": "1234"})

    r = await client.post("/api/auth/logout")

    assert r.status_code == 204
    assert "operator_name" not in client.cookies


@pytest.mark.asyncio
async def test_ui_documents_allows_operator(client, db_session):
    await ensure_operator(db_session, "Оператор", password="1234")
    await db_session.commit()
    await client.post("/api/auth/login", json={"username": "Оператор", "password": "1234"})

    r = await client.get("/ui/documents")

    assert r.status_code == 200
    assert "documents-list-page" in r.text


@pytest.mark.asyncio
async def test_operator_dashboard_has_envelopes_and_documents_links(client, db_session):
    await ensure_operator(db_session, "Оператор", password="1234")
    await db_session.commit()
    await client.post("/api/auth/login", json={"username": "Оператор", "password": "1234"})

    r = await client.get("/")

    assert r.status_code == 200
    assert 'hx-get="/ui/envelopes"' in r.text
    assert 'hx-get="/ui/documents"' in r.text


@pytest.mark.asyncio
async def test_operator_can_see_unseal_control_on_sealed_envelope_card(client, db_session):
    from datetime import UTC, datetime

    from app.models import Envelope, EnvelopeStatus

    await ensure_operator(db_session, "Оператор", password="1234")
    envelope = Envelope(
        number="ТА-100001",
        barcode="1234567890123456",
        status=EnvelopeStatus.sealed,
        created_by="Оператор",
        created_at=datetime(2026, 7, 3, 9, 0, tzinfo=UTC),
        sealed_at=datetime(2026, 7, 3, 10, 0, tzinfo=UTC),
    )
    db_session.add(envelope)
    await db_session.commit()
    await client.post("/api/auth/login", json={"username": "Оператор", "password": "1234"})

    r = await client.get(f"/ui/envelopes/{envelope.id}/card")

    assert r.status_code == 200
    assert "Редактирование состава" in r.text
    assert "только Admin" not in r.text
    assert f'hx-post="/ui/envelopes/{envelope.id}/unseal"' in r.text
