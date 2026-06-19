import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_inventory_log_requires_auth(client: AsyncClient):
    resp = await client.get("/api/inventory-log")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_inventory_log_list(client: AsyncClient, auth_headers):
    resp = await client.get("/api/inventory-log", headers=auth_headers)
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_inventory_log_summary(client: AsyncClient, auth_headers):
    resp = await client.get("/api/inventory-log/summary", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "total_entries" in data


@pytest.mark.asyncio
async def test_inventory_log_after_purchase(client: AsyncClient, auth_headers):
    # Create part
    r = await client.post("/api/parts", json={
        "name": "Battery",
        "sku": "BAT-001",
        "stock_qty": 5,
        "unit_price": 20.0,
        "selling_price": 35.0,
    }, headers=auth_headers)
    part_id = r.json()["id"]

    # Create supplier
    r = await client.post("/api/suppliers", json={
        "name": "Supplier A",
    }, headers=auth_headers)
    supplier_id = r.json()["id"]

    # Create PO
    r = await client.post("/api/purchase-orders", json={
        "po_number": "PO-TEST-001",
        "supplier_id": supplier_id,
        "items": [{
            "part_name": "Battery",
            "qty_ordered": 10,
            "qty_received": 10,
            "cost_price": 20.0,
            "selling_price": 35.0,
            "part_id": part_id,
        }],
    }, headers=auth_headers)
    po_id = r.json()["id"]

    # Mark received
    resp = await client.patch(f"/api/purchase-orders/{po_id}/receive", headers=auth_headers)
    assert resp.status_code == 200

    # Check inventory log
    resp = await client.get("/api/inventory-log", headers=auth_headers)
    entries = resp.json()
    assert any(e["reason"] == "purchase_receipt" for e in entries)
