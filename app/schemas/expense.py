from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class ExpenseCreate(BaseModel):
    amount: float
    currency: str = "USD"
    category_id: int
    date: Optional[str] = None
    note: str = ""


class ExpenseUpdate(BaseModel):
    amount: Optional[float] = None
    currency: Optional[str] = None
    category_id: Optional[int] = None
    date: Optional[str] = None
    note: Optional[str] = None


class ExpenseResponse(BaseModel):
    id: int
    date: str
    amount: float
    currency: str
    category_id: int
    category_name: str = ""
    note: str
    created_by: int
    created_at: Optional[datetime] = None


class ExpenseCategoryCreate(BaseModel):
    name: str


class ExpenseCategoryResponse(BaseModel):
    id: int
    name: str

    class Config:
        from_attributes = True
