import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_create_part(client: AsyncClient, auth_headers):
    resp = await client.post("/api/parts", json={
        "name": "Screen A1",
        "sku": "SCR-001",
        "stock_qty": 10,
        "unit_price": 50.0,
        "selling_price": 80.0,
    }, headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["sku"] == "SCR-001"


@pytest.mark.asyncio
async def test_list_parts(client: AsyncClient, auth_headers):
    resp = await client.get("/api/parts", headers=auth_headers)
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)
