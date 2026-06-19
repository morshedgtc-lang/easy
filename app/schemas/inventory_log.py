from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class InventoryLogResponse(BaseModel):
    id: int
    date: str
    part_id: int
    part_name: str = ""
    change_qty: int
    old_qty: int
    new_qty: int
    reason: str
    reference_type: str
    reference_id: Optional[int] = None
    unit_cost: float
    note: str
    created_by: int
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True
