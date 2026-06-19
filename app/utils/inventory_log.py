from datetime import date as _date
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.inventory_log import InventoryLog


async def record_stock_change(
    db: AsyncSession,
    *,
    part_id: int,
    change_qty: int,
    old_qty: int,
    new_qty: int,
    reason: str,
    reference_type: str = "",
    reference_id: int = None,
    reference_table: str = "",
    reference_pk: int = None,
    unit_cost: float = 0,
    note: str = "",
    created_by: int = 0,
):
    entry = InventoryLog(
        date=_date.today().isoformat(),
        part_id=part_id,
        change_qty=change_qty,
        old_qty=old_qty,
        new_qty=new_qty,
        reason=reason,
        reference_type=reference_type,
        reference_id=reference_id,
        reference_table=reference_table,
        reference_pk=reference_pk,
        unit_cost=unit_cost,
        note=note,
        created_by=created_by,
    )
    db.add(entry)
