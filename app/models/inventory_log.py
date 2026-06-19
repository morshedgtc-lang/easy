from sqlalchemy import Column, Integer, String, Float, ForeignKey, DateTime, Text, func
from sqlalchemy.orm import relationship
from app.database import Base


class InventoryLog(Base):
    __tablename__ = "inventory_log"

    id = Column(Integer, primary_key=True, index=True)
    date = Column(String, nullable=False, index=True)
    part_id = Column(Integer, ForeignKey("parts.id"), nullable=False, index=True)
    change_qty = Column(Integer, nullable=False)
    old_qty = Column(Integer, nullable=False)
    new_qty = Column(Integer, nullable=False)
    reason = Column(String, nullable=False)
    reference_type = Column(String, default="")
    reference_id = Column(Integer, nullable=True)
    reference_table = Column(String, default="")
    reference_pk = Column(Integer, nullable=True)
    unit_cost = Column(Float, default=0)
    note = Column(Text, default="")
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, server_default=func.now())

    part = relationship("Part")
    creator = relationship("User", foreign_keys=[created_by])
