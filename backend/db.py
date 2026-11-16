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
    role TEXT NOT NULL CHECK(role IN ('admin', 'owner', 'manager', 'staff', 'support', 'finance', 'compliance')),
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

CREATE TABLE IF NOT EXISTS platform_settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS promo_preferences (
    phone TEXT PRIMARY KEY,
    customer_name TEXT,
    promo_opt_in BOOLEAN DEFAULT 1,
    promo_longterm_opt_in BOOLEAN DEFAULT 0,
    last_location_id TEXT REFERENCES locations(id),
    in_service_area BOOLEAN DEFAULT 1,
    booked_for_at TIMESTAMP,
    last_source_type TEXT DEFAULT 'order',
    last_order_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
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
    power_backup_type TEXT DEFAULT 'none' CHECK(power_backup_type IN ('generator', 'inverter', 'none')),
    rnc_tax_id TEXT, -- Optional Dominican Republic tax identifier
    rnc_status TEXT DEFAULT 'unverified',
    rejection_reason TEXT,
    payment_modes TEXT DEFAULT 'cash_and_digital',
    cash_only BOOLEAN DEFAULT 0,
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
    delivery_pin_lat REAL,
    delivery_pin_lng REAL,
    customer_notes TEXT,
    status TEXT NOT NULL CHECK(status IN ('pending', 'accepted', 'in_kitchen', 'ready', 'completed', 'cancelled', 'declined')) DEFAULT 'pending',
    subtotal REAL NOT NULL,
    delivery_fee REAL DEFAULT 0.0,
    driver_tip REAL DEFAULT 0.0,
    total REAL NOT NULL,
    currency TEXT DEFAULT 'DOP',
    payment_method TEXT NOT NULL CHECK(payment_method IN ('cash', 'card', 'transfer', 'zelle', 'wise', 'cash_or_card')) DEFAULT 'cash',
    payment_proof_url TEXT,
    payment_proof_hash TEXT,
    payment_verified BOOLEAN DEFAULT 0,
    payment_verified_source TEXT,
    promo_opt_in BOOLEAN DEFAULT 1,
    promo_longterm_opt_in BOOLEAN DEFAULT 0,
    cash_due REAL,
    cash_received REAL,
    cash_reconciled BOOLEAN DEFAULT 0,
    cash_exception_reason TEXT,
    customer_alias TEXT,
    phone_hash TEXT,
    attribution_source TEXT DEFAULT 'mavunqo',
    is_manual_fallback BOOLEAN DEFAULT 0,
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
    pin_code TEXT DEFAULT '1234',
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
    rain_mode_active BOOLEAN DEFAULT 0,
    pause_reason TEXT,
    max_orders_per_driver INTEGER NOT NULL DEFAULT 2,
    override_active BOOLEAN DEFAULT 0,
    override_reason TEXT,
    override_by TEXT REFERENCES users(id),
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_drivers_status_loc ON drivers(status, location_id);
CREATE INDEX IF NOT EXISTS idx_dispatches_status ON delivery_dispatches(status);

-- Masked Order In-App Relay Chat Schema
CREATE TABLE IF NOT EXISTS order_messages (
    id TEXT PRIMARY KEY,
    order_id TEXT NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
    sender_role TEXT NOT NULL CHECK(sender_role IN ('customer', 'driver', 'restaurant')),
    sender_name TEXT NOT NULL,
    message TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_order_messages_order ON order_messages(order_id, created_at);

-- -------------------------------------------------------------
-- WhatsApp Gateway, Consent, Attribution, Tokens & Audit Schema
-- -------------------------------------------------------------

CREATE TABLE IF NOT EXISTS whatsapp_webhook_events (
    id TEXT PRIMARY KEY,
    event_id TEXT UNIQUE NOT NULL,
    message_id TEXT,
    phone_hash TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'processed',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS customer_consents (
    phone_hash TEXT PRIMARY KEY,
    transactional_consent BOOLEAN DEFAULT 1,
    transactional_consent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    marketing_consent BOOLEAN DEFAULT 0,
    marketing_consent_at TIMESTAMP,
    opted_out BOOLEAN DEFAULT 0,
    opted_out_at TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS order_attributions (
    order_id TEXT PRIMARY KEY REFERENCES orders(id) ON DELETE CASCADE,
    business_id TEXT NOT NULL REFERENCES businesses(id) ON DELETE CASCADE,
    source TEXT NOT NULL CHECK(source IN ('mavunqo', 'merchant')),
    campaign TEXT,
    merchant_tag TEXT,
    signature TEXT NOT NULL,
    rule_version TEXT NOT NULL DEFAULT 'v1_2026',
    commission_rate REAL NOT NULL,
    fee_amount REAL NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS secure_order_tokens (
    token_hash TEXT PRIMARY KEY,
    order_id TEXT NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
    purpose TEXT NOT NULL CHECK(purpose IN ('checkout_confirmation', 'live_tracking', 'payment_review')),
    expires_at TIMESTAMP NOT NULL,
    used_at TIMESTAMP,
    revoked_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS exceptional_access_logs (
    id TEXT PRIMARY KEY,
    requester_id TEXT NOT NULL REFERENCES users(id),
    order_id TEXT NOT NULL REFERENCES orders(id),
    reason TEXT NOT NULL,
    authorized_by TEXT REFERENCES users(id),
    accessed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS manual_fallback_logs (
    id TEXT PRIMARY KEY,
    order_id TEXT NOT NULL REFERENCES orders(id),
    staff_id TEXT NOT NULL REFERENCES users(id),
    reason TEXT NOT NULL,
    customer_warned BOOLEAN NOT NULL DEFAULT 1,
    warning_text TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS order_substitutions (
    id TEXT PRIMARY KEY,
    order_id TEXT NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
    original_item_id TEXT,
    substitute_item_name TEXT NOT NULL,
    price_difference REAL DEFAULT 0.0,
    reason TEXT NOT NULL,
    status TEXT NOT NULL CHECK(status IN ('proposed', 'accepted', 'rejected')) DEFAULT 'proposed',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_webhook_events_msg ON whatsapp_webhook_events(message_id);
CREATE INDEX IF NOT EXISTS idx_tokens_order ON secure_order_tokens(order_id, purpose);
CREATE INDEX IF NOT EXISTS idx_attributions_biz ON order_attributions(business_id, source);

-- -------------------------------------------------------------
-- Phase 2 Merchant Request Automation, Pins & Delivery Schema
-- -------------------------------------------------------------

CREATE TABLE IF NOT EXISTS merchant_requests (
    id TEXT PRIMARY KEY,
    request_number TEXT UNIQUE NOT NULL,
    business_id TEXT NOT NULL REFERENCES businesses(id) ON DELETE CASCADE,
    category_id TEXT,
    action_type TEXT NOT NULL DEFAULT 'request_appointment', -- request_appointment, request_order, request_estimate, request_room, request_ride, request_quote
    customer_name TEXT NOT NULL,
    customer_phone TEXT NOT NULL,
    customer_phone_hash TEXT,
    customer_email TEXT,
    request_text TEXT NOT NULL,
    category_details_json TEXT, -- JSON attributes: service_options, pickup_time, appointment_date, etc.
    service_mode TEXT DEFAULT 'in_shop', -- in_shop, mobile_visit, pickup, delivery, meeting_point
    pickup_lat REAL,
    pickup_lng REAL,
    pickup_entrance_note TEXT,
    destination_lat REAL,
    destination_lng REAL,
    destination_entrance_note TEXT,
    status TEXT NOT NULL CHECK(status IN ('awaiting_confirmation', 'offer_pending', 'confirmed', 'declined', 'expired', 'cancelled')) DEFAULT 'awaiting_confirmation',
    status_token TEXT UNIQUE NOT NULL,
    status_token_expires_at TIMESTAMP NOT NULL,
    merchant_token TEXT UNIQUE NOT NULL,
    merchant_token_expires_at TIMESTAMP NOT NULL,
    requested_time TIMESTAMP,
    deadline_utc TIMESTAMP NOT NULL,
    agreed_price REAL,
    agreed_currency TEXT DEFAULT 'DOP',
    language TEXT NOT NULL DEFAULT 'en',
    origin TEXT NOT NULL CHECK(origin IN ('marketplace', 'merchant_link')) DEFAULT 'marketplace',
    confirmed_order_id TEXT REFERENCES orders(id),
    decline_reason TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS request_offers (
    id TEXT PRIMARY KEY,
    request_id TEXT NOT NULL REFERENCES merchant_requests(id) ON DELETE CASCADE,
    offered_price REAL NOT NULL,
    offered_currency TEXT DEFAULT 'DOP',
    offered_time TIMESTAMP NOT NULL,
    deadline_utc TIMESTAMP NOT NULL,
    notes TEXT,
    status TEXT NOT NULL CHECK(status IN ('pending', 'accepted', 'rejected', 'expired')) DEFAULT 'pending',
    created_by TEXT REFERENCES users(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS merchant_interest (
    id TEXT PRIMARY KEY,
    business_id TEXT NOT NULL REFERENCES businesses(id) ON DELETE CASCADE,
    customer_name TEXT,
    customer_contact TEXT NOT NULL,
    interest_note TEXT,
    source_url TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS customer_saved_pins (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    label TEXT NOT NULL, -- Home, Condo, Villa, etc.
    lat REAL NOT NULL,
    lng REAL NOT NULL,
    entrance_note TEXT,
    is_default BOOLEAN DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS cash_collections (
    id TEXT PRIMARY KEY,
    order_id TEXT UNIQUE NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
    driver_id TEXT NOT NULL REFERENCES drivers(id),
    amount_expected REAL NOT NULL,
    amount_collected REAL NOT NULL,
    currency TEXT DEFAULT 'DOP',
    collected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    notes TEXT
);

CREATE TABLE IF NOT EXISTS cash_handoffs (
    id TEXT PRIMARY KEY,
    handoff_batch_id TEXT NOT NULL,
    driver_id TEXT NOT NULL REFERENCES drivers(id),
    receiver_id TEXT NOT NULL REFERENCES users(id),
    order_ids_json TEXT NOT NULL,
    total_driver_reported REAL NOT NULL,
    total_receiver_counted REAL NOT NULL,
    difference REAL NOT NULL, -- reported - counted (shortage if negative / counted < reported)
    status TEXT NOT NULL CHECK(status IN ('reconciled', 'unresolved_discrepancy')) DEFAULT 'reconciled',
    resolution_notes TEXT,
    resolved_by TEXT REFERENCES users(id),
    resolved_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS merchant_payouts (
    id TEXT PRIMARY KEY,
    payout_batch_id TEXT UNIQUE NOT NULL,
    business_id TEXT NOT NULL REFERENCES businesses(id),
    order_ids_json TEXT NOT NULL,
    gross_subtotal REAL NOT NULL,
    commission_retained REAL NOT NULL,
    net_payout_amount REAL NOT NULL,
    currency TEXT DEFAULT 'DOP',
    status TEXT NOT NULL CHECK(status IN ('pending', 'settled', 'cancelled')) DEFAULT 'pending',
    settled_by TEXT REFERENCES users(id),
    settled_at TIMESTAMP,
    payout_method TEXT DEFAULT 'cash_envelope',
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_merchant_payouts_biz ON merchant_payouts(business_id, status);

CREATE INDEX IF NOT EXISTS idx_merchant_requests_biz ON merchant_requests(business_id, status);
CREATE INDEX IF NOT EXISTS idx_merchant_requests_token ON merchant_requests(status_token);
CREATE INDEX IF NOT EXISTS idx_merchant_requests_mtoken ON merchant_requests(merchant_token);
CREATE INDEX IF NOT EXISTS idx_merchant_interest_biz ON merchant_interest(business_id);
CREATE INDEX IF NOT EXISTS idx_customer_saved_pins_usr ON customer_saved_pins(user_id);


"""


def run_migrations(conn):
    cur = conn.cursor()
    # Check businesses columns
    cur.execute("PRAGMA table_info(businesses)")
    existing_cols = {row[1] for row in cur.fetchall()}

    new_business_cols = [
        ("requests_enabled", "BOOLEAN DEFAULT 0"),
        ("request_action_label_en", "TEXT DEFAULT 'Request an appointment'"),
        ("request_action_label_es", "TEXT DEFAULT 'Solicitar una cita'"),
        ("whatsapp_alerts_consent", "BOOLEAN DEFAULT 0"),
        ("whatsapp_alerts_phone", "TEXT"),
        ('service_modes_supported', "TEXT DEFAULT '[\"in_shop\"]'"),
        ("storefront_pin_lat", "REAL"),
        ("storefront_pin_lng", "REAL"),
        ("pickup_pin_lat", "REAL"),
        ("pickup_pin_lng", "REAL"),
        ("pickup_pin_note", "TEXT"),
        ("pilot_delivery_enabled", "BOOLEAN DEFAULT 0"),
        ("power_backup_type", "TEXT DEFAULT 'none'"),
        ("custom_commission_rate", "REAL")
    ]
    for col_name, col_def in new_business_cols:
        if col_name not in existing_cols:
            try:
                cur.execute(f"ALTER TABLE businesses ADD COLUMN {col_name} {col_def}")
            except Exception as e:
                pass

    # Check orders columns
    cur.execute("PRAGMA table_info(orders)")
    order_cols = {row[1] for row in cur.fetchall()}
    for col_name, col_def in [
        ("delivery_pin_lat", "REAL"),
        ("delivery_pin_lng", "REAL"),
        ("driver_tip", "REAL DEFAULT 0.0"),
        ("payment_proof_url", "TEXT"),
        ("payment_proof_hash", "TEXT"),
        ("payment_verified", "BOOLEAN DEFAULT 0"),
        ("payment_verified_source", "TEXT"),
        ("promo_opt_in", "BOOLEAN DEFAULT 1"),
        ("promo_longterm_opt_in", "BOOLEAN DEFAULT 0")
    ]:
        if col_name not in order_cols:
            try:
                cur.execute(f"ALTER TABLE orders ADD COLUMN {col_name} {col_def}")
            except Exception:
                pass

    # Check promo_preferences columns
    cur.execute("PRAGMA table_info(promo_preferences)")
    promo_cols = {row[1] for row in cur.fetchall()}
    for col_name, col_def in [
        ("last_location_id", "TEXT REFERENCES locations(id)"),
        ("in_service_area", "BOOLEAN DEFAULT 1"),
        ("booked_for_at", "TIMESTAMP"),
        ("last_source_type", "TEXT DEFAULT 'order'")
    ]:
        if col_name not in promo_cols:
            try:
                cur.execute(f"ALTER TABLE promo_preferences ADD COLUMN {col_name} {col_def}")
            except Exception:
                pass

    # Upgrade orders.payment_method CHECK constraint to include 'wise' if missing
    ord_sql_row = cur.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='orders'").fetchone()
    if ord_sql_row and "'wise'" not in ord_sql_row[0]:
        try:
            cur.execute("PRAGMA foreign_keys = OFF")
            cur.execute("PRAGMA legacy_alter_table = ON")
            cur.execute("PRAGMA table_info(orders)")
            existing_ord_cols = [r[1] for r in cur.fetchall()]
            cols_csv = ", ".join(existing_ord_cols)
            cur.execute("ALTER TABLE orders RENAME TO orders_old_mig")
            cur.execute("""
                CREATE TABLE orders (
                    id TEXT PRIMARY KEY,
                    order_number TEXT UNIQUE NOT NULL,
                    business_id TEXT NOT NULL REFERENCES businesses(id) ON DELETE CASCADE,
                    customer_name TEXT NOT NULL,
                    customer_phone TEXT NOT NULL,
                    customer_email TEXT,
                    order_origin TEXT NOT NULL CHECK(order_origin IN ('mavunqo', 'merchant')) DEFAULT 'mavunqo',
                    fulfillment_type TEXT NOT NULL CHECK(fulfillment_type IN ('pickup', 'delivery')) DEFAULT 'pickup',
                    delivery_address TEXT,
                    delivery_pin_lat REAL,
                    delivery_pin_lng REAL,
                    customer_notes TEXT,
                    status TEXT NOT NULL CHECK(status IN ('pending', 'accepted', 'in_kitchen', 'ready', 'completed', 'cancelled', 'declined')) DEFAULT 'pending',
                    subtotal REAL NOT NULL,
                    delivery_fee REAL DEFAULT 0.0,
                    driver_tip REAL DEFAULT 0.0,
                    total REAL NOT NULL,
                    currency TEXT DEFAULT 'DOP',
                    payment_method TEXT NOT NULL CHECK(payment_method IN ('cash', 'card', 'transfer', 'zelle', 'wise', 'cash_or_card')) DEFAULT 'cash',
                    payment_proof_url TEXT,
                    payment_proof_hash TEXT,
                    payment_verified BOOLEAN DEFAULT 0,
                    payment_verified_source TEXT,
                    promo_opt_in BOOLEAN DEFAULT 1,
                    promo_longterm_opt_in BOOLEAN DEFAULT 0,
                    cash_due REAL,
                    cash_received REAL,
                    cash_reconciled BOOLEAN DEFAULT 0,
                    cash_exception_reason TEXT,
                    customer_alias TEXT,
                    phone_hash TEXT,
                    attribution_source TEXT DEFAULT 'mavunqo',
                    is_manual_fallback BOOLEAN DEFAULT 0,
                    estimated_ready_at TIMESTAMP,
                    status_token TEXT UNIQUE NOT NULL,
                    status_token_expires_at TIMESTAMP NOT NULL,
                    decline_reason TEXT,
                    cancellation_reason TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            cur.execute(f"INSERT INTO orders ({cols_csv}) SELECT {cols_csv} FROM orders_old_mig")
            cur.execute("DROP TABLE orders_old_mig")
            cur.execute("PRAGMA legacy_alter_table = OFF")
            cur.execute("PRAGMA foreign_keys = ON")
        except Exception as e:
            print(f"[DB Migration] orders CHECK upgrade warning: {e}")
            cur.execute("PRAGMA legacy_alter_table = OFF")
            cur.execute("PRAGMA foreign_keys = ON")

    # Check drivers columns
    cur.execute("PRAGMA table_info(drivers)")
    driver_cols = {row[1] for row in cur.fetchall()}
    if "pin_code" not in driver_cols:
        try:
            cur.execute("ALTER TABLE drivers ADD COLUMN pin_code TEXT DEFAULT '1234'")
        except Exception:
            pass

    # Check delivery_capacity_settings columns
    cur.execute("PRAGMA table_info(delivery_capacity_settings)")
    cap_cols = {row[1] for row in cur.fetchall()}
    if "rain_mode_active" not in cap_cols:
        try:
            cur.execute("ALTER TABLE delivery_capacity_settings ADD COLUMN rain_mode_active BOOLEAN DEFAULT 0")
        except Exception:
            pass

    # Check locations columns
    cur.execute("PRAGMA table_info(locations)")
    loc_cols = {row[1] for row in cur.fetchall()}
    if "search_aliases" not in loc_cols:
        try:
            cur.execute("ALTER TABLE locations ADD COLUMN search_aliases TEXT")
        except Exception:
            pass

    # Check categories columns
    cur.execute("PRAGMA table_info(categories)")
    cat_cols = {row[1] for row in cur.fetchall()}
    if "parent_category_id" not in cat_cols:
        try:
            cur.execute("ALTER TABLE categories ADD COLUMN parent_category_id TEXT REFERENCES categories(id)")
        except Exception:
            pass
    if "search_aliases" not in cat_cols:
        try:
            cur.execute("ALTER TABLE categories ADD COLUMN search_aliases TEXT")
        except Exception:
            pass

def init_db(db_path: str):
    os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.executescript(SCHEMA_SQL)
    run_migrations(conn)
    for k, v in [
        ("standard_commission_rate", "0.15"),
        ("delivery_fee_dop", "100.0"),
        ("rain_hazard_fee_dop", "50.0"),
        ("max_driver_cash_float_dop", "3000.0"),
        ("dop_to_usd_rate", "60.0"),
    ]:
        conn.execute("INSERT OR IGNORE INTO platform_settings (key, value) VALUES (?, ?)", (k, v))
    conn.commit()
    return conn

def get_connection(db_path: str):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn
