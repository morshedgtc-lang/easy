from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class DailySaleCreate(BaseModel):
    amount: float
    currency: str = "USD"
    category: str = "general"
    date: Optional[str] = None
    note: str = ""


class DailySaleUpdate(BaseModel):
    amount: Optional[float] = None
    currency: Optional[str] = None
    category: Optional[str] = None
    date: Optional[str] = None
    note: Optional[str] = None


class DailySaleResponse(BaseModel):
    id: int
    date: str
    amount: float
    currency: str
    category: str
    note: str
    created_by: int
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True
