from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, func as sqlfunc
from typing import Optional
from datetime import date

from app.database import get_db
from app.models.expense import Expense
from app.models.expense_category import ExpenseCategory
from app.schemas.expense import (
    ExpenseCreate, ExpenseUpdate, ExpenseCategoryCreate,
    ExpenseCategoryResponse, ExpenseResponse,
)
from app.utils.auth import get_current_user
from app.utils.permissions import require_warehouse_or_admin, require_admin
from app.utils.cash_ledger import record_cash_entry

router = APIRouter(prefix="/api/expenses", tags=["expenses"])


@router.get("", response_model=dict)
async def list_expenses(
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    category_id: Optional[int] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    db=Depends(get_db),
    current_user=Depends(get_current_user),
):
    count_stmt = select(sqlfunc.count(Expense.id))
    list_stmt = select(Expense)
    if date_from:
        count_stmt = count_stmt.where(Expense.date >= date_from)
        list_stmt = list_stmt.where(Expense.date >= date_from)
    if date_to:
        count_stmt = count_stmt.where(Expense.date <= date_to)
        list_stmt = list_stmt.where(Expense.date <= date_to)
    if category_id:
        count_stmt = count_stmt.where(Expense.category_id == category_id)
        list_stmt = list_stmt.where(Expense.category_id == category_id)
    total = (await db.execute(count_stmt)).scalar() or 0
    expenses = (
        (await db.execute(list_stmt.order_by(Expense.date.desc()).offset((page - 1) * limit).limit(limit)))
        .scalars().all()
    )
    items = []
    for e in expenses:
        cat = await db.get(ExpenseCategory, e.category_id)
        items.append(ExpenseResponse(
            id=e.id, date=e.date, amount=e.amount, currency=e.currency,
            category_id=e.category_id, category_name=cat.name if cat else "",
            note=e.note, created_by=e.created_by, created_at=e.created_at,
        ))
    return {
        "items": items, "total": total, "page": page,
        "limit": limit, "pages": (total + limit - 1) // limit,
    }


@router.post("", response_model=ExpenseResponse, status_code=status.HTTP_201_CREATED)
async def create_expense(
    data: ExpenseCreate,
    db=Depends(get_db),
    current_user=Depends(require_warehouse_or_admin),
):
    cat = await db.get(ExpenseCategory, data.category_id)
    if not cat:
        raise HTTPException(status_code=404, detail="Expense category not found")
    expense_date = data.date or date.today().isoformat()
    expense = Expense(
        amount=data.amount, category_id=data.category_id,
        currency=data.currency, note=data.note,
        date=expense_date, created_by=current_user.id,
    )
    db.add(expense)
    await db.flush()

    await record_cash_entry(
        db, type="expense", direction="OUT",
        amount=data.amount, currency=data.currency,
        reference_type="expense", reference_pk=expense.id,
        reference_table="expenses", note=data.note or cat.name,
        created_by=current_user.id,
    )

    await db.commit()
    await db.refresh(expense)
    return ExpenseResponse(
        id=expense.id, date=expense.date, amount=expense.amount,
        currency=expense.currency, category_id=expense.category_id,
        category_name=cat.name, note=expense.note,
        created_by=expense.created_by, created_at=expense.created_at,
    )


@router.get("/categories", response_model=list[ExpenseCategoryResponse])
async def list_expense_categories(
    db=Depends(get_db),
    current_user=Depends(get_current_user),
):
    rows = (await db.execute(select(ExpenseCategory))).scalars().all()
    return rows


@router.post("/categories", response_model=ExpenseCategoryResponse, status_code=201)
async def create_expense_category(
    data: ExpenseCategoryCreate,
    db=Depends(get_db),
    current_user=Depends(require_admin),
):
    existing = (await db.execute(select(ExpenseCategory).where(ExpenseCategory.name == data.name))).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=400, detail="Category already exists")
    category = ExpenseCategory(name=data.name)
    db.add(category)
    await db.commit()
    await db.refresh(category)
    return category


@router.put("/{expense_id}", response_model=ExpenseResponse)
async def update_expense(
    expense_id: int,
    data: ExpenseUpdate,
    db=Depends(get_db),
    current_user=Depends(require_warehouse_or_admin),
):
    expense = await db.get(Expense, expense_id)
    if not expense:
        raise HTTPException(status_code=404, detail="Expense not found")
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(expense, key, value)
    await db.commit()
    await db.refresh(expense)
    cat = await db.get(ExpenseCategory, expense.category_id)
    return ExpenseResponse(
        id=expense.id, date=expense.date, amount=expense.amount,
        currency=expense.currency, category_id=expense.category_id,
        category_name=cat.name if cat else "", note=expense.note,
        created_by=expense.created_by, created_at=expense.created_at,
    )


@router.delete("/{expense_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_expense(
    expense_id: int,
    db=Depends(get_db),
    current_user=Depends(require_admin),
):
    expense = await db.get(Expense, expense_id)
    if not expense:
        raise HTTPException(status_code=404, detail="Expense not found")
    await db.delete(expense)
    await db.commit()
