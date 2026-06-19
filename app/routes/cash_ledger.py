from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, func as sqlfunc
from typing import Optional

from app.database import get_db
from app.models.cash_ledger import CashLedger
from app.schemas.cash_ledger import CashLedgerEntry, CashLedgerResponse
from app.utils.auth import get_current_user
from app.utils.permissions import require_admin
from app.utils.cash_ledger import record_cash_entry

router = APIRouter(prefix="/api/cash-ledger", tags=["cash-ledger"])


@router.get("", response_model=dict)
async def list_entries(
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    type: Optional[str] = Query(None),
    direction: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200),
    db=Depends(get_db),
    current_user=Depends(get_current_user),
):
    count_stmt = select(sqlfunc.count(CashLedger.id))
    list_stmt = select(CashLedger)
    if date_from:
        count_stmt = count_stmt.where(CashLedger.date >= date_from)
        list_stmt = list_stmt.where(CashLedger.date >= date_from)
    if date_to:
        count_stmt = count_stmt.where(CashLedger.date <= date_to)
        list_stmt = list_stmt.where(CashLedger.date <= date_to)
    if type:
        count_stmt = count_stmt.where(CashLedger.type == type)
        list_stmt = list_stmt.where(CashLedger.type == type)
    if direction:
        count_stmt = count_stmt.where(CashLedger.direction == direction)
        list_stmt = list_stmt.where(CashLedger.direction == direction)
    total = (await db.execute(count_stmt)).scalar() or 0
    rows = (
        (await db.execute(list_stmt.order_by(CashLedger.created_at.desc()).offset((page - 1) * limit).limit(limit)))
        .scalars().all()
    )
    return {
        "items": [CashLedgerResponse.model_validate(r) for r in rows],
        "total": total, "page": page, "limit": limit,
        "pages": (total + limit - 1) // limit,
    }


@router.get("/summary")
async def summary(
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    db=Depends(get_db),
    current_user=Depends(get_current_user),
):
    query = select(CashLedger)
    if date_from:
        query = query.where(CashLedger.date >= date_from)
    if date_to:
        query = query.where(CashLedger.date <= date_to)
    rows = (await db.execute(query)).scalars().all()

    total_in = sum(r.amount for r in rows if r.direction == "IN")
    total_out = sum(r.amount for r in rows if r.direction == "OUT")
    by_type = {}
    by_method = {}
    for r in rows:
        by_type[r.type] = by_type.get(r.type, 0) + r.amount
        by_method[r.payment_method] = by_method.get(r.payment_method, 0) + r.amount

    return {
        "total_in": total_in,
        "total_out": total_out,
        "net": total_in - total_out,
        "by_type": by_type,
        "by_method": by_method,
        "count": len(rows),
    }


@router.get("/balance")
async def balance(
    db=Depends(get_db),
    current_user=Depends(get_current_user),
):
    rows = (await db.execute(select(CashLedger))).scalars().all()
    total_in = sum(r.amount for r in rows if r.direction == "IN")
    total_out = sum(r.amount for r in rows if r.direction == "OUT")
    return {"balance": total_in - total_out, "total_in": total_in, "total_out": total_out}


@router.post("", status_code=201)
async def create_manual_entry(
    data: CashLedgerEntry,
    db=Depends(get_db),
    current_user=Depends(require_admin),
):
    await record_cash_entry(
        db, date=data.date, type=data.type, direction=data.direction,
        amount=data.amount, currency=data.currency,
        reference_type=data.reference_type, reference_id=data.reference_id,
        reference_table=data.reference_table, reference_pk=data.reference_pk,
        payment_method=data.payment_method, note=data.note,
        created_by=current_user.id,
    )
    await db.commit()
    return {"message": "Entry recorded"}
