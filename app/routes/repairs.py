from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, func as sqlfunc
from typing import Optional
from datetime import date

from app.database import get_db
from app.models.repair import Repair
from app.models.customer import Customer
from app.models.user import User
from app.models.part import Part
from app.models.repair_part import RepairPart
from app.models.payment import Payment
from app.schemas.repair import (
    RepairCreate, RepairUpdate, RepairStatusUpdate, RepairResponse,
    RepairPartResponse, RepairPaymentResponse,
    VALID_TRANSITIONS, CANCELLABLE_STATUSES,
)
from app.utils.auth import get_current_user
from app.utils.permissions import (
    require_reception, require_technician,
    require_reception_or_technician, require_reception_or_admin,
    require_admin, can_cancel_repair,
)
from app.utils.ws_manager import ws_manager
from app.utils.cash_ledger import record_cash_entry
from app.utils.inventory_log import record_stock_change

router = APIRouter(prefix="/api/repairs", tags=["repairs"])


async def build_repair_response(r: Repair, db) -> RepairResponse:
    cust = await db.get(Customer, r.customer_id) if r.customer_id else None
    assigned_user = await db.get(User, r.assigned_to) if r.assigned_to else None
    creator = await db.get(User, r.created_by)

    rps = (await db.execute(select(RepairPart).where(RepairPart.repair_id == r.id))).scalars().all()
    total_parts_cost = sum(rp.qty * rp.selling_price for rp in rps)

    pay_result = await db.execute(
        select(sqlfunc.coalesce(sqlfunc.sum(Payment.amount), 0)).where(Payment.repair_id == r.id)
    )
    total_payments = float(pay_result.scalar() or 0)

    part_ids = list(set(rp.part_id for rp in rps if rp.part_id))
    part_map = {}
    if part_ids:
        pr = await db.execute(select(Part).where(Part.id.in_(part_ids)))
        part_map = {p.id: p.name for p in pr.scalars().all()}

    parts = [
        RepairPartResponse(
            id=rp.id, part_id=rp.part_id, qty=rp.qty,
            unit_price=rp.unit_price, selling_price=rp.selling_price,
            returned_qty=rp.returned_qty,
            part_name=part_map.get(rp.part_id) or "",
        )
        for rp in rps
    ]

    pay_rows = (await db.execute(select(Payment).where(Payment.repair_id == r.id))).scalars().all()
    payments = [
        RepairPaymentResponse(
            id=p.id, amount=p.amount, currency=p.currency,
            method=p.method, notes=p.notes, paid_at=p.paid_at,
        )
        for p in pay_rows
    ]

    balance = (total_parts_cost + (r.service_fee or 0)) - total_payments

    return RepairResponse(
        id=r.id, customer_id=r.customer_id,
        customer_name=cust.name if cust else "",
        assigned_to=r.assigned_to,
        assigned_user_name=assigned_user.name if assigned_user else "",
        created_by=r.created_by,
        creator_name=creator.name if creator else "",
        status=r.status, model=r.model, issues=r.issues,
        imei=r.imei or "", estimated_cost=r.estimated_cost or 0,
        actual_cost=r.actual_cost or 0, service_fee=r.service_fee or 0,
        payment_status=r.payment_status or "UNPAID",
        notes=r.notes or "", created_at=r.created_at, updated_at=r.updated_at,
        parts=parts, payments=payments,
        total_parts_cost=total_parts_cost,
        total_payments=total_payments,
        balance=balance,
    )


@router.get("", response_model=dict)
async def list_repairs(
    status_filter: Optional[str] = Query(None, alias="status"),
    search: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    db=Depends(get_db),
    current_user=Depends(get_current_user),
):
    query = select(Repair)
    count_stmt = select(sqlfunc.count(Repair.id))
    if status_filter:
        query = query.where(Repair.status == status_filter)
        count_stmt = count_stmt.where(Repair.status == status_filter)
    if search:
        term = f"%{search}%"
        query = query.outerjoin(Customer, Repair.customer_id == Customer.id).where(
            Customer.name.ilike(term) | Repair.model.ilike(term) | Repair.imei.ilike(term)
        )
        count_stmt = count_stmt.where(
            Repair.id.in_(
                select(Repair.id).outerjoin(Customer, Repair.customer_id == Customer.id).where(
                    Customer.name.ilike(term) | Repair.model.ilike(term) | Repair.imei.ilike(term)
                )
            )
        )
    total = (await db.execute(count_stmt)).scalar() or 0
    rows = (
        (await db.execute(query.order_by(Repair.created_at.desc()).offset((page - 1) * limit).limit(limit)))
        .scalars().unique().all()
    )
    items = [await build_repair_response(r, db) for r in rows]
    return {
        "items": items, "total": total, "page": page,
        "limit": limit, "pages": (total + limit - 1) // limit,
    }


@router.post("", response_model=RepairResponse, status_code=status.HTTP_201_CREATED)
async def create_repair(
    data: RepairCreate,
    db=Depends(get_db),
    current_user=Depends(require_reception_or_technician),
):
    customer_id = data.customer_id
    if not customer_id and (data.customer_name or data.customer_phone):
        if data.customer_phone:
            existing = (await db.execute(
                select(Customer).where(Customer.phone == data.customer_phone)
            )).scalar_one_or_none()
            if existing:
                customer_id = existing.id
        if not customer_id:
            cust = Customer(name=data.customer_name or "Walk-in", phone=data.customer_phone or "")
            db.add(cust)
            await db.flush()
            customer_id = cust.id

    repair = Repair(
        customer_id=customer_id, created_by=current_user.id,
        model=data.model, issues=data.issues, imei=data.imei,
        estimated_cost=data.estimated_cost, service_fee=data.service_fee,
        assigned_to=data.assigned_to, notes=data.notes,
    )
    db.add(repair)
    await db.commit()
    await db.refresh(repair)
    await ws_manager.broadcast("repair_created", {"repair_id": repair.id, "model": repair.model})
    return await build_repair_response(repair, db)


@router.get("/{repair_id}", response_model=RepairResponse)
async def get_repair(
    repair_id: int,
    db=Depends(get_db),
    current_user=Depends(get_current_user),
):
    repair = await db.get(Repair, repair_id)
    if not repair:
        raise HTTPException(status_code=404, detail="Repair not found")
    return await build_repair_response(repair, db)


@router.put("/{repair_id}", response_model=RepairResponse)
async def update_repair(
    repair_id: int,
    data: RepairUpdate,
    db=Depends(get_db),
    current_user=Depends(get_current_user),
):
    repair = await db.get(Repair, repair_id)
    if not repair:
        raise HTTPException(status_code=404, detail="Repair not found")
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(repair, key, value)
    await db.commit()
    await db.refresh(repair)
    return await build_repair_response(repair, db)


@router.put("/{repair_id}/status", response_model=RepairResponse)
async def update_repair_status(
    repair_id: int,
    data: RepairStatusUpdate,
    db=Depends(get_db),
    current_user=Depends(get_current_user),
):
    repair = await db.get(Repair, repair_id)
    if not repair:
        raise HTTPException(status_code=404, detail="Repair not found")
    allowed = VALID_TRANSITIONS.get(repair.status, set())
    if data.status not in allowed:
        raise HTTPException(status_code=400, detail=f"Invalid transition from '{repair.status}' to '{data.status}'")
    repair.status = data.status
    await db.commit()
    await db.refresh(repair)
    await ws_manager.broadcast("repair_status_changed", {"repair_id": repair.id, "new_status": repair.status})
    return await build_repair_response(repair, db)


@router.post("/{repair_id}/parts", response_model=RepairPartResponse, status_code=201)
async def add_repair_part(
    repair_id: int,
    part_id: int = Query(...),
    qty: int = Query(1, ge=1),
    selling_price: float = Query(0),
    db=Depends(get_db),
    current_user=Depends(require_technician),
):
    repair = await db.get(Repair, repair_id)
    if not repair:
        raise HTTPException(status_code=404, detail="Repair not found")
    part = (await db.execute(select(Part).where(Part.id == part_id).with_for_update())).scalar_one_or_none()
    if not part:
        raise HTTPException(status_code=404, detail="Part not found")
    if part.stock_qty < qty:
        raise HTTPException(status_code=400, detail=f"Insufficient stock. Available: {part.stock_qty}")

    old_qty = part.stock_qty
    part.stock_qty -= qty

    await record_stock_change(
        db, part_id=part.id, change_qty=-qty,
        old_qty=old_qty, new_qty=part.stock_qty,
        reason="repair_use", reference_type="repair",
        reference_id=repair_id, reference_table="repair_parts",
        unit_cost=part.unit_price, created_by=current_user.id,
    )

    final_price = selling_price if selling_price > 0 else part.selling_price
    repair_part = RepairPart(
        repair_id=repair_id, part_id=part_id, qty=qty,
        unit_price=part.unit_price, selling_price=final_price,
    )
    db.add(repair_part)
    await db.commit()
    await db.refresh(repair_part)

    if repair.payment_status == "UNPAID":
        repair.payment_status = "PARTIAL"
        await db.commit()

    return RepairPartResponse(
        id=repair_part.id, part_id=repair_part.part_id, qty=repair_part.qty,
        unit_price=repair_part.unit_price, selling_price=repair_part.selling_price,
        returned_qty=repair_part.returned_qty, part_name=part.name,
    )


@router.delete("/{repair_id}/parts/{rp_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_repair_part(
    repair_id: int, rp_id: int,
    db=Depends(get_db),
    current_user=Depends(get_current_user),
):
    repair_part = (
        await db.execute(select(RepairPart).where(RepairPart.id == rp_id, RepairPart.repair_id == repair_id))
    ).scalar_one_or_none()
    if not repair_part:
        raise HTTPException(status_code=404, detail="Repair part not found")
    part = await db.get(Part, repair_part.part_id)
    if part:
        old_qty = part.stock_qty
        part.stock_qty += repair_part.qty
        await record_stock_change(
            db, part_id=part.id, change_qty=repair_part.qty,
            old_qty=old_qty, new_qty=part.stock_qty,
            reason="part_return", reference_type="repair",
            reference_id=repair_id, created_by=current_user.id,
        )
    await db.delete(repair_part)
    await db.commit()


@router.post("/{repair_id}/cancel")
async def cancel_repair(
    repair_id: int,
    db=Depends(get_db),
    current_user=Depends(get_current_user),
):
    repair = await db.get(Repair, repair_id)
    if not repair:
        raise HTTPException(status_code=404, detail="Repair not found")
    if not can_cancel_repair(repair.status, current_user):
        raise HTTPException(status_code=403, detail="No permission to cancel this repair")

    rps = (await db.execute(select(RepairPart).where(RepairPart.repair_id == repair_id))).scalars().all()
    for rp in rps:
        remaining = rp.qty - rp.returned_qty
        if remaining > 0:
            rp.returned_qty = rp.qty
            part = await db.get(Part, rp.part_id)
            if part:
                old_qty = part.stock_qty
                part.stock_qty += remaining
                await record_stock_change(
                    db, part_id=part.id, change_qty=remaining,
                    old_qty=old_qty, new_qty=part.stock_qty,
                    reason="part_return", reference_type="repair",
                    reference_id=repair_id, created_by=current_user.id,
                )

    pay_rows = (await db.execute(select(Payment).where(Payment.repair_id == repair_id))).scalars().all()
    for p in pay_rows:
        if p.amount > 0:
            refund = Payment(
                repair_id=repair_id, amount=-p.amount, currency=p.currency,
                method="cash", notes="Refund for cancelled repair",
                created_by=current_user.id,
            )
            db.add(refund)
            await record_cash_entry(
                db, type="refund", direction="OUT",
                amount=p.amount, currency=p.currency,
                reference_type="repair", reference_id=repair_id,
                payment_method="cash", note="Refund for cancelled repair",
                created_by=current_user.id,
            )

    repair.status = "CANCELLED"
    await db.commit()
    await ws_manager.broadcast("repair_cancelled", {"repair_id": repair.id})
    return {"message": "Repair cancelled", "repair_id": repair.id}
