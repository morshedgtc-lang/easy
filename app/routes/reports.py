from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func as sqlfunc
from typing import Optional
from datetime import date, timedelta

from app.database import get_db
from app.models.payment import Payment
from app.models.repair import Repair
from app.models.daily_sale import DailySale
from app.models.expense import Expense
from app.models.customer import Customer
from app.models.cash_ledger import CashLedger
from app.utils.auth import get_current_user

router = APIRouter(prefix="/api/reports", tags=["reports"])


@router.get("/daily")
async def daily_summary(
    date_str: Optional[str] = Query(None, alias="date"),
    db=Depends(get_db),
    current_user=Depends(get_current_user),
):
    target_date = date_str or date.today().isoformat()
    end_bound = target_date + " 23:59:59"

    payments = (await db.execute(
        select(Payment).where(Payment.paid_at >= target_date, Payment.paid_at <= end_bound)
    )).scalars().all()
    total_revenue = sum(p.amount for p in payments)

    manual = (await db.execute(select(DailySale).where(DailySale.date == target_date))).scalars().all()
    total_manual = sum(s.amount for s in manual)

    expenses = (await db.execute(select(Expense).where(Expense.date == target_date))).scalars().all()
    total_expenses = sum(e.amount for e in expenses)

    cash_entries = (await db.execute(select(CashLedger).where(CashLedger.date == target_date))).scalars().all()
    cash_in = sum(r.amount for r in cash_entries if r.direction == "IN")
    cash_out = sum(r.amount for r in cash_entries if r.direction == "OUT")

    completed = (await db.execute(
        select(sqlfunc.count(Repair.id)).where(
            Repair.status == "COMPLETED",
            Repair.updated_at >= target_date, Repair.updated_at <= end_bound,
        )
    )).scalar() or 0

    return {
        "date": target_date,
        "total_revenue": total_revenue + total_manual,
        "total_expenses": total_expenses,
        "net_profit": total_revenue + total_manual - total_expenses,
        "cash_in": cash_in, "cash_out": cash_out,
        "repairs_completed": completed,
    }


@router.get("/monthly")
async def monthly_summary(
    year: Optional[int] = Query(None),
    month: Optional[int] = Query(None),
    db=Depends(get_db),
    current_user=Depends(get_current_user),
):
    import calendar
    today = date.today()
    y = year or today.year
    m = month or today.month
    first_day = f"{y}-{m:02d}-01"
    last_day_num = calendar.monthrange(y, m)[1]
    last_day = f"{y}-{m:02d}-{last_day_num:02d}"
    end_bound = last_day + " 23:59:59"

    payments = (await db.execute(
        select(Payment).where(Payment.paid_at >= first_day, Payment.paid_at <= end_bound)
    )).scalars().all()
    total_revenue = sum(p.amount for p in payments)

    manual = (await db.execute(
        select(DailySale).where(DailySale.date >= first_day, DailySale.date <= last_day)
    )).scalars().all()
    total_revenue += sum(s.amount for s in manual)

    expenses = (await db.execute(
        select(Expense).where(Expense.date >= first_day, Expense.date <= last_day)
    )).scalars().all()
    total_expenses = sum(e.amount for e in expenses)

    completed = (await db.execute(
        select(sqlfunc.count(Repair.id)).where(
            Repair.status == "COMPLETED",
            Repair.updated_at >= first_day, Repair.updated_at <= end_bound,
        )
    )).scalar() or 0

    return {
        "year": y, "month": m,
        "total_revenue": total_revenue,
        "total_expenses": total_expenses,
        "net_profit": total_revenue - total_expenses,
        "repairs_completed": completed,
    }


@router.get("/profit-loss")
async def profit_loss(
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    db=Depends(get_db),
    current_user=Depends(get_current_user),
):
    today = date.today()
    start = date_from or (today - timedelta(days=30)).isoformat()
    end = date_to or today.isoformat()
    end_bound = end + " 23:59:59"

    payments = (await db.execute(select(Payment).where(Payment.paid_at >= start, Payment.paid_at <= end_bound))).scalars().all()
    manual = (await db.execute(select(DailySale).where(DailySale.date >= start, DailySale.date <= end))).scalars().all()
    expenses = (await db.execute(select(Expense).where(Expense.date >= start, Expense.date <= end))).scalars().all()

    revenue_by_date = {}
    for p in payments:
        day = p.paid_at.strftime("%Y-%m-%d") if p.paid_at else start
        revenue_by_date[day] = revenue_by_date.get(day, 0) + p.amount
    for s in manual:
        revenue_by_date[s.date] = revenue_by_date.get(s.date, 0) + s.amount

    expense_by_date = {}
    for e in expenses:
        expense_by_date[e.date] = expense_by_date.get(e.date, 0) + e.amount

    all_dates = sorted(set(list(revenue_by_date.keys()) + list(expense_by_date.keys())))
    items = []
    for d in all_dates:
        rev = revenue_by_date.get(d, 0)
        exp = expense_by_date.get(d, 0)
        items.append({"date": d, "revenue": rev, "expenses": exp, "net": rev - exp})

    return {
        "start_date": start, "end_date": end,
        "total_revenue": sum(i["revenue"] for i in items),
        "total_expenses": sum(i["expenses"] for i in items),
        "net_profit": sum(i["net"] for i in items),
        "items": items,
    }
