# AGENTS.md — Shop App (Mobile Repair Shop Framework)

## Quick Start

```bash
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
# Open http://localhost:8000
# Login: admin@shop.com / admin123
```

## Stack

- **Backend:** FastAPI + SQLAlchemy (async) + PostgreSQL (Railway) or SQLite (local dev)
- **Auth:** JWT via python-jose + bcrypt (NOT passlib — see gotchas)
- **Frontend:** Single-page vanilla HTML/CSS/JS in `static/`
- **Deploy:** Railway (Procfile runs uvicorn)
- **Testing:** Pytest + pytest-asyncio

## Architecture

This system connects every module to a central **Cash Ledger** and unified **Inventory Log**. Every action in the shop either moves an inventory count, adds money to the ledger, or subtracts money from it.

```
app/
  main.py              — FastAPI app, CORS, startup (init_db), /api/dashboard, /health
  config.py            — env vars via python-dotenv
  database.py          — engine, SessionLocal, Base, init_db() seeds admin + categories + settings
  models/              — SQLAlchemy models
  schemas/             — Pydantic request/response models
  routes/              — FastAPI routers, all prefixed /api/<resource>
  utils/
    auth.py            — JWT helpers, password hashing, role dependencies
    permissions.py     — Role-based access control
    cash_ledger.py     — record_cash_entry() helper
    inventory_log.py   — record_stock_change() helper
    ws_manager.py      — WebSocket connection manager
static/
  index.html           — SPA shell
  js/app.js            — Core app logic, state, routing, WebSocket
  js/pages.js          — Page renderers and CRUD functions
  css/style.css        — Dark theme styles
```

## Gotchas — Read Before Changing Code

### bcrypt (NOT passlib)
`passlib` is incompatible with bcrypt>=4.x on Python 3.13+. Use `bcrypt` directly:
```python
import bcrypt
hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
ok = bcrypt.checkpw(plain.encode(), hashed.encode())
```

### JWT `sub` must be a string
`python-jose` raises `Subject must be a string` if `sub` is an integer:
```python
create_access_token(data={"sub": str(user.id), "role": user.role})
# Decode: user_id = int(payload["sub"])
```

### Route trailing slashes
`redirect_slashes=False` is set on the FastAPI app. All routes use `@router.get("")` (not `@router.get("/")`). If you add new root routes, use `""` to match the frontend calls.

### DATABASE_URL on Railway
Railway auto-injects `DATABASE_URL` from its PostgreSQL plugin. Do NOT put a placeholder DATABASE_URL in `.env.example`. The `database.py` auto-appends `?sslmode=require` for PostgreSQL.

### Frontend API calls
The SPA uses relative URLs (`/api/customers`, not `http://...`). All API calls go through the `api()` helper in `app.js` which handles JWT headers and 401 redirects.

## How Modules Connect

```
Every cash movement ──────► cash_ledger (IN or OUT)
Every stock change ───────► inventory_log (why, when, by whom)

payments ─────────────────► cash_ledger (type="payment", direction="IN")
expenses ─────────────────► cash_ledger (type="expense", direction="OUT")
daily_sales ──────────────► cash_ledger (type="daily_sale", direction="IN")
supplier_payments ────────► cash_ledger (type="supplier_payment", direction="OUT")
purchase_receipts ────────► cash_ledger (type="purchase", direction="OUT") + inventory_log
repair parts added ───────► inventory_log (reason="repair_use")
repair parts returned ────► inventory_log (reason="part_return")

due_collections ──────────► cash_ledger (type="due_collection", direction="IN")
reconciliation ───────────► cash_ledger (type="reconciliation_adjustment")
```

## Cash Ledger Entry Pattern

Every route that moves money calls this AFTER creating its business record:

```python
from app.utils.cash_ledger import record_cash_entry

await record_cash_entry(
    db,
    date="2026-06-20",
    type="payment",           # payment, expense, daily_sale, supplier_payment, etc.
    direction="IN",           # IN or OUT
    amount=150.00,
    currency="USD",
    reference_type="repair",  # repair, supplier, customer
    reference_id=5,           # repair_id, supplier_id, etc.
    reference_table="payments",
    reference_pk=payment.id,
    payment_method="cash",
    note="Screen replacement payment",
    created_by=current_user.id,
)
# Do NOT commit here — let the calling route commit
```

## Inventory Log Entry Pattern

Every route that changes `part.stock_qty` calls this:

```python
from app.utils.inventory_log import record_stock_change

old_qty = part.stock_qty
part.stock_qty -= qty  # or += qty
await record_stock_change(
    db,
    part_id=part.id,
    change_qty=-qty,          # negative = out, positive = in
    old_qty=old_qty,
    new_qty=part.stock_qty,
    reason="repair_use",      # purchase_receipt, repair_use, part_return, adjustment, bulk_import
    reference_type="repair",
    reference_id=repair.id,
    reference_table="repair_parts",
    reference_pk=repair_part.id,
    unit_cost=part.unit_price,
    created_by=current_user.id,
)
```

## Roles & Permissions

| Role | Can Do |
|------|--------|
| admin | Everything |
| reception | Create repairs, record payments, manage customers |
| technician | Request parts, update repair status |
| warehouse | Manage inventory, fulfill part requests, receive shipments |

## Running Locally

```bash
# Local dev uses SQLite automatically (no DATABASE_URL = shop.db)
python -m uvicorn app.main:app --reload --port 8000
```

## Deployment

Railway auto-deploys from `main` branch. Add PostgreSQL database via Railway dashboard (New -> Database -> PostgreSQL). Set `JWT_SECRET` env var.
