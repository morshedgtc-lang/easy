from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, func as sqlfunc
from typing import Optional
from datetime import date

from app.database import get_db
from app.models.due_collection import DueCollection
from app.models.customer import Customer
from app.models.repair import Repair
from app.models.repair_part import RepairPart
from app.models.payment import Payment
from app.schemas.due_collection import DueCollectionCreate, DueCollectionResponse, CustomerBalance
from app.utils.auth import get_current_user
from app.utils.permissions import require_reception_or_admin
from app.utils.cash_ledger import record_cash_entry

router = APIRouter(prefix="/api/due-collections", tags=["due-collections"])


async def get_customer_balance(customer_id: int, db) -> CustomerBalance:
    customer = await db.get(Customer, customer_id)
    if not customer:
        return CustomerBalance(customer_id=customer_id, customer_name="Unknown", total_owed=0, total_paid=0, balance=0)

    repairs = (await db.execute(
        select(Repair).where(Repair.customer_id == customer_id)
    )).scalars().all()

    total_owed = 0
    for r in repairs:
        rps = (await db.execute(select(RepairPart).where(RepairPart.repair_id == r.id))).scalars().all()
        parts_cost = sum(rp.qty * rp.selling_price for rp in rps)
        total_owed += parts_cost + (r.service_fee or 0)

    repair_ids = [r.id for r in repairs]
    total_paid = 0
    if repair_ids:
        pay_result = await db.execute(
            select(sqlfunc.coalesce(sqlfunc.sum(Payment.amount), 0)).where(Payment.repair_id.in_(repair_ids))
        )
        total_paid += float(pay_result.scalar() or 0)

    due_result = await db.execute(
        select(sqlfunc.coalesce(sqlfunc.sum(DueCollection.amount), 0)).where(DueCollection.customer_id == customer_id)
    )
    total_paid += float(due_result.scalar() or 0)

    return CustomerBalance(
        customer_id=customer_id, customer_name=customer.name,
        total_owed=total_owed, total_paid=total_paid,
        balance=total_owed - total_paid,
    )


@router.get("", response_model=dict)
async def list_due_collections(
    customer_id: Optional[int] = Query(None),
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    db=Depends(get_db),
    current_user=Depends(get_current_user),
):
    count_stmt = select(sqlfunc.count(DueCollection.id))
    list_stmt = select(DueCollection)
    if customer_id:
        count_stmt = count_stmt.where(DueCollection.customer_id == customer_id)
        list_stmt = list_stmt.where(DueCollection.customer_id == customer_id)
    if date_from:
        count_stmt = count_stmt.where(DueCollection.date >= date_from)
        list_stmt = list_stmt.where(DueCollection.date >= date_from)
    if date_to:
        count_stmt = count_stmt.where(DueCollection.date <= date_to)
        list_stmt = list_stmt.where(DueCollection.date <= date_to)
    total = (await db.execute(count_stmt)).scalar() or 0
    rows = (
        (await db.execute(list_stmt.order_by(DueCollection.created_at.desc()).offset((page - 1) * limit).limit(limit)))
        .scalars().all()
    )

    customer_ids = list(set(r.customer_id for r in rows))
    customer_map = {}
    if customer_ids:
        custs = (await db.execute(select(Customer).where(Customer.id.in_(customer_ids)))).scalars().all()
        customer_map = {c.id: c.name for c in custs}

    items = [
        DueCollectionResponse(
            id=r.id, customer_id=r.customer_id,
            customer_name=customer_map.get(r.customer_id, ""),
            repair_id=r.repair_id, amount=r.amount, currency=r.currency,
            method=r.method, date=r.date, note=r.note,
            created_by=r.created_by, created_at=r.created_at,
        )
        for r in rows
    ]
    return {
        "items": items, "total": total, "page": page,
        "limit": limit, "pages": (total + limit - 1) // limit,
    }


@router.post("", response_model=DueCollectionResponse, status_code=201)
async def create_due_collection(
    data: DueCollectionCreate,
    db=Depends(get_db),
    current_user=Depends(require_reception_or_admin),
):
    customer = await db.get(Customer, data.customer_id)
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    pay_date = data.date or date.today().isoformat()
    due = DueCollection(
        customer_id=data.customer_id, repair_id=data.repair_id,
        amount=data.amount, currency=data.currency,
        method=data.method, date=pay_date,
        note=data.note, created_by=current_user.id,
    )
    db.add(due)
    await db.flush()

    await record_cash_entry(
        db, type="due_collection", direction="IN",
        amount=data.amount, currency=data.currency,
        reference_type="customer", reference_id=data.customer_id,
        reference_table="due_collections", reference_pk=due.id,
        payment_method=data.method,
        note=data.note or f"Due collection from {customer.name}",
        created_by=current_user.id,
    )

    await db.commit()
    await db.refresh(due)
    return DueCollectionResponse(
        id=due.id, customer_id=due.customer_id,
        customer_name=customer.name,
        repair_id=due.repair_id, amount=due.amount, currency=due.currency,
        method=due.method, date=due.date, note=due.note,
        created_by=due.created_by, created_at=due.created_at,
    )


@router.get("/balances", response_model=list[CustomerBalance])
async def list_balances(
    db=Depends(get_db),
    current_user=Depends(get_current_user),
):
    customers = (await db.execute(select(Customer))).scalars().all()
    balances = []
    for c in customers:
        b = await get_customer_balance(c.id, db)
        if b.total_owed > 0:
            balances.append(b)
    balances.sort(key=lambda x: x.balance, reverse=True)
    return balances


@router.get("/balance/{customer_id}", response_model=CustomerBalance)
async def get_balance(
    customer_id: int,
    db=Depends(get_db),
    current_user=Depends(get_current_user),
):
    return await get_customer_balance(customer_id, db)


@router.delete("/{due_id}", status_code=204)
async def delete_due_collection(
    due_id: int,
    db=Depends(get_db),
    current_user=Depends(require_reception_or_admin),
):
    due = await db.get(DueCollection, due_id)
    if not due:
        raise HTTPException(status_code=404, detail="Due collection not found")
    await db.delete(due)
    await db.commit()
