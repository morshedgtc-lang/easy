from datetime import date
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, func as sqlfunc
from typing import Optional

from app.database import get_db
from app.models.purchase_order import PurchaseOrder, PurchaseOrderItem
from app.models.supplier import Supplier
from app.models.part import Part
from app.models.user import User
from app.schemas.purchase_order import (
    PurchaseOrderCreate, PurchaseOrderResponse, PurchaseOrderItemResponse,
    PO_STATUSES, PO_VALID_TRANSITIONS,
)
from app.utils.auth import get_current_user
from app.utils.permissions import require_warehouse_or_admin
from app.utils.ws_manager import ws_manager
from app.utils.cash_ledger import record_cash_entry
from app.utils.inventory_log import record_stock_change

router = APIRouter(prefix="/api/purchase-orders", tags=["purchase-orders"])


async def generate_po_number(db) -> str:
    result = await db.execute(select(sqlfunc.max(PurchaseOrder.id)))
    max_id = result.scalar() or 0
    return f"PO-{max_id + 1:04d}"


async def build_po_response(po: PurchaseOrder, db) -> PurchaseOrderResponse:
    items = []
    total = 0
    po_items = (await db.execute(select(PurchaseOrderItem).where(PurchaseOrderItem.po_id == po.id))).scalars().all()
    for item in po_items:
        items.append(PurchaseOrderItemResponse(
            id=item.id, part_id=item.part_id, part_name=item.part_name or "",
            qty=item.qty_ordered, cost=item.cost_price,
            selling_price=item.selling_price, qty_received=item.qty_received,
            status=item.part_status,
        ))
        total += item.cost_price * item.qty_ordered
    sup = await db.get(Supplier, po.supplier_id)
    creator = await db.get(User, po.created_by)
    return PurchaseOrderResponse(
        id=po.id, po_number=po.po_number, supplier_id=po.supplier_id,
        supplier_name=sup.name if sup else "",
        status=po.status, payment_type=po.payment_type, notes=po.notes,
        total=total, created_by=po.created_by,
        creator_name=creator.name if creator else "",
        created_at=po.created_at, items=items,
    )


@router.get("", response_model=dict)
async def list_pos(
    status_filter: Optional[str] = Query(None, alias="status"),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    db=Depends(get_db),
    current_user=Depends(get_current_user),
):
    count_stmt = select(sqlfunc.count(PurchaseOrder.id))
    list_stmt = select(PurchaseOrder)
    if status_filter:
        count_stmt = count_stmt.where(PurchaseOrder.status == status_filter)
        list_stmt = list_stmt.where(PurchaseOrder.status == status_filter)
    total = (await db.execute(count_stmt)).scalar() or 0
    pos = (
        (await db.execute(list_stmt.order_by(PurchaseOrder.created_at.desc()).offset((page - 1) * limit).limit(limit)))
        .scalars().all()
    )
    return {
        "items": [await build_po_response(po, db) for po in pos],
        "total": total, "page": page, "limit": limit,
        "pages": (total + limit - 1) // limit,
    }


@router.post("", response_model=PurchaseOrderResponse, status_code=201)
async def create_po(
    data: PurchaseOrderCreate,
    db=Depends(get_db),
    current_user=Depends(require_warehouse_or_admin),
):
    po = PurchaseOrder(
        po_number=await generate_po_number(db),
        supplier_id=data.supplier_id, payment_type=data.payment_type,
        notes=data.notes, created_by=current_user.id,
    )
    db.add(po)
    await db.flush()
    for item_data in data.items:
        db.add(PurchaseOrderItem(
            po_id=po.id, part_id=item_data.part_id,
            part_name=item_data.part_name,
            qty_ordered=item_data.qty, cost_price=item_data.cost,
            selling_price=item_data.selling_price,
        ))
    await db.commit()
    await db.refresh(po)
    await ws_manager.broadcast("po_created", {"po_id": po.id, "po_number": po.po_number})
    return await build_po_response(po, db)


@router.get("/{po_id}", response_model=PurchaseOrderResponse)
async def get_po(po_id: int, db=Depends(get_db), current_user=Depends(get_current_user)):
    po = await db.get(PurchaseOrder, po_id)
    if not po:
        raise HTTPException(status_code=404, detail="Purchase order not found")
    return await build_po_response(po, db)


@router.put("/{po_id}/status", response_model=PurchaseOrderResponse)
async def update_po_status(
    po_id: int,
    data: dict,
    db=Depends(get_db),
    current_user=Depends(require_warehouse_or_admin),
):
    po = await db.get(PurchaseOrder, po_id)
    if not po:
        raise HTTPException(status_code=404, detail="Purchase order not found")
    new_status = data.get("status", "")
    if new_status not in PO_STATUSES:
        raise HTTPException(status_code=400, detail=f"Invalid status")
    allowed = PO_VALID_TRANSITIONS.get(po.status, set())
    if new_status not in allowed:
        raise HTTPException(status_code=400, detail=f"Invalid transition from '{po.status}' to '{new_status}'")
    po.status = new_status
    await db.commit()
    await db.refresh(po)
    await ws_manager.broadcast("po_status_changed", {"po_id": po.id, "new_status": po.status})
    return await build_po_response(po, db)


@router.post("/{po_id}/receive")
async def receive_shipment(
    po_id: int,
    data: dict,
    db=Depends(get_db),
    current_user=Depends(require_warehouse_or_admin),
):
    po = await db.get(PurchaseOrder, po_id)
    if not po:
        raise HTTPException(status_code=404, detail="Purchase order not found")
    if po.status in ("cancelled", "closed"):
        raise HTTPException(status_code=400, detail="Cannot receive for cancelled/closed PO")

    items_data = data.get("items", [])
    all_received = True
    for item_data in items_data:
        po_item = (await db.execute(
            select(PurchaseOrderItem).where(
                PurchaseOrderItem.id == item_data.get("po_item_id"),
                PurchaseOrderItem.po_id == po_id,
            )
        )).scalar_one_or_none()
        if not po_item:
            continue

        qty_recv = item_data.get("qty_received", 0)
        cost = item_data.get("cost_price", po_item.cost_price)

        po_item.qty_received += qty_recv
        po_item.cost_price = cost

        if po_item.qty_received >= po_item.qty_ordered:
            po_item.part_status = "received"
        elif po_item.qty_received > 0:
            po_item.part_status = "partial"
        else:
            all_received = False

        if qty_recv > 0 and po_item.part_id:
            part = (await db.execute(select(Part).where(Part.id == po_item.part_id).with_for_update())).scalar_one_or_none()
            if part:
                old_qty = part.stock_qty
                part.stock_qty += qty_recv
                part.unit_price = cost
                await record_stock_change(
                    db, part_id=part.id, change_qty=qty_recv,
                    old_qty=old_qty, new_qty=part.stock_qty,
                    reason="purchase_receipt", reference_type="purchase_order",
                    reference_id=po_id, reference_table="purchase_orders",
                    unit_cost=cost, created_by=current_user.id,
                )

    if po.payment_type == "cash":
        total_cost = sum(
            item_data.get("qty_received", 0) * item_data.get("cost_price", 0)
            for item_data in items_data
        )
        if total_cost > 0:
            await record_cash_entry(
                db, type="purchase", direction="OUT",
                amount=total_cost,
                reference_type="purchase_order", reference_id=po_id,
                reference_table="purchase_orders",
                note=f"PO {po.po_number} received",
                created_by=current_user.id,
            )

    po.status = "received" if all_received else "partially_received"
    await db.commit()
    await ws_manager.broadcast("po_received", {"po_id": po.id, "po_number": po.po_number})
    return {"message": "Shipment received", "status": po.status}
