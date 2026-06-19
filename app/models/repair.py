from sqlalchemy import Column, Integer, String, Float, ForeignKey, DateTime, Text, func
from sqlalchemy.orm import relationship
from app.database import Base


class Repair(Base):
    __tablename__ = "repairs"
    id = Column(Integer, primary_key=True, index=True)
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=True)
    assigned_to = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    status = Column(String, default="PENDING_ESTIMATE")
    model = Column(String, nullable=False)
    issues = Column(Text, nullable=False)
    imei = Column(String, default="")
    estimated_cost = Column(Float, default=0)
    actual_cost = Column(Float, default=0)
    service_fee = Column(Float, default=0)
    payment_status = Column(String, default="UNPAID")
    notes = Column(Text, default="")
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    customer = relationship("Customer", backref="repairs")
    assigned_user = relationship("User", foreign_keys=[assigned_to])
    creator = relationship("User", foreign_keys=[created_by])
