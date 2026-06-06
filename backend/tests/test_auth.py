import pytest


@pytest.mark.asyncio
async def test_register_and_login(client):
    res = await client.post("/auth/register", json={"email": "test@example.com", "password": "secret123"})
    assert res.status_code == 201

    res2 = await client.post("/auth/register", json={"email": "test@example.com", "password": "secret123"})
    assert res2.status_code == 409

    res3 = await client.post("/auth/login", json={"email": "test@example.com", "password": "secret123"})
    assert res3.status_code == 200
    data = res3.json()
    assert "access_token" in data and "refresh_token" in data

    res4 = await client.post("/auth/login", json={"email": "test@example.com", "password": "wrong"})
    assert res4.status_code == 401


@pytest.mark.asyncio
async def test_protected_endpoint_requires_auth(client):
    res = await client.get("/clones")
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_refresh_token_rotation(client):
    await client.post("/auth/register", json={"email": "refresh@example.com", "password": "pass"})
    login = await client.post("/auth/login", json={"email": "refresh@example.com", "password": "pass"})
    refresh = login.json()["refresh_token"]

    res = await client.post("/auth/refresh", json={"refresh_token": refresh})
    assert res.status_code == 200
    assert res.json()["refresh_token"] != refresh

    # Reuse triggers 401
    res2 = await client.post("/auth/refresh", json={"refresh_token": refresh})
    assert res2.status_code == 401
