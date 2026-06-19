import os

from fastapi import FastAPI, Depends, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.exceptions import RequestValidationError
from sqlalchemy import select, func as sqlfunc
from sqlalchemy.exc import IntegrityError

from app.database import init_db, get_db
from app.utils.auth import get_current_user
from app.models.cash_ledger import CashLedger
from app.models.inventory_log import InventoryLog
from app.models.part import Part
from app.models.customer import Customer
from app.models.repair import Repair
from app.models.repair_part import RepairPart
from app.models.payment import Payment
from app.models.supplier import Supplier
from app.models.supplier_payment import SupplierPayment
from app.models.purchase_order import PurchaseOrder, PurchaseOrderItem
from app.models.due_collection import DueCollection
from app.routes import (
    auth, customers, parts, suppliers,
    cash_ledger, inventory_log, due_collections, reconciliation, ws,
)

app = FastAPI(
    title="Shop App",
    description="Cash ledger, inventory, dues, reconciliation & supplier payables",
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
app.include_router(suppliers.router)
app.include_router(cash_ledger.router)
app.include_router(inventory_log.router)
app.include_router(due_collections.router)
app.include_router(reconciliation.router)
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
    today = __import__("datetime").date.today().isoformat()

    all_cash = (await db.execute(select(CashLedger))).scalars().all()
    total_cash_in = sum(r.amount for r in all_cash if r.direction == "IN")
    total_cash_out = sum(r.amount for r in all_cash if r.direction == "OUT")
    cash_balance = total_cash_in - total_cash_out

    today_cash = [r for r in all_cash if r.date == today]
    cash_in_today = sum(r.amount for r in today_cash if r.direction == "IN")
    cash_out_today = sum(r.amount for r in today_cash if r.direction == "OUT")

    total_parts = (await db.execute(select(sqlfunc.count(Part.id)))).scalar() or 0
    low_stock = (await db.execute(
        select(Part).where(Part.stock_qty <= Part.min_stock_alert)
    )).scalars().all()
    inventory_entries = (await db.execute(select(sqlfunc.count(InventoryLog.id)))).scalar() or 0

    total_customers = (await db.execute(select(sqlfunc.count(Customer.id)))).scalar() or 0
    customers_with_dues = 0
    customer_ids = list(set(
        r[0] for r in (await db.execute(select(DueCollection.customer_id))).all()
    ))
    for cid in customer_ids:
        from app.utils.due_balance import get_customer_due_balance
        bal = await get_customer_due_balance(cid, db)
        if bal > 0:
            customers_with_dues += 1

    total_suppliers = (await db.execute(select(sqlfunc.count(Supplier.id)))).scalar() or 0
    supplier_payables = 0
    suppliers_list = (await db.execute(select(Supplier))).scalars().all()
    for s in suppliers_list:
        pos = (await db.execute(
            select(PurchaseOrder).where(
                PurchaseOrder.supplier_id == s.id,
                PurchaseOrder.payment_type == "credit",
                PurchaseOrder.status.in_(["sent", "partially_received", "received"]),
            )
        )).scalars().all()
        for po in pos:
            items = (await db.execute(
                select(PurchaseOrderItem).where(PurchaseOrderItem.po_id == po.id)
            )).scalars().all()
            for item in items:
                supplier_payables += item.cost_price * item.qty_received
        payments = (await db.execute(
            select(sqlfunc.coalesce(sqlfunc.sum(SupplierPayment.amount), 0)).where(
                SupplierPayment.supplier_id == s.id
            )
        )).scalar() or 0
        supplier_payables -= float(payments)

    return {
        "cash_in_today": cash_in_today,
        "cash_out_today": cash_out_today,
        "cash_balance": cash_balance,
        "total_parts": total_parts,
        "low_stock": [{"id": p.id, "name": p.name, "stock_qty": p.stock_qty} for p in low_stock],
        "inventory_entries": inventory_entries,
        "total_customers": total_customers,
        "customers_with_dues": customers_with_dues,
        "total_suppliers": total_suppliers,
        "supplier_payables": max(supplier_payables, 0),
    }
