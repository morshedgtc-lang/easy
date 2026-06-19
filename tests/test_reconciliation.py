import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_reconciliation_requires_auth(client: AsyncClient):
    resp = await client.get("/api/reconciliation/today")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_reconciliation_today(client: AsyncClient, auth_headers):
    resp = await client.get("/api/reconciliation/today", headers=auth_headers)
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_reconciliation_close_day(client: AsyncClient, auth_headers):
    resp = await client.post("/api/reconciliation/close", json={
        "date": "2026-06-20",
        "actual_close": 0.0,
        "notes": "Testing close",
    }, headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["date"] == "2026-06-20"


@pytest.mark.asyncio
async def test_reconciliation_double_close_fails(client: AsyncClient, auth_headers):
    await client.post("/api/reconciliation/close", json={
        "date": "2026-06-21",
        "actual_close": 0.0,
    }, headers=auth_headers)
    resp = await client.post("/api/reconciliation/close", json={
        "date": "2026-06-21",
        "actual_close": 0.0,
    }, headers=auth_headers)
    assert resp.status_code == 400
