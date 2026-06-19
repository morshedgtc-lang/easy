import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_create_customer(client: AsyncClient, auth_headers):
    resp = await client.post("/api/customers", json={
        "name": "John Doe",
        "phone": "5551234",
        "email": "john@test.com",
    }, headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "John Doe"


@pytest.mark.asyncio
async def test_list_customers(client: AsyncClient, auth_headers):
    await client.post("/api/customers", json={
        "name": "Jane",
        "phone": "5559999",
    }, headers=auth_headers)
    resp = await client.get("/api/customers", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) >= 1


@pytest.mark.asyncio
async def test_update_customer(client: AsyncClient, auth_headers):
    r = await client.post("/api/customers", json={
        "name": "To Update",
        "phone": "1111111",
    }, headers=auth_headers)
    cid = r.json()["id"]
    resp = await client.put(f"/api/customers/{cid}", json={
        "name": "Updated Name",
        "phone": "1111111",
    }, headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["name"] == "Updated Name"
