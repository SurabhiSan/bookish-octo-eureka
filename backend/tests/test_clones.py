import pytest


async def _headers(client, email: str = "clone@test.com") -> dict:
    await client.post("/auth/register", json={"email": email, "password": "pass"})
    r = await client.post("/auth/login", json={"email": email, "password": "pass"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.mark.asyncio
async def test_clone_lifecycle(client):
    h = await _headers(client)

    # Create
    res = await client.post("/clones", json={"name": "Einstein"}, headers=h)
    assert res.status_code == 201
    clone = res.json()
    assert clone["name"] == "Einstein"
    assert clone["vector_namespace"].startswith("persona_")

    # List
    res2 = await client.get("/clones", headers=h)
    assert any(c["id"] == clone["id"] for c in res2.json())

    # Empty name
    res3 = await client.post("/clones", json={"name": ""}, headers=h)
    assert res3.status_code == 422

    # Cross-user blocked
    h2 = await _headers(client, "other@test.com")
    res4 = await client.get(f"/clones/{clone['id']}", headers=h2)
    assert res4.status_code in (403, 404)

    # Delete
    del_res = await client.delete(f"/clones/{clone['id']}", headers=h)
    assert del_res.status_code == 204

    res5 = await client.get(f"/clones/{clone['id']}", headers=h)
    assert res5.status_code == 404
