-- migrations.sql — All CREATE TABLE statements for the shop app
-- Run against PostgreSQL (Railway) or SQLite (local dev)

CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    phone TEXT DEFAULT '',
    role TEXT DEFAULT 'reception',
    active INTEGER DEFAULT 1,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS customers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    phone TEXT NOT NULL,
    email TEXT DEFAULT '',
    address TEXT DEFAULT '',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS ix_customers_phone ON customers(phone);

CREATE TABLE IF NOT EXISTS parts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    sku TEXT UNIQUE,
    stock_qty INTEGER DEFAULT 0,
    unit_price REAL DEFAULT 0,
    selling_price REAL DEFAULT 0,
    currency TEXT DEFAULT 'USD',
    min_stock_alert INTEGER DEFAULT 5,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS repairs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_id INTEGER REFERENCES customers(id),
    assigned_to INTEGER REFERENCES users(id),
    created_by INTEGER NOT NULL REFERENCES users(id),
    status TEXT DEFAULT 'PENDING_ESTIMATE',
    model TEXT NOT NULL,
    issues TEXT NOT NULL,
    imei TEXT DEFAULT '',
    estimated_cost REAL DEFAULT 0,
    actual_cost REAL DEFAULT 0,
    service_fee REAL DEFAULT 0,
    payment_status TEXT DEFAULT 'UNPAID',
    notes TEXT DEFAULT '',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS repair_parts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    repair_id INTEGER NOT NULL REFERENCES repairs(id),
    part_id INTEGER NOT NULL REFERENCES parts(id),
    qty INTEGER DEFAULT 1,
    unit_price REAL DEFAULT 0,
    selling_price REAL DEFAULT 0,
    returned_qty INTEGER DEFAULT 0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS services (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    description TEXT DEFAULT '',
    default_price REAL DEFAULT 0,
    currency TEXT DEFAULT 'USD',
    active INTEGER DEFAULT 1,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS payments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    repair_id INTEGER NOT NULL REFERENCES repairs(id),
    amount REAL NOT NULL,
    currency TEXT DEFAULT 'USD',
    method TEXT DEFAULT 'cash',
    notes TEXT DEFAULT '',
    created_by INTEGER NOT NULL REFERENCES users(id),
    paid_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS expense_categories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS expenses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL,
    amount REAL NOT NULL,
    currency TEXT DEFAULT 'USD',
    category_id INTEGER NOT NULL REFERENCES expense_categories(id),
    note TEXT DEFAULT '',
    created_by INTEGER NOT NULL REFERENCES users(id),
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS ix_expenses_date ON expenses(date);

CREATE TABLE IF NOT EXISTS daily_sales (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL,
    amount REAL NOT NULL,
    currency TEXT DEFAULT 'USD',
    category TEXT DEFAULT 'general',
    note TEXT DEFAULT '',
    created_by INTEGER NOT NULL REFERENCES users(id),
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS ix_daily_sales_date ON daily_sales(date);

CREATE TABLE IF NOT EXISTS suppliers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    phone TEXT DEFAULT '',
    address TEXT DEFAULT '',
    notes TEXT DEFAULT '',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS supplier_payments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    supplier_id INTEGER NOT NULL REFERENCES suppliers(id),
    amount REAL DEFAULT 0,
    method TEXT DEFAULT 'cash',
    date TEXT DEFAULT '',
    notes TEXT DEFAULT '',
    created_by INTEGER NOT NULL REFERENCES users(id),
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS purchase_orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    po_number TEXT NOT NULL UNIQUE,
    supplier_id INTEGER NOT NULL REFERENCES suppliers(id),
    status TEXT DEFAULT 'draft',
    payment_type TEXT DEFAULT 'credit',
    notes TEXT DEFAULT '',
    created_by INTEGER NOT NULL REFERENCES users(id),
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS purchase_order_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    po_id INTEGER NOT NULL REFERENCES purchase_orders(id),
    part_id INTEGER REFERENCES parts(id),
    part_name TEXT DEFAULT '',
    qty_ordered INTEGER DEFAULT 1,
    qty_received INTEGER DEFAULT 0,
    cost_price REAL DEFAULT 0,
    selling_price REAL DEFAULT 0,
    part_status TEXT DEFAULT 'pending'
);

CREATE TABLE IF NOT EXISTS settings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    key TEXT NOT NULL UNIQUE,
    value TEXT DEFAULT '',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS cash_ledger (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL,
    type TEXT NOT NULL,
    direction TEXT NOT NULL,
    amount REAL NOT NULL,
    currency TEXT DEFAULT 'USD',
    reference_type TEXT DEFAULT '',
    reference_id INTEGER,
    reference_table TEXT DEFAULT '',
    reference_pk INTEGER,
    payment_method TEXT DEFAULT 'cash',
    note TEXT DEFAULT '',
    created_by INTEGER NOT NULL REFERENCES users(id),
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS ix_cash_ledger_date ON cash_ledger(date);
CREATE INDEX IF NOT EXISTS ix_cash_ledger_type ON cash_ledger(type);

CREATE TABLE IF NOT EXISTS inventory_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL,
    part_id INTEGER NOT NULL REFERENCES parts(id),
    change_qty INTEGER NOT NULL,
    old_qty INTEGER NOT NULL,
    new_qty INTEGER NOT NULL,
    reason TEXT NOT NULL,
    reference_type TEXT DEFAULT '',
    reference_id INTEGER,
    reference_table TEXT DEFAULT '',
    reference_pk INTEGER,
    unit_cost REAL DEFAULT 0,
    note TEXT DEFAULT '',
    created_by INTEGER NOT NULL REFERENCES users(id),
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS ix_inventory_log_date ON inventory_log(date);
CREATE INDEX IF NOT EXISTS ix_inventory_log_part_id ON inventory_log(part_id);

CREATE TABLE IF NOT EXISTS due_collections (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_id INTEGER NOT NULL REFERENCES customers(id),
    repair_id INTEGER REFERENCES repairs(id),
    amount REAL NOT NULL,
    currency TEXT DEFAULT 'USD',
    method TEXT DEFAULT 'cash',
    date TEXT NOT NULL,
    note TEXT DEFAULT '',
    created_by INTEGER NOT NULL REFERENCES users(id),
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS ix_due_collections_customer_id ON due_collections(customer_id);

CREATE TABLE IF NOT EXISTS reconciliations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL UNIQUE,
    opening_balance REAL NOT NULL DEFAULT 0,
    total_cash_in REAL NOT NULL DEFAULT 0,
    total_cash_out REAL NOT NULL DEFAULT 0,
    expected_close REAL NOT NULL DEFAULT 0,
    actual_close REAL NOT NULL DEFAULT 0,
    discrepancy REAL NOT NULL DEFAULT 0,
    notes TEXT DEFAULT '',
    closed_by INTEGER NOT NULL REFERENCES users(id),
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS ix_reconciliations_date ON reconciliations(date);
