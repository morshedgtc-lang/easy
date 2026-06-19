import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_supplier_requires_auth(client: AsyncClient):
    resp = await client.get("/api/suppliers")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_create_supplier(client: AsyncClient, auth_headers):
    resp = await client.post("/api/suppliers", json={
        "name": "Test Supplier",
        "phone": "5550000",
        "address": "123 Main St",
    }, headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["name"] == "Test Supplier"


@pytest.mark.asyncio
async def test_supplier_payable_summary(client: AsyncClient, auth_headers):
    resp = await client.get("/api/suppliers/payable-summary", headers=auth_headers)
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)
