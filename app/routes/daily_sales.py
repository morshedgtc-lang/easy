from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, func as sqlfunc
from typing import Optional
from datetime import date

from app.database import get_db
from app.models.daily_sale import DailySale
from app.schemas.daily_sale import DailySaleCreate, DailySaleUpdate, DailySaleResponse
from app.utils.auth import get_current_user
from app.utils.permissions import require_warehouse_or_admin, require_admin
from app.utils.cash_ledger import record_cash_entry

router = APIRouter(prefix="/api/daily-sales", tags=["daily_sales"])


@router.get("", response_model=dict)
async def list_daily_sales(
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    db=Depends(get_db),
    current_user=Depends(get_current_user),
):
    count_stmt = select(sqlfunc.count(DailySale.id))
    list_stmt = select(DailySale)
    if date_from:
        count_stmt = count_stmt.where(DailySale.date >= date_from)
        list_stmt = list_stmt.where(DailySale.date >= date_from)
    if date_to:
        count_stmt = count_stmt.where(DailySale.date <= date_to)
        list_stmt = list_stmt.where(DailySale.date <= date_to)
    total = (await db.execute(count_stmt)).scalar() or 0
    sales = (
        (await db.execute(list_stmt.order_by(DailySale.date.desc()).offset((page - 1) * limit).limit(limit)))
        .scalars().all()
    )
    return {
        "items": [DailySaleResponse.model_validate(s) for s in sales],
        "total": total, "page": page, "limit": limit,
        "pages": (total + limit - 1) // limit,
    }


@router.post("", response_model=DailySaleResponse, status_code=status.HTTP_201_CREATED)
async def create_daily_sale(
    data: DailySaleCreate,
    db=Depends(get_db),
    current_user=Depends(require_warehouse_or_admin),
):
    sale_date = data.date or date.today().isoformat()
    sale = DailySale(
        amount=data.amount, currency=data.currency,
        category=data.category, note=data.note,
        date=sale_date, created_by=current_user.id,
    )
    db.add(sale)
    await db.flush()

    await record_cash_entry(
        db, type="daily_sale", direction="IN",
        amount=data.amount, currency=data.currency,
        reference_type="daily_sale", reference_pk=sale.id,
        reference_table="daily_sales",
        note=data.note or data.category,
        created_by=current_user.id,
    )

    await db.commit()
    await db.refresh(sale)
    return sale


@router.put("/{sale_id}", response_model=DailySaleResponse)
async def update_daily_sale(
    sale_id: int,
    data: DailySaleUpdate,
    db=Depends(get_db),
    current_user=Depends(require_warehouse_or_admin),
):
    sale = await db.get(DailySale, sale_id)
    if not sale:
        raise HTTPException(status_code=404, detail="Daily sale not found")
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(sale, key, value)
    await db.commit()
    await db.refresh(sale)
    return sale


@router.delete("/{sale_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_daily_sale(
    sale_id: int,
    db=Depends(get_db),
    current_user=Depends(require_admin),
):
    sale = await db.get(DailySale, sale_id)
    if not sale:
        raise HTTPException(status_code=404, detail="Daily sale not found")
    await db.delete(sale)
    await db.commit()
