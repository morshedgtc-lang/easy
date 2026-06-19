from typing import Optional
from pydantic import BaseModel


class DailySummary(BaseModel):
    date: str
    total_revenue: float = 0
    total_expenses: float = 0
    net_profit: float = 0
    cash_in: float = 0
    cash_out: float = 0
    repairs_completed: int = 0
    new_customers: int = 0


class MonthlySummary(BaseModel):
    year: int
    month: int
    total_revenue: float = 0
    total_expenses: float = 0
    net_profit: float = 0
    repairs_completed: int = 0
    new_customers: int = 0
