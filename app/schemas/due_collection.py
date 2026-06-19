from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class DueCollectionCreate(BaseModel):
    customer_id: int
    repair_id: Optional[int] = None
    amount: float
    currency: str = "USD"
    method: str = "cash"
    date: Optional[str] = None
    note: str = ""


class DueCollectionResponse(BaseModel):
    id: int
    customer_id: int
    customer_name: str = ""
    repair_id: Optional[int] = None
    amount: float
    currency: str
    method: str
    date: str
    note: str
    created_by: int
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class CustomerBalance(BaseModel):
    customer_id: int
    customer_name: str
    total_owed: float
    total_paid: float
    balance: float
