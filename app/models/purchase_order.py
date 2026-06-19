from sqlalchemy import Column, Integer, String, Float, ForeignKey, DateTime, Text, func
from sqlalchemy.orm import relationship
from app.database import Base


class PurchaseOrder(Base):
    __tablename__ = "purchase_orders"

    id = Column(Integer, primary_key=True, index=True)
    po_number = Column(String, unique=True, nullable=False)
    supplier_id = Column(Integer, ForeignKey("suppliers.id"), nullable=False)
    status = Column(String, default="draft")
    payment_type = Column(String, default="credit")
    notes = Column(Text, default="")
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    supplier = relationship("Supplier", backref="purchase_orders")
    creator = relationship("User", foreign_keys=[created_by])
    items = relationship("PurchaseOrderItem", backref="purchase_order", cascade="all, delete-orphan")


class PurchaseOrderItem(Base):
    __tablename__ = "purchase_order_items"

    id = Column(Integer, primary_key=True, index=True)
    po_id = Column(Integer, ForeignKey("purchase_orders.id"), nullable=False)
    part_id = Column(Integer, ForeignKey("parts.id"), nullable=True)
    part_name = Column(String, default="")
    qty_ordered = Column(Integer, default=1)
    qty_received = Column(Integer, default=0)
    cost_price = Column(Float, default=0)
    selling_price = Column(Float, default=0)
    part_status = Column(String, default="pending")

    part = relationship("Part")
