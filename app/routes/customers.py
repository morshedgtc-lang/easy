from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, func as sqlfunc
from typing import Optional

from app.database import get_db
from app.models.customer import Customer
from app.schemas.customer import CustomerCreate, CustomerUpdate, CustomerResponse
from app.utils.auth import get_current_user
from app.utils.permissions import require_reception_or_admin

router = APIRouter(prefix="/api/customers", tags=["customers"])


@router.get("", response_model=dict)
async def list_customers(
    search: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    db=Depends(get_db),
    current_user=Depends(get_current_user),
):
    count_stmt = select(sqlfunc.count(Customer.id))
    list_stmt = select(Customer)
    if search:
        term = f"%{search}%"
        count_stmt = count_stmt.where(Customer.name.ilike(term) | Customer.phone.ilike(term))
        list_stmt = list_stmt.where(Customer.name.ilike(term) | Customer.phone.ilike(term))
    total = (await db.execute(count_stmt)).scalar() or 0
    rows = (
        (await db.execute(list_stmt.order_by(Customer.created_at.desc()).offset((page - 1) * limit).limit(limit)))
        .scalars().all()
    )
    return {
        "items": [CustomerResponse.model_validate(c) for c in rows],
        "total": total, "page": page, "limit": limit,
        "pages": (total + limit - 1) // limit,
    }


@router.post("", response_model=CustomerResponse, status_code=status.HTTP_201_CREATED)
async def create_customer(
    data: CustomerCreate,
    db=Depends(get_db),
    current_user=Depends(require_reception_or_admin),
):
    customer = Customer(
        name=data.name, phone=data.phone,
        email=data.email, address=data.address,
    )
    db.add(customer)
    await db.commit()
    await db.refresh(customer)
    return customer


@router.get("/{customer_id}", response_model=CustomerResponse)
async def get_customer(
    customer_id: int,
    db=Depends(get_db),
    current_user=Depends(get_current_user),
):
    customer = await db.get(Customer, customer_id)
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    return customer


@router.put("/{customer_id}", response_model=CustomerResponse)
async def update_customer(
    customer_id: int,
    data: CustomerUpdate,
    db=Depends(get_db),
    current_user=Depends(require_reception_or_admin),
):
    customer = await db.get(Customer, customer_id)
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(customer, key, value)
    await db.commit()
    await db.refresh(customer)
    return customer


@router.delete("/{customer_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_customer(
    customer_id: int,
    db=Depends(get_db),
    current_user=Depends(require_reception_or_admin),
):
    customer = await db.get(Customer, customer_id)
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    await db.delete(customer)
    await db.commit()
