from sqlalchemy import select, func as sqlfunc
from app.models.customer import Customer
from app.models.repair import Repair
from app.models.repair_part import RepairPart
from app.models.payment import Payment
from app.models.due_collection import DueCollection


async def get_customer_due_balance(customer_id: int, db) -> float:
    customer = await db.get(Customer, customer_id)
    if not customer:
        return 0

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

    return max(total_owed - total_paid, 0)
