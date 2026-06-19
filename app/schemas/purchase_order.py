from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel


class POItemCreate(BaseModel):
    part_id: Optional[int] = None
    part_name: str = ""
    qty: int = 1
    cost: float = 0
    selling_price: float = 0


class PurchaseOrderCreate(BaseModel):
    supplier_id: int
    items: List[POItemCreate] = []
    payment_type: str = "credit"
    notes: str = ""


class PurchaseOrderItemResponse(BaseModel):
    id: int
    part_id: Optional[int] = None
    part_name: str = ""
    qty: int
    cost: float
    selling_price: float
    qty_received: int = 0
    status: str = "pending"


class PurchaseOrderResponse(BaseModel):
    id: int
    po_number: str
    supplier_id: int
    supplier_name: str = ""
    status: str
    payment_type: str
    notes: str
    total: float = 0
    created_by: int
    creator_name: str = ""
    created_at: Optional[datetime] = None
    items: List[PurchaseOrderItemResponse] = []


PO_STATUSES = ["draft", "sent", "partially_received", "received", "cancelled"]
PO_VALID_TRANSITIONS = {
    "draft": {"sent", "cancelled"},
    "sent": {"partially_received", "received", "cancelled"},
    "partially_received": {"received", "cancelled"},
    "received": set(),
    "cancelled": set(),
}
