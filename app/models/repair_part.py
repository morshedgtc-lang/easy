from sqlalchemy import Column, Integer, Float, ForeignKey, DateTime, func
from sqlalchemy.orm import relationship
from app.database import Base


class RepairPart(Base):
    __tablename__ = "repair_parts"
    id = Column(Integer, primary_key=True, index=True)
    repair_id = Column(Integer, ForeignKey("repairs.id"), nullable=False)
    part_id = Column(Integer, ForeignKey("parts.id"), nullable=False)
    qty = Column(Integer, default=1)
    unit_price = Column(Float, default=0)
    selling_price = Column(Float, default=0)
    returned_qty = Column(Integer, default=0)
    created_at = Column(DateTime, server_default=func.now())
    repair = relationship("Repair", backref="parts_used")
    part = relationship("Part")
