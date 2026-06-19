from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
from sqlalchemy import select, update
from app.config import DATABASE_URL

_ASYNC_SCHEMES = {
    "sqlite://": "sqlite+aiosqlite://",
    "postgresql://": "postgresql+asyncpg://",
    "postgresql+psycopg2://": "postgresql+asyncpg://",
}
async_db_url = DATABASE_URL
for old, new in _ASYNC_SCHEMES.items():
    if DATABASE_URL.startswith(old):
        async_db_url = new + DATABASE_URL[len(old):]
        break

engine_kwargs = {}
if not async_db_url.startswith("sqlite"):
    engine_kwargs["pool_pre_ping"] = True
    if "sslmode" not in async_db_url:
        sep = "&" if "?" in async_db_url else "?"
        async_db_url = async_db_url + sep + "sslmode=require"

engine = create_async_engine(async_db_url, **engine_kwargs)
AsyncSessionLocal = async_sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)
Base = declarative_base()

ROLE_ADMIN = "admin"
ROLE_TECHNICIAN = "technician"
ROLE_WAREHOUSE = "warehouse"
ROLE_RECEPTION = "reception"
VALID_ROLES = {ROLE_ADMIN, ROLE_TECHNICIAN, ROLE_WAREHOUSE, ROLE_RECEPTION}


async def get_db():
    async with AsyncSessionLocal() as session:
        yield session


async def init_db():
    from app.models import user, customer, repair, service, part, repair_part
    from app.models import payment, daily_sale, expense, expense_category, setting
    from app.models import supplier, purchase_order, supplier_payment
    from app.models import cash_ledger, inventory_log, due_collection, reconciliation

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    await _seed_expense_categories()
    await _seed_admin_user()
    await _seed_settings()


async def _seed_expense_categories():
    from app.models.expense_category import ExpenseCategory
    from sqlalchemy.exc import IntegrityError
    async with AsyncSessionLocal() as db:
        try:
            r = await db.execute(select(ExpenseCategory).limit(1))
            if r.scalar():
                return
            for name in ["Rent", "Electricity / Utilities", "Internet",
                         "Staff Salary", "Transport", "Marketing",
                         "Miscellaneous"]:
                db.add(ExpenseCategory(name=name))
            await db.commit()
        except IntegrityError:
            await db.rollback()


async def _seed_admin_user():
    from app.models.user import User
    from app.utils.auth import hash_password
    from sqlalchemy.exc import IntegrityError
    async with AsyncSessionLocal() as db:
        try:
            r = await db.execute(select(User).where(User.role == ROLE_ADMIN).limit(1))
            if r.scalar():
                return
            db.add(User(
                name="Admin",
                email="admin@shop.com",
                password_hash=hash_password("admin123"),
                phone="",
                role=ROLE_ADMIN,
                active=True,
            ))
            await db.commit()
        except IntegrityError:
            await db.rollback()


async def _seed_settings():
    from app.models.setting import Setting
    from sqlalchemy.exc import IntegrityError
    async with AsyncSessionLocal() as db:
        try:
            r = await db.execute(select(Setting).limit(1))
            if r.scalar():
                return
            for key, value in {
                "shop_name": "My Repair Shop",
                "shop_address": "",
                "shop_phone": "",
                "default_currency": "USD",
                "supported_currencies": '["USD", "BDT", "INR", "NGN"]',
            }.items():
                db.add(Setting(key=key, value=value))
            await db.commit()
        except IntegrityError:
            await db.rollback()
