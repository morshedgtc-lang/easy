from datetime import date as _date
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.cash_ledger import CashLedger


async def record_cash_entry(
    db: AsyncSession,
    *,
    date: str = "",
    type: str,
    direction: str,
    amount: float,
    currency: str = "USD",
    reference_type: str = "",
    reference_id: int = None,
    reference_table: str = "",
    reference_pk: int = None,
    payment_method: str = "cash",
    note: str = "",
    created_by: int = 0,
):
    entry = CashLedger(
        date=date or _date.today().isoformat(),
        type=type,
        direction=direction,
        amount=abs(amount),
        currency=currency,
        reference_type=reference_type,
        reference_id=reference_id,
        reference_table=reference_table,
        reference_pk=reference_pk,
        payment_method=payment_method,
        note=note,
        created_by=created_by,
    )
    db.add(entry)
