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

CREATE INDEX IF NOT EXISTS idx_businesses_status ON businesses(status);
CREATE INDEX IF NOT EXISTS idx_businesses_slug ON businesses(slug);
CREATE INDEX IF NOT EXISTS idx_businesses_category ON businesses(category_id);
CREATE INDEX IF NOT EXISTS idx_businesses_location ON businesses(primary_location_id);
CREATE INDEX IF NOT EXISTS idx_services_business ON services(business_id);
CREATE INDEX IF NOT EXISTS idx_change_requests_status ON change_requests(status);
CREATE INDEX IF NOT EXISTS idx_audit_events_created ON audit_events(created_at);
"""

def init_db(db_path: str):
    os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.executescript(SCHEMA_SQL)
    conn.commit()
    return conn
