from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func as sqlfunc
from typing import Optional

from app.database import get_db
from app.models.inventory_log import InventoryLog
from app.models.part import Part
from app.schemas.inventory_log import InventoryLogResponse
from app.utils.auth import get_current_user

router = APIRouter(prefix="/api/inventory-log", tags=["inventory-log"])


@router.get("", response_model=dict)
async def list_entries(
    part_id: Optional[int] = Query(None),
    reason: Optional[str] = Query(None),
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200),
    db=Depends(get_db),
    current_user=Depends(get_current_user),
):
    count_stmt = select(sqlfunc.count(InventoryLog.id))
    list_stmt = select(InventoryLog)
    if part_id:
        count_stmt = count_stmt.where(InventoryLog.part_id == part_id)
        list_stmt = list_stmt.where(InventoryLog.part_id == part_id)
    if reason:
        count_stmt = count_stmt.where(InventoryLog.reason == reason)
        list_stmt = list_stmt.where(InventoryLog.reason == reason)
    if date_from:
        count_stmt = count_stmt.where(InventoryLog.date >= date_from)
        list_stmt = list_stmt.where(InventoryLog.date >= date_from)
    if date_to:
        count_stmt = count_stmt.where(InventoryLog.date <= date_to)
        list_stmt = list_stmt.where(InventoryLog.date <= date_to)
    total = (await db.execute(count_stmt)).scalar() or 0
    rows = (
        (await db.execute(list_stmt.order_by(InventoryLog.created_at.desc()).offset((page - 1) * limit).limit(limit)))
        .scalars().all()
    )

    part_ids = list(set(r.part_id for r in rows))
    part_map = {}
    if part_ids:
        parts = (await db.execute(select(Part).where(Part.id.in_(part_ids)))).scalars().all()
        part_map = {p.id: p.name for p in parts}

    items = []
    for r in rows:
        items.append(InventoryLogResponse(
            id=r.id, date=r.date, part_id=r.part_id,
            part_name=part_map.get(r.part_id) or "",
            change_qty=r.change_qty, old_qty=r.old_qty, new_qty=r.new_qty,
            reason=r.reason, reference_type=r.reference_type,
            reference_id=r.reference_id, unit_cost=r.unit_cost,
            note=r.note, created_by=r.created_by, created_at=r.created_at,
        ))

    return {
        "items": items, "total": total, "page": page,
        "limit": limit, "pages": (total + limit - 1) // limit,
    }


@router.get("/summary")
async def summary(
    db=Depends(get_db),
    current_user=Depends(get_current_user),
):
    rows = (await db.execute(select(InventoryLog))).scalars().all()
    part_ids = list(set(r.part_id for r in rows))
    part_map = {}
    if part_ids:
        parts = (await db.execute(select(Part).where(Part.id.in_(part_ids)))).scalars().all()
        part_map = {p.id: p.name for p in parts}

    by_part = {}
    for r in rows:
        key = r.part_id
        if key not in by_part:
            by_part[key] = {"part_id": key, "part_name": part_map.get(key, ""), "total_in": 0, "total_out": 0}
        if r.change_qty > 0:
            by_part[key]["total_in"] += r.change_qty
        else:
            by_part[key]["total_out"] += abs(r.change_qty)

    return {"by_part": list(by_part.values()), "total_entries": len(rows)}
