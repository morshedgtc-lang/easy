from datetime import date as _date
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


@router.get("/today")
async def today_status(
    db=Depends(get_db),
    current_user=Depends(get_current_user),
):
    today = _date.today().isoformat()
    existing = (await db.execute(select(Reconciliation).where(Reconciliation.date == today))).scalar_one_or_none()
    if existing:
        return {"closed": True, "date": today, "reconciliation": ReconciliationResponse.model_validate(existing)}

    rows = (await db.execute(select(CashLedger).where(CashLedger.date == today))).scalars().all()
    total_in = sum(r.amount for r in rows if r.direction == "IN")
    total_out = sum(r.amount for r in rows if r.direction == "OUT")

    return {
        "closed": False,
        "date": today,
        "total_cash_in": total_in,
        "total_cash_out": total_out,
    }


@router.post("/close")
async def close_day(
    data: ReconciliationCreate,
    db=Depends(get_db),
    current_user=Depends(require_admin),
):
    today = _date.today().isoformat()
    existing = (await db.execute(select(Reconciliation).where(Reconciliation.date == today))).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=400, detail="Day already closed")

    all_cash = (await db.execute(select(CashLedger))).scalars().all()
    prev_in = sum(r.amount for r in all_cash if r.direction == "IN" and r.date < today)
    prev_out = sum(r.amount for r in all_cash if r.direction == "OUT" and r.date < today)
    opening_balance = prev_in - prev_out

    today_rows = [r for r in all_cash if r.date == today]
    total_in = sum(r.amount for r in today_rows if r.direction == "IN")
    total_out = sum(r.amount for r in today_rows if r.direction == "OUT")
    expected = opening_balance + total_in - total_out
    discrepancy = data.actual_close - expected

    recon = Reconciliation(
        date=today,
        opening_balance=opening_balance,
        total_cash_in=total_in, total_cash_out=total_out,
        expected_close=expected, actual_close=data.actual_close,
        discrepancy=discrepancy, notes=data.notes,
        closed_by=current_user.id,
    )
    db.add(recon)

    if discrepancy != 0:
        await record_cash_entry(
            db, date=today,
            type="reconciliation_adjustment",
            direction="IN" if discrepancy > 0 else "OUT",
            amount=abs(discrepancy),
            note=f"Daily reconciliation {'overage' if discrepancy > 0 else 'shortage'}",
            created_by=current_user.id,
        )

    await db.commit()
    await db.refresh(recon)
    return ReconciliationResponse.model_validate(recon)
