from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, func as sqlfunc
from typing import Optional

from app.database import get_db
from app.models.payment import Payment
from app.models.repair import Repair
from app.schemas.payment import PaymentCreate, PaymentResponse
from app.utils.auth import get_current_user
from app.utils.permissions import require_warehouse_or_admin
from app.utils.ws_manager import ws_manager
from app.utils.cash_ledger import record_cash_entry

router = APIRouter(prefix="/api/payments", tags=["payments"])


@router.get("", response_model=dict)
async def list_payments(
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    method: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    db=Depends(get_db),
    current_user=Depends(get_current_user),
):
    count_stmt = select(sqlfunc.count(Payment.id))
    list_stmt = select(Payment)
    if date_from:
        count_stmt = count_stmt.where(Payment.paid_at >= date_from)
        list_stmt = list_stmt.where(Payment.paid_at >= date_from)
    if date_to:
        count_stmt = count_stmt.where(Payment.paid_at <= date_to + " 23:59:59")
        list_stmt = list_stmt.where(Payment.paid_at <= date_to + " 23:59:59")
    if method:
        count_stmt = count_stmt.where(Payment.method == method)
        list_stmt = list_stmt.where(Payment.method == method)
    total = (await db.execute(count_stmt)).scalar() or 0
    rows = (
        (await db.execute(list_stmt.order_by(Payment.paid_at.desc()).offset((page - 1) * limit).limit(limit)))
        .scalars().all()
    )
    return {
        "items": [PaymentResponse.model_validate(p) for p in rows],
        "total": total, "page": page, "limit": limit,
        "pages": (total + limit - 1) // limit,
    }


@router.post("", response_model=PaymentResponse, status_code=status.HTTP_201_CREATED)
async def create_payment(
    data: PaymentCreate,
    db=Depends(get_db),
    current_user=Depends(require_warehouse_or_admin),
):
    repair = await db.get(Repair, data.repair_id)
    if not repair:
        raise HTTPException(status_code=404, detail="Repair not found")

    payment = Payment(
        repair_id=data.repair_id, amount=data.amount,
        currency=data.currency, method=data.method,
        notes=data.notes, created_by=current_user.id,
    )
    db.add(payment)
    await db.flush()

    await record_cash_entry(
        db, type="payment", direction="IN",
        amount=data.amount, currency=data.currency,
        reference_type="repair", reference_id=data.repair_id,
        reference_table="payments", reference_pk=payment.id,
        payment_method=data.method, note=data.notes,
        created_by=current_user.id,
    )

    await db.commit()
    await db.refresh(payment)
    await ws_manager.broadcast("payment_received", {
        "payment_id": payment.id, "repair_id": payment.repair_id,
        "amount": payment.amount,
    })
    return payment


@router.get("/summary")
async def payment_summary(
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    db=Depends(get_db),
    current_user=Depends(get_current_user),
):
    query = select(Payment)
    if date_from:
        query = query.where(Payment.paid_at >= date_from)
    if date_to:
        query = query.where(Payment.paid_at <= date_to + " 23:59:59")
    payments = (await db.execute(query)).scalars().all()
    by_method = {}
    for p in payments:
        by_method[p.method] = by_method.get(p.method, 0) + p.amount
    return {
        "total": sum(p.amount for p in payments),
        "by_method": by_method,
        "count": len(payments),
    }


@router.delete("/{payment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_payment(
    payment_id: int,
    db=Depends(get_db),
    current_user=Depends(require_warehouse_or_admin),
):
    payment = await db.get(Payment, payment_id)
    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")

    await record_cash_entry(
        db, type="payment_delete", direction="OUT",
        amount=payment.amount, currency=payment.currency,
        reference_type="repair", reference_id=payment.repair_id,
        payment_method=payment.method, note="Payment deleted",
        created_by=current_user.id,
    )

    await db.delete(payment)
    await db.commit()
