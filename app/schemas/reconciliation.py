from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class ReconciliationCreate(BaseModel):
    actual_close: float
    notes: str = ""


class ReconciliationResponse(BaseModel):
    id: int
    date: str
    opening_balance: float
    total_cash_in: float
    total_cash_out: float
    expected_close: float
    actual_close: float
    discrepancy: float
    notes: str
    closed_by: int
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True
