from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, func
from sqlalchemy.orm import relationship
from app.database import Base


class Part(Base):
    __tablename__ = "parts"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    sku = Column(String, unique=True, nullable=True)
    stock_qty = Column(Integer, default=0)
    unit_price = Column(Float, default=0)
    selling_price = Column(Float, default=0)
    currency = Column(String, default="USD")
    min_stock_alert = Column(Integer, default=5)
    created_at = Column(DateTime, server_default=func.now())
