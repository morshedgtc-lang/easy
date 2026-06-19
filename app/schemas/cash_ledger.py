from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class CashLedgerEntry(BaseModel):
    date: str
    type: str
    direction: str
    amount: float
    currency: str = "USD"
    reference_type: str = ""
    reference_id: Optional[int] = None
    reference_table: str = ""
    reference_pk: Optional[int] = None
    payment_method: str = "cash"
    note: str = ""


class CashLedgerResponse(BaseModel):
    id: int
    date: str
    type: str
    direction: str
    amount: float
    currency: str
    reference_type: str
    reference_id: Optional[int] = None
    reference_table: str
    reference_pk: Optional[int] = None
    payment_method: str
    note: str
    created_by: int
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True
