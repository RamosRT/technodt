import pytest


@pytest.mark.asyncio
async def test_branches_post_get_patch(client):
    client.cookies.set("operator_name", "Ivan")
    r = await client.post("/api/branches", json={"name": "Москва"})
    assert r.status_code == 201
    branch = r.json()
    assert branch["is_active"] is True

    listed = (await client.get("/api/branches?active=true")).json()
    assert any(b["id"] == branch["id"] for b in listed)

    r = await client.patch(f"/api/branches/{branch['id']}", json={"is_active": False})
    assert r.status_code == 200

    listed = (await client.get("/api/branches?active=true")).json()
    assert all(b["id"] != branch["id"] for b in listed)


@pytest.mark.asyncio
async def test_signers_post_get_patch(client):
    client.cookies.set("operator_name", "Ivan")
    r = await client.post("/api/signers", json={"last_name": "Иванов", "first_name": "Иван"})
    assert r.status_code == 201
    s = r.json()

    listed = (await client.get("/api/signers?active=true")).json()
    assert any(x["id"] == s["id"] for x in listed)

    r = await client.patch(f"/api/signers/{s['id']}", json={"last_name": "Петров"})
    assert r.status_code == 200
    assert r.json()["last_name"] == "Петров"
