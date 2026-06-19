from datetime import date
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, func as sqlfunc
from typing import Optional

from app.database import get_db
from app.models.supplier import Supplier
from app.models.supplier_payment import SupplierPayment
from app.models.purchase_order import PurchaseOrder, PurchaseOrderItem
from app.schemas.supplier import (
    SupplierCreate, SupplierUpdate, SupplierResponse,
    SupplierPaymentCreate, SupplierPaymentResponse,
)
from app.utils.auth import get_current_user
from app.utils.permissions import require_warehouse_or_admin, require_admin
from app.utils.cash_ledger import record_cash_entry

router = APIRouter(prefix="/api/suppliers", tags=["suppliers"])


@router.get("", response_model=dict)
async def list_suppliers(
    search: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    db=Depends(get_db),
    current_user=Depends(get_current_user),
):
    count_stmt = select(sqlfunc.count(Supplier.id))
    list_stmt = select(Supplier)
    if search:
        term = f"%{search}%"
        count_stmt = count_stmt.where(Supplier.name.ilike(term))
        list_stmt = list_stmt.where(Supplier.name.ilike(term))
    total = (await db.execute(count_stmt)).scalar() or 0
    rows = (
        (await db.execute(list_stmt.order_by(Supplier.created_at.desc()).offset((page - 1) * limit).limit(limit)))
        .scalars().all()
    )
    return {
        "items": [SupplierResponse.model_validate(s) for s in rows],
        "total": total, "page": page, "limit": limit,
        "pages": (total + limit - 1) // limit,
    }


@router.post("", response_model=SupplierResponse, status_code=201)
async def create_supplier(
    data: SupplierCreate,
    db=Depends(get_db),
    current_user=Depends(require_warehouse_or_admin),
):
    supplier = Supplier(name=data.name, phone=data.phone, address=data.address, notes=data.notes)
    db.add(supplier)
    await db.commit()
    await db.refresh(supplier)
    return supplier


@router.get("/payable-summary")
async def payable_summary(
    db=Depends(get_db),
    current_user=Depends(get_current_user),
):
    suppliers = (await db.execute(select(Supplier))).scalars().all()
    total_payable = 0
    supplier_payables = []
    for s in suppliers:
        pos = (await db.execute(
            select(PurchaseOrder).where(
                PurchaseOrder.supplier_id == s.id,
                PurchaseOrder.payment_type == "credit",
                PurchaseOrder.status.in_(["sent", "partially_received", "received"]),
            )
        )).scalars().all()
        owed = 0
        for po in pos:
            items = (await db.execute(
                select(PurchaseOrderItem).where(PurchaseOrderItem.po_id == po.id)
            )).scalars().all()
            for item in items:
                owed += item.cost_price * item.qty_received
        payments = (await db.execute(
            select(sqlfunc.coalesce(sqlfunc.sum(SupplierPayment.amount), 0)).where(
                SupplierPayment.supplier_id == s.id
            )
        )).scalar() or 0
        balance = owed - float(payments)
        if balance > 0:
            total_payable += balance
            supplier_payables.append({"supplier_id": s.id, "name": s.name, "payable": balance})
    return {"total_payable": total_payable, "suppliers": supplier_payables}


@router.get("/{supplier_id}", response_model=SupplierResponse)
async def get_supplier(
    supplier_id: int,
    db=Depends(get_db),
    current_user=Depends(get_current_user),
):
    supplier = await db.get(Supplier, supplier_id)
    if not supplier:
        raise HTTPException(status_code=404, detail="Supplier not found")
    return supplier


@router.put("/{supplier_id}", response_model=SupplierResponse)
async def update_supplier(
    supplier_id: int,
    data: SupplierUpdate,
    db=Depends(get_db),
    current_user=Depends(require_warehouse_or_admin),
):
    supplier = await db.get(Supplier, supplier_id)
    if not supplier:
        raise HTTPException(status_code=404, detail="Supplier not found")
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(supplier, key, value)
    await db.commit()
    await db.refresh(supplier)
    return supplier


@router.delete("/{supplier_id}", status_code=204)
async def delete_supplier(
    supplier_id: int,
    db=Depends(get_db),
    current_user=Depends(require_admin),
):
    supplier = await db.get(Supplier, supplier_id)
    if not supplier:
        raise HTTPException(status_code=404, detail="Supplier not found")
    await db.delete(supplier)
    await db.commit()


@router.get("/{supplier_id}/payments", response_model=list[SupplierPaymentResponse])
async def list_supplier_payments(
    supplier_id: int,
    db=Depends(get_db),
    current_user=Depends(get_current_user),
):
    rows = (
        await db.execute(
            select(SupplierPayment).where(SupplierPayment.supplier_id == supplier_id)
            .order_by(SupplierPayment.created_at.desc())
        )
    ).scalars().all()
    return rows


@router.post("/{supplier_id}/payments", response_model=SupplierPaymentResponse, status_code=201)
async def create_supplier_payment(
    supplier_id: int,
    data: SupplierPaymentCreate,
    db=Depends(get_db),
    current_user=Depends(require_warehouse_or_admin),
):
    supplier = await db.get(Supplier, supplier_id)
    if not supplier:
        raise HTTPException(status_code=404, detail="Supplier not found")
    pay_date = data.date or date.today().isoformat()
    payment = SupplierPayment(
        supplier_id=supplier_id, amount=data.amount,
        method=data.method, date=pay_date,
        notes=data.notes, created_by=current_user.id,
    )
    db.add(payment)
    await db.flush()

    await record_cash_entry(
        db, type="supplier_payment", direction="OUT",
        amount=data.amount, currency=data.currency,
        reference_type="supplier", reference_id=supplier_id,
        reference_table="supplier_payments", reference_pk=payment.id,
        payment_method=data.method, note=data.notes or f"Payment to {supplier.name}",
        created_by=current_user.id,
    )

    await db.commit()
    await db.refresh(payment)
    return payment
