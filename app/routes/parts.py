from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, func as sqlfunc
from typing import Optional

from app.database import get_db
from app.models.part import Part
from app.schemas.part import PartCreate, PartUpdate, PartResponse
from app.utils.auth import get_current_user
from app.utils.permissions import require_warehouse_or_admin
from app.utils.inventory_log import record_stock_change

router = APIRouter(prefix="/api/parts", tags=["parts"])


@router.get("", response_model=dict)
async def list_parts(
    search: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    db=Depends(get_db),
    current_user=Depends(get_current_user),
):
    count_stmt = select(sqlfunc.count(Part.id))
    list_stmt = select(Part)
    if search:
        term = f"%{search}%"
        count_stmt = count_stmt.where(Part.name.ilike(term) | Part.sku.ilike(term))
        list_stmt = list_stmt.where(Part.name.ilike(term) | Part.sku.ilike(term))
    total = (await db.execute(count_stmt)).scalar() or 0
    rows = (
        (await db.execute(list_stmt.order_by(Part.created_at.desc()).offset((page - 1) * limit).limit(limit)))
        .scalars().all()
    )
    return {
        "items": [PartResponse.model_validate(p) for p in rows],
        "total": total, "page": page, "limit": limit,
        "pages": (total + limit - 1) // limit,
    }


@router.post("", response_model=PartResponse, status_code=status.HTTP_201_CREATED)
async def create_part(
    data: PartCreate,
    db=Depends(get_db),
    current_user=Depends(require_warehouse_or_admin),
):
    sku = data.sku
    if not sku:
        result = await db.execute(select(sqlfunc.max(Part.id)))
        max_id = result.scalar() or 0
        sku = f"PART-{max_id + 1:04d}"
    part = Part(
        name=data.name, sku=sku,
        stock_qty=data.stock_qty, unit_price=data.unit_price,
        selling_price=data.selling_price, currency=data.currency,
        min_stock_alert=data.min_stock_alert,
    )
    db.add(part)
    await db.commit()
    await db.refresh(part)

    if data.stock_qty > 0:
        await record_stock_change(
            db, part_id=part.id, change_qty=data.stock_qty,
            old_qty=0, new_qty=data.stock_qty,
            reason="initial_stock", created_by=current_user.id,
        )
        await db.commit()

    return part


@router.get("/{part_id}", response_model=PartResponse)
async def get_part(
    part_id: int,
    db=Depends(get_db),
    current_user=Depends(get_current_user),
):
    part = await db.get(Part, part_id)
    if not part:
        raise HTTPException(status_code=404, detail="Part not found")
    return part


@router.put("/{part_id}", response_model=PartResponse)
async def update_part(
    part_id: int,
    data: PartUpdate,
    db=Depends(get_db),
    current_user=Depends(require_warehouse_or_admin),
):
    part = await db.get(Part, part_id)
    if not part:
        raise HTTPException(status_code=404, detail="Part not found")

    old_qty = part.stock_qty
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(part, key, value)
    await db.commit()
    await db.refresh(part)

    new_qty = part.stock_qty
    if new_qty != old_qty:
        await record_stock_change(
            db, part_id=part.id,
            change_qty=new_qty - old_qty,
            old_qty=old_qty, new_qty=new_qty,
            reason="adjustment",
            note="Manual stock adjustment",
            created_by=current_user.id,
        )
        await db.commit()

    return part


@router.delete("/{part_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_part(
    part_id: int,
    db=Depends(get_db),
    current_user=Depends(require_warehouse_or_admin),
):
    part = await db.get(Part, part_id)
    if not part:
        raise HTTPException(status_code=404, detail="Part not found")
    await db.delete(part)
    await db.commit()


@router.get("/low-stock", response_model=list[PartResponse])
async def low_stock_parts(
    db=Depends(get_db),
    current_user=Depends(get_current_user),
):
    rows = (
        await db.execute(
            select(Part).where(Part.stock_qty <= Part.min_stock_alert)
        )
    ).scalars().all()
    return rows
