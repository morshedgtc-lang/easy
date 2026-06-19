from sqlalchemy import Column, Integer, String, Float, ForeignKey, DateTime, Text, func
from sqlalchemy.orm import relationship
from app.database import Base


class Reconciliation(Base):
    __tablename__ = "reconciliations"

    id = Column(Integer, primary_key=True, index=True)
    date = Column(String, unique=True, nullable=False, index=True)
    opening_balance = Column(Float, nullable=False, default=0)
    total_cash_in = Column(Float, nullable=False, default=0)
    total_cash_out = Column(Float, nullable=False, default=0)
    expected_close = Column(Float, nullable=False, default=0)
    actual_close = Column(Float, nullable=False, default=0)
    discrepancy = Column(Float, nullable=False, default=0)
    notes = Column(Text, default="")
    closed_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, server_default=func.now())

    closer = relationship("User", foreign_keys=[closed_by])
