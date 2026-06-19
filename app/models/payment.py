from sqlalchemy import Column, Integer, String, Float, ForeignKey, DateTime, Text, func
from app.database import Base


class Payment(Base):
    __tablename__ = "payments"

    id = Column(Integer, primary_key=True, index=True)
    repair_id = Column(Integer, ForeignKey("repairs.id"), nullable=False)
    amount = Column(Float, nullable=False)
    currency = Column(String, default="USD")
    method = Column(String, default="cash")
    notes = Column(Text, default="")
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    paid_at = Column(DateTime, server_default=func.now())
