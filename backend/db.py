"""
Mavunqo Phase 1 - SQLite Database Schema & Migrations
"""
import sqlite3
import os

SCHEMA_SQL = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    email TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    full_name TEXT NOT NULL,
    role TEXT NOT NULL CHECK(role IN ('admin', 'owner')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS categories (
    id TEXT PRIMARY KEY,
    slug TEXT UNIQUE NOT NULL,
    name_en TEXT NOT NULL,
    name_es TEXT NOT NULL,
    icon TEXT DEFAULT 'tag',
    sort_order INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS locations (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    region TEXT DEFAULT 'Puerto Plata Province',
    status TEXT NOT NULL CHECK(status IN ('active', 'upcoming', 'inactive')),
    is_launch_market BOOLEAN DEFAULT 0,
    sort_order INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS businesses (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    trading_name TEXT NOT NULL,
    legal_name TEXT,
    slug TEXT UNIQUE NOT NULL,
    category_id TEXT NOT NULL REFERENCES categories(id),
    primary_location_id TEXT NOT NULL REFERENCES locations(id),
    description_en TEXT NOT NULL,
    description_es TEXT NOT NULL,
    status TEXT NOT NULL CHECK(status IN ('pending', 'approved', 'rejected', 'suspended')) DEFAULT 'pending',
    has_physical_location BOOLEAN DEFAULT 1,
    address TEXT,
    serves_entire_area BOOLEAN DEFAULT 0,
    website_url TEXT,
    whatsapp TEXT,
    phone TEXT,
    public_email TEXT,
    logo_url TEXT,
    cover_image_url TEXT,
    hours_json TEXT, -- JSON string for weekly hours
    rnc_tax_id TEXT, -- Optional Dominican Republic tax identifier
    rnc_status TEXT DEFAULT 'unverified',
    rejection_reason TEXT,
    approved_by TEXT REFERENCES users(id),
    approved_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS business_service_areas (
    business_id TEXT NOT NULL REFERENCES businesses(id) ON DELETE CASCADE,
    location_id TEXT NOT NULL REFERENCES locations(id) ON DELETE CASCADE,
    PRIMARY KEY (business_id, location_id)
);

CREATE TABLE IF NOT EXISTS services (
    id TEXT PRIMARY KEY,
    business_id TEXT NOT NULL REFERENCES businesses(id) ON DELETE CASCADE,
    name_en TEXT NOT NULL,
    name_es TEXT NOT NULL,
    description_en TEXT,
    description_es TEXT,
    price REAL,
    currency TEXT DEFAULT 'DOP',
    display_price BOOLEAN DEFAULT 0,
    sort_order INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS change_requests (
    id TEXT PRIMARY KEY,
    business_id TEXT NOT NULL REFERENCES businesses(id) ON DELETE CASCADE,
    requested_by TEXT NOT NULL REFERENCES users(id),
    changes_json TEXT NOT NULL,
    status TEXT NOT NULL CHECK(status IN ('pending', 'approved', 'rejected')) DEFAULT 'pending',
    reviewer_notes TEXT,
    reviewed_by TEXT REFERENCES users(id),
    reviewed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS contact_requests (
    id TEXT PRIMARY KEY,
    business_id TEXT NOT NULL REFERENCES businesses(id) ON DELETE CASCADE,
    sender_name TEXT NOT NULL,
    sender_contact TEXT NOT NULL,
    message TEXT NOT NULL,
    status TEXT NOT NULL CHECK(status IN ('new', 'read', 'archived')) DEFAULT 'new',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS audit_events (
    id TEXT PRIMARY KEY,
    actor_id TEXT REFERENCES users(id),
    action TEXT NOT NULL,
    target_type TEXT NOT NULL,
    target_id TEXT NOT NULL,
    details_json TEXT,
    ip_address TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS search_events (
    id TEXT PRIMARY KEY,
    query_text TEXT,
    category_id TEXT REFERENCES categories(id),
    location_id TEXT REFERENCES locations(id),
    results_count INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Phase 2 Restaurant Ordering Pilot Schema
CREATE TABLE IF NOT EXISTS menu_categories (
    id TEXT PRIMARY KEY,
    business_id TEXT NOT NULL REFERENCES businesses(id) ON DELETE CASCADE,
    name_en TEXT NOT NULL,
    name_es TEXT NOT NULL,
    sort_order INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS menu_items (
    id TEXT PRIMARY KEY,
    business_id TEXT NOT NULL REFERENCES businesses(id) ON DELETE CASCADE,
    category_id TEXT REFERENCES menu_categories(id) ON DELETE SET NULL,
    name_en TEXT NOT NULL,
    name_es TEXT NOT NULL,
    description_en TEXT,
    description_es TEXT,
    price REAL NOT NULL,
    currency TEXT DEFAULT 'DOP',
    image_url TEXT,
    is_available BOOLEAN DEFAULT 1,
    sort_order INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS menu_modifiers (
    id TEXT PRIMARY KEY,
    menu_item_id TEXT NOT NULL REFERENCES menu_items(id) ON DELETE CASCADE,
    group_name_en TEXT NOT NULL,
    group_name_es TEXT NOT NULL,
    name_en TEXT NOT NULL,
    name_es TEXT NOT NULL,
    price_delta REAL DEFAULT 0.0,
    currency TEXT DEFAULT 'DOP',
    is_required BOOLEAN DEFAULT 0,
    sort_order INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS orders (
    id TEXT PRIMARY KEY,
    order_number TEXT UNIQUE NOT NULL,
    business_id TEXT NOT NULL REFERENCES businesses(id) ON DELETE CASCADE,
    customer_name TEXT NOT NULL,
    customer_phone TEXT NOT NULL,
    customer_email TEXT,
    order_origin TEXT NOT NULL CHECK(order_origin IN ('mavunqo', 'merchant')) DEFAULT 'mavunqo',
    fulfillment_type TEXT NOT NULL CHECK(fulfillment_type IN ('pickup', 'delivery')) DEFAULT 'pickup',
    delivery_address TEXT,
    customer_notes TEXT,
    status TEXT NOT NULL CHECK(status IN ('pending', 'accepted', 'in_kitchen', 'ready', 'completed', 'cancelled', 'declined')) DEFAULT 'pending',
    subtotal REAL NOT NULL,
    delivery_fee REAL DEFAULT 0.0,
    total REAL NOT NULL,
    currency TEXT DEFAULT 'DOP',
    payment_method TEXT NOT NULL CHECK(payment_method IN ('cash')) DEFAULT 'cash',
    cash_received REAL,
    cash_reconciled BOOLEAN DEFAULT 0,
    estimated_ready_at TIMESTAMP,
    status_token TEXT UNIQUE NOT NULL,
    status_token_expires_at TIMESTAMP NOT NULL,
    decline_reason TEXT,
    cancellation_reason TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS order_items (
    id TEXT PRIMARY KEY,
    order_id TEXT NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
    menu_item_id TEXT REFERENCES menu_items(id) ON DELETE SET NULL,
    item_name_en TEXT NOT NULL,
    item_name_es TEXT NOT NULL,
    unit_price REAL NOT NULL,
    quantity INTEGER NOT NULL CHECK(quantity > 0),
    modifiers_json TEXT, -- array of selected modifier objects with name & price_delta
    line_total REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS fee_records (
    id TEXT PRIMARY KEY,
    order_id TEXT UNIQUE NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
    business_id TEXT NOT NULL REFERENCES businesses(id) ON DELETE CASCADE,
    order_origin TEXT NOT NULL,
    commission_rate REAL NOT NULL, -- e.g. 0.12 for 12%
    commissionable_amount REAL NOT NULL,
    fee_amount REAL NOT NULL,
    currency TEXT DEFAULT 'DOP',
    status TEXT NOT NULL CHECK(status IN ('pending', 'accrued', 'reconciled', 'reversed')) DEFAULT 'pending',
    reversal_reason TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Multi-Vertical Hospitality & Accommodations Schema (City Lights & Stays)
CREATE TABLE IF NOT EXISTS lodging_units (
    id TEXT PRIMARY KEY,
    business_id TEXT NOT NULL REFERENCES businesses(id) ON DELETE CASCADE,
    unit_number TEXT NOT NULL,
    unit_type TEXT NOT NULL CHECK(unit_type IN ('private_room', 'suite', 'dorm_bed', 'apartment')),
    name_en TEXT NOT NULL,
    name_es TEXT NOT NULL,
    description_en TEXT,
    description_es TEXT,
    capacity INTEGER NOT NULL DEFAULT 2,
    base_price_night REAL NOT NULL,
    currency TEXT DEFAULT 'USD',
    is_available BOOLEAN DEFAULT 1,
    sort_order INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS reservations (
    id TEXT PRIMARY KEY,
    reservation_code TEXT UNIQUE NOT NULL,
    business_id TEXT NOT NULL REFERENCES businesses(id) ON DELETE CASCADE,
    unit_id TEXT NOT NULL REFERENCES lodging_units(id) ON DELETE CASCADE,
    guest_name TEXT NOT NULL,
    guest_contact TEXT NOT NULL,
    guest_email TEXT,
    check_in_date TEXT NOT NULL, -- YYYY-MM-DD
    check_out_date TEXT NOT NULL, -- YYYY-MM-DD
    nights INTEGER NOT NULL,
    guest_count INTEGER NOT NULL DEFAULT 1,
    nightly_rate REAL NOT NULL,
    total_amount REAL NOT NULL,
    currency TEXT DEFAULT 'USD',
    status TEXT NOT NULL CHECK(status IN ('confirmed', 'checked_in', 'checked_out', 'cancelled', 'no_show')) DEFAULT 'confirmed',
    payment_method TEXT NOT NULL CHECK(payment_method IN ('cash_on_arrival')) DEFAULT 'cash_on_arrival',
    cash_collected REAL DEFAULT 0.0,
    staff_notes TEXT,
    status_token TEXT UNIQUE NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_businesses_status ON businesses(status);
CREATE INDEX IF NOT EXISTS idx_businesses_slug ON businesses(slug);
CREATE INDEX IF NOT EXISTS idx_businesses_category ON businesses(category_id);
CREATE INDEX IF NOT EXISTS idx_businesses_location ON businesses(primary_location_id);
CREATE INDEX IF NOT EXISTS idx_services_business ON services(business_id);
CREATE INDEX IF NOT EXISTS idx_change_requests_status ON change_requests(status);
CREATE INDEX IF NOT EXISTS idx_audit_events_created ON audit_events(created_at);
CREATE INDEX IF NOT EXISTS idx_menu_items_biz ON menu_items(business_id);
CREATE INDEX IF NOT EXISTS idx_orders_biz_status ON orders(business_id, status);
CREATE INDEX IF NOT EXISTS idx_orders_token ON orders(status_token);
CREATE INDEX IF NOT EXISTS idx_fee_records_biz ON fee_records(business_id);
CREATE INDEX IF NOT EXISTS idx_lodging_units_biz ON lodging_units(business_id);
CREATE INDEX IF NOT EXISTS idx_reservations_biz_status ON reservations(business_id, status);

-- Automatic Delivery Capacity Control & Motorcycle Dispatch Schema
CREATE TABLE IF NOT EXISTS drivers (
    id TEXT PRIMARY KEY,
    full_name TEXT NOT NULL,
    phone TEXT NOT NULL,
    vehicle_type TEXT NOT NULL DEFAULT 'motorcycle',
    status TEXT NOT NULL CHECK(status IN ('online', 'on_delivery', 'offline')) DEFAULT 'online',
    max_concurrent_orders INTEGER NOT NULL DEFAULT 2,
    location_id TEXT NOT NULL REFERENCES locations(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS delivery_dispatches (
    id TEXT PRIMARY KEY,
    order_id TEXT UNIQUE NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
    driver_id TEXT REFERENCES drivers(id) ON DELETE SET NULL,
    status TEXT NOT NULL CHECK(status IN ('queued_for_ready', 'dispatched', 'picked_up', 'delivered', 'cancelled')) DEFAULT 'queued_for_ready',
    dispatched_at TIMESTAMP,
    picked_up_at TIMESTAMP,
    delivered_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS delivery_capacity_settings (
    location_id TEXT PRIMARY KEY REFERENCES locations(id) ON DELETE CASCADE,
    is_delivery_paused BOOLEAN DEFAULT 0,
    pause_reason TEXT,
    max_orders_per_driver INTEGER NOT NULL DEFAULT 2,
    override_active BOOLEAN DEFAULT 0,
    override_reason TEXT,
    override_by TEXT REFERENCES users(id),
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_drivers_status_loc ON drivers(status, location_id);
CREATE INDEX IF NOT EXISTS idx_dispatches_status ON delivery_dispatches(status);
"""

def init_db(db_path: str):
    os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.executescript(SCHEMA_SQL)
    conn.commit()
    return conn
