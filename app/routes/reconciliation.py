from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from typing import Optional

from app.database import get_db
from app.models.reconciliation import Reconciliation
from app.models.cash_ledger import CashLedger
from app.schemas.reconciliation import ReconciliationCreate, ReconciliationResponse
from app.utils.auth import get_current_user
from app.utils.permissions import require_admin
from app.utils.cash_ledger import record_cash_entry

router = APIRouter(prefix="/api/reconciliation", tags=["reconciliation"])


@router.get("", response_model=dict)
async def list_reconciliations(
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    db=Depends(get_db),
    current_user=Depends(get_current_user),
):
    query = select(Reconciliation)
    if date_from:
        query = query.where(Reconciliation.date >= date_from)
    if date_to:
        query = query.where(Reconciliation.date <= date_to)
    rows = (await db.execute(query.order_by(Reconciliation.date.desc()).offset((page - 1) * limit).limit(limit))).scalars().all()
    return {
        "items": [ReconciliationResponse.model_validate(r) for r in rows],
        "page": page, "limit": limit,
    }


@router.get("/today")
async def today_status(
    db=Depends(get_db),
    current_user=Depends(get_current_user),
):
    from datetime import date as _date
    today = _date.today().isoformat()
    existing = (await db.execute(select(Reconciliation).where(Reconciliation.date == today))).scalar_one_or_none()
    if existing:
        return {"closed": True, "reconciliation": ReconciliationResponse.model_validate(existing)}

    rows = (await db.execute(select(CashLedger).where(CashLedger.date == today))).scalars().all()
    total_in = sum(r.amount for r in rows if r.direction == "IN")
    total_out = sum(r.amount for r in rows if r.direction == "OUT")

    return {
        "closed": False,
        "date": today,
        "total_cash_in": total_in,
        "total_cash_out": total_out,
    }


@router.post("", response_model=ReconciliationResponse)
async def close_day(
    data: ReconciliationCreate,
    db=Depends(get_db),
    current_user=Depends(require_admin),
):
    existing = (await db.execute(select(Reconciliation).where(Reconciliation.date == data.date))).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=400, detail="Day already closed")

    rows = (await db.execute(select(CashLedger).where(CashLedger.date == data.date))).scalars().all()
    total_in = sum(r.amount for r in rows if r.direction == "IN")
    total_out = sum(r.amount for r in rows if r.direction == "OUT")
    expected = data.opening_balance + total_in - total_out
    discrepancy = data.actual_close - expected

    recon = Reconciliation(
        date=data.date,
        opening_balance=data.opening_balance,
        total_cash_in=total_in, total_cash_out=total_out,
        expected_close=expected, actual_close=data.actual_close,
        discrepancy=discrepancy, notes=data.notes,
        closed_by=current_user.id,
    )
    db.add(recon)

    if discrepancy != 0:
        await record_cash_entry(
            db, date=data.date,
            type="reconciliation_adjustment",
            direction="IN" if discrepancy > 0 else "OUT",
            amount=abs(discrepancy),
            note=f"Daily reconciliation {'overage' if discrepancy > 0 else 'shortage'}",
            created_by=current_user.id,
        )

    await db.commit()
    await db.refresh(recon)
    return recon
