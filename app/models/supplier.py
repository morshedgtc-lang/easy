from sqlalchemy import Column, Integer, String, Text, DateTime, func
from app.database import Base


class Supplier(Base):
    __tablename__ = "suppliers"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    phone = Column(String, default="")
    address = Column(String, default="")
    notes = Column(Text, default="")
    created_at = Column(DateTime, server_default=func.now())
