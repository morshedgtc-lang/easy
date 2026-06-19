import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_cash_ledger_requires_auth(client: AsyncClient):
    resp = await client.get("/api/cash-ledger")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_cash_ledger_list(client: AsyncClient, auth_headers):
    resp = await client.get("/api/cash-ledger", headers=auth_headers)
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_cash_ledger_summary(client: AsyncClient, auth_headers):
    resp = await client.get("/api/cash-ledger/summary", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "total_in" in data
    assert "total_out" in data


@pytest.mark.asyncio
async def test_cash_ledger_balance(client: AsyncClient, auth_headers):
    resp = await client.get("/api/cash-ledger/balance", headers=auth_headers)
    assert resp.status_code == 200
    assert "balance" in resp.json()


@pytest.mark.asyncio
async def test_manual_cash_entry(client: AsyncClient, auth_headers):
    resp = await client.post("/api/cash-ledger", json={
        "date": "2026-06-20",
        "type": "manual",
        "direction": "IN",
        "amount": 100.0,
        "currency": "USD",
        "payment_method": "cash",
        "note": "Test manual entry",
    }, headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["amount"] == 100.0
    assert data["type"] == "manual"
