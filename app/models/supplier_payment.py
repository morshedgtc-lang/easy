from sqlalchemy import Column, Integer, String, Float, ForeignKey, DateTime, Text, func
from sqlalchemy.orm import relationship
from app.database import Base


class SupplierPayment(Base):
    __tablename__ = "supplier_payments"

    id = Column(Integer, primary_key=True, index=True)
    supplier_id = Column(Integer, ForeignKey("suppliers.id"), nullable=False)
    amount = Column(Float, default=0)
    method = Column(String, default="cash")
    date = Column(String, default="")
    notes = Column(Text, default="")
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, server_default=func.now())

    supplier = relationship("Supplier", backref="payments")
    creator = relationship("User", foreign_keys=[created_by])
