import os
from datetime import date

from fastapi import FastAPI, Depends, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.exceptions import RequestValidationError
from sqlalchemy import select, func as sqlfunc
from sqlalchemy.exc import IntegrityError

from app.database import init_db, get_db
from app.utils.auth import get_current_user
from app.models.repair import Repair
from app.models.payment import Payment
from app.models.daily_sale import DailySale
from app.models.expense import Expense
from app.models.customer import Customer
from app.models.part import Part
from app.models.cash_ledger import CashLedger
from app.routes import (
    auth, customers, parts, repairs, payments, expenses,
    daily_sales, suppliers, purchase_orders, cash_ledger,
    inventory_log, due_collections, reconciliation, reports, ws,
)

app = FastAPI(
    title="Shop App",
    description="Mobile repair shop management framework",
    version="1.0.0",
    redirect_slashes=False,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(customers.router)
app.include_router(parts.router)
app.include_router(repairs.router)
app.include_router(payments.router)
app.include_router(expenses.router)
app.include_router(daily_sales.router)
app.include_router(suppliers.router)
app.include_router(purchase_orders.router)
app.include_router(cash_ledger.router)
app.include_router(inventory_log.router)
app.include_router(due_collections.router)
app.include_router(reconciliation.router)
app.include_router(reports.router)
app.include_router(ws.router)

static_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static")
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")


@app.on_event("startup")
async def startup_event():
    await init_db()


@app.exception_handler(HTTPException)
async def http_exception_handler(_request: Request, exc: HTTPException):
    return JSONResponse(status_code=exc.status_code, content={"error": exc.detail})


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(_request: Request, exc: RequestValidationError):
    errors = []
    for err in exc.errors():
        loc = ".".join(str(p) for p in err.get("loc", []))
        msg = err.get("msg", "Invalid value")
        errors.append(f"{loc}: {msg}" if loc else msg)
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"error": "Validation failed", "details": errors},
    )


@app.exception_handler(IntegrityError)
async def integrity_error_handler(_request: Request, exc: IntegrityError):
    return JSONResponse(
        status_code=status.HTTP_409_CONFLICT,
        content={"error": "Database constraint violation"},
    )


@app.exception_handler(Exception)
async def general_exception_handler(_request: Request, exc: Exception):
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"error": "Internal server error"},
    )


@app.get("/", include_in_schema=False)
async def root():
    index_path = os.path.join(static_dir, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {"message": "Shop App API is running"}


@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "Shop App API"}


@app.get("/api/dashboard")
async def dashboard(
    current_user=Depends(get_current_user),
    db=Depends(get_db),
):
    today = date.today().isoformat()

    total_repairs = (await db.execute(select(sqlfunc.count(Repair.id)))).scalar() or 0
    pending = (await db.execute(
        select(sqlfunc.count(Repair.id)).where(Repair.status.in_(["PENDING_ESTIMATE", "ESTIMATE_GIVEN"]))
    )).scalar() or 0
    in_progress = (await db.execute(
        select(sqlfunc.count(Repair.id)).where(Repair.status.in_(["APPROVED", "WAITING_PARTS", "REPAIRED"]))
    )).scalar() or 0
    completed_today = (await db.execute(
        select(sqlfunc.count(Repair.id)).where(
            Repair.status == "COMPLETED",
            Repair.updated_at >= today, Repair.updated_at < today + " 23:59:59",
        )
    )).scalar() or 0

    repair_payments = (await db.execute(
        select(Payment).where(Payment.paid_at >= today, Payment.paid_at <= today + " 23:59:59")
    )).scalars().all()
    total_revenue = sum(p.amount for p in repair_payments)

    manual_sales = (await db.execute(select(DailySale).where(DailySale.date == today))).scalars().all()
    total_revenue += sum(s.amount for s in manual_sales)

    expenses = (await db.execute(select(Expense).where(Expense.date == today))).scalars().all()
    total_expenses = sum(e.amount for e in expenses)

    cash_entries = (await db.execute(select(CashLedger).where(CashLedger.date == today))).scalars().all()
    cash_in = sum(r.amount for r in cash_entries if r.direction == "IN")
    cash_out = sum(r.amount for r in cash_entries if r.direction == "OUT")

    all_cash = (await db.execute(select(CashLedger))).scalars().all()
    total_cash_balance = sum(r.amount for r in all_cash if r.direction == "IN") - sum(r.amount for r in all_cash if r.direction == "OUT")

    low_stock = (await db.execute(
        select(Part).where(Part.stock_qty <= Part.min_stock_alert)
    )).scalars().all()

    recent_repairs = (await db.execute(
        select(Repair).order_by(Repair.created_at.desc()).limit(5)
    )).scalars().all()
    recent_list = []
    for r in recent_repairs:
        cust = (await db.execute(select(Customer).where(Customer.id == r.customer_id))).scalar_one_or_none()
        recent_list.append({
            "id": r.id, "customer_name": cust.name if cust else "Unknown",
            "model": r.model, "status": r.status,
            "created_at": str(r.created_at) if r.created_at else "",
        })

    return {
        "today_repairs": total_repairs,
        "pending": pending,
        "in_progress": in_progress,
        "completed_today": completed_today,
        "today_revenue": total_revenue,
        "today_expenses": total_expenses,
        "net_profit": total_revenue - total_expenses,
        "cash_in_today": cash_in,
        "cash_out_today": cash_out,
        "cash_balance": total_cash_balance,
        "low_stock": [{"id": p.id, "name": p.name, "stock_qty": p.stock_qty} for p in low_stock],
        "recent_repairs": recent_list,
    }
