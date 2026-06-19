from sqlalchemy import Column, Integer, String, DateTime, func
from app.database import Base


class Customer(Base):
    __tablename__ = "customers"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    phone = Column(String, nullable=False, index=True)
    email = Column(String, default="")
    address = Column(String, default="")
    created_at = Column(DateTime, server_default=func.now())
