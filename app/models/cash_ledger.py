from sqlalchemy import Column, Integer, String, Float, ForeignKey, DateTime, Text, func
from sqlalchemy.orm import relationship
from app.database import Base


class CashLedger(Base):
    __tablename__ = "cash_ledger"

    id = Column(Integer, primary_key=True, index=True)
    date = Column(String, nullable=False, index=True)
    type = Column(String, nullable=False, index=True)
    direction = Column(String, nullable=False)
    amount = Column(Float, nullable=False)
    currency = Column(String, default="USD")
    reference_type = Column(String, default="")
    reference_id = Column(Integer, nullable=True)
    reference_table = Column(String, default="")
    reference_pk = Column(Integer, nullable=True)
    payment_method = Column(String, default="cash")
    note = Column(Text, default="")
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, server_default=func.now())

    creator = relationship("User", foreign_keys=[created_by])
