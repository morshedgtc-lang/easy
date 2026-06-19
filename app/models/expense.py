from sqlalchemy import Column, Integer, String, Float, ForeignKey, DateTime, Text, func
from app.database import Base


class Expense(Base):
    __tablename__ = "expenses"

    id = Column(Integer, primary_key=True, index=True)
    date = Column(String, nullable=False, index=True)
    amount = Column(Float, nullable=False)
    currency = Column(String, default="USD")
    category_id = Column(Integer, ForeignKey("expense_categories.id"), nullable=False)
    note = Column(Text, default="")
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, server_default=func.now())
