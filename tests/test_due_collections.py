import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_due_collection_requires_auth(client: AsyncClient):
    resp = await client.get("/api/due-collections")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_due_collection_list(client: AsyncClient, auth_headers):
    resp = await client.get("/api/due-collections", headers=auth_headers)
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_due_collection_balances(client: AsyncClient, auth_headers):
    resp = await client.get("/api/due-collections/balances", headers=auth_headers)
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


@pytest.mark.asyncio
async def test_create_due_collection(client: AsyncClient, auth_headers):
    # Create customer
    r = await client.post("/api/customers", json={
        "name": "Due Customer",
        "phone": "5552222",
    }, headers=auth_headers)
    customer_id = r.json()["id"]

    # Create repair for the customer
    r = await client.post("/api/repairs", json={
        "customer_id": customer_id,
        "model": "iPhone 15",
        "issues": "Cracked screen",
        "estimated_cost": 200.0,
    }, headers=auth_headers)
    repair_id = r.json()["id"]

    # Create due collection
    resp = await client.post("/api/due-collections", json={
        "customer_id": customer_id,
        "repair_id": repair_id,
        "amount": 100.0,
        "currency": "USD",
        "method": "cash",
        "date": "2026-06-20",
        "note": "Partial payment",
    }, headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["amount"] == 100.0
