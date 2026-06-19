from sqlalchemy import Column, Integer, String, Float, ForeignKey, DateTime, Text, func
from sqlalchemy.orm import relationship
from app.database import Base


class DueCollection(Base):
    __tablename__ = "due_collections"

    id = Column(Integer, primary_key=True, index=True)
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=False, index=True)
    repair_id = Column(Integer, ForeignKey("repairs.id"), nullable=True)
    amount = Column(Float, nullable=False)
    currency = Column(String, default="USD")
    method = Column(String, default="cash")
    date = Column(String, nullable=False)
    note = Column(Text, default="")
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, server_default=func.now())

    customer = relationship("Customer", backref="due_payments")
    repair = relationship("Repair")
    creator = relationship("User", foreign_keys=[created_by])
