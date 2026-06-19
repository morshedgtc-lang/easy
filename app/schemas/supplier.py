from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class SupplierCreate(BaseModel):
    name: str
    phone: str = ""
    address: str = ""
    notes: str = ""


class SupplierUpdate(BaseModel):
    name: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    notes: Optional[str] = None


class SupplierResponse(BaseModel):
    id: int
    name: str
    phone: str
    address: str
    notes: str
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class SupplierPaymentCreate(BaseModel):
    amount: float
    currency: str = "USD"
    method: str = "cash"
    date: Optional[str] = None
    notes: str = ""


class SupplierPaymentResponse(BaseModel):
    id: int
    supplier_id: int
    amount: float
    method: str
    date: str
    notes: str
    created_by: int
    created_at: Optional[datetime] = None
