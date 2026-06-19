from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class CustomerCreate(BaseModel):
    name: str
    phone: str = ""
    email: str = ""
    address: str = ""


class CustomerUpdate(BaseModel):
    name: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    address: Optional[str] = None


class CustomerResponse(BaseModel):
    id: int
    name: str
    phone: str
    email: str
    address: str
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True
