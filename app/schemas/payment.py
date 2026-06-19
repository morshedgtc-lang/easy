from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class PaymentCreate(BaseModel):
    repair_id: int
    amount: float
    currency: str = "USD"
    method: str = "cash"
    notes: str = ""


class PaymentResponse(BaseModel):
    id: int
    repair_id: int
    amount: float
    currency: str
    method: str
    notes: str
    created_by: int
    paid_at: Optional[datetime] = None

    class Config:
        from_attributes = True
