"""
Seed data for Mavunqo Phase 1.
Initializes:
- Admin user: (admin@mavunqo.com)
- Initial categories (Home Services, Dining & Food, Health & Wellness, Auto & Transport, Professional Services, Hospitality & Tourism)
- Initial locations: Sosúa (Active launch market), Cabarete (Upcoming), Puerto Plata (Upcoming)
- Two realistic demo businesses:
  1. 'Sosúa Ocean View Villa Rentals' (Owner with existing website: https://example-sosua-villas.com)
  2. 'Caribe Fix Auto & AC' (Free Mavunqo hosted storefront at /b/caribe-fix-auto)
"""
import uuid
import json
import sqlite3
import os
from .db import init_db
from .auth import hash_password

def seed_database(db_path: str):
    conn = init_db(db_path)
    cur = conn.cursor()

    # 1. Admin User
    admin_id = "user_admin"
    cur.execute("SELECT id FROM users WHERE email = 'admin@mavunqo.com'")
    if not cur.fetchone():
        cur.execute(
            """INSERT INTO users (id, email, password_hash, full_name, role)
               VALUES (?, ?, ?, ?, ?)""",
            (admin_id, "admin@mavunqo.com", hash_password("AdminPass2026!"), "Mavunqo Admin", "admin")
        )

    # 2. Categories
    categories = [
        ("cat_home", "home-services", "Home & Villa Services", "Servicios para el Hogar y Villas", "wrench", 1),
        ("cat_dining", "dining-food", "Dining & Restaurants", "Restaurantes y Comida", "utensils", 2),
        ("cat_health", "health-wellness", "Health & Wellness", "Salud y Bienestar", "heart-pulse", 3),
        ("cat_auto", "auto-transport", "Automotive & Transport", "Automotriz y Transporte", "car", 4),
        ("cat_prof", "professional-services", "Professional Services", "Servicios Profesionales", "briefcase", 5),
        ("cat_tourism", "hospitality-tourism", "Tourism & Activities", "Turismo y Actividades", "palmtree", 6),
    ]
    for cid, cslug, cname_en, cname_es, cicon, corder in categories:
        cur.execute("SELECT id FROM categories WHERE id = ?", (cid,))
        if not cur.fetchone():
            cur.execute(
                """INSERT INTO categories (id, slug, name_en, name_es, icon, sort_order)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (cid, cslug, cname_en, cname_es, cicon, corder)
            )

    # 3. Locations (Sosúa is active launch market, others upcoming)
    locations = [
        ("loc_sosua", "Sosúa", "Puerto Plata Province", "active", 1, 1),
        ("loc_cabarete", "Cabarete", "Puerto Plata Province", "upcoming", 0, 2),
        ("loc_puerto_plata", "Puerto Plata", "Puerto Plata Province", "upcoming", 0, 3),
    ]
    for lid, lname, lreg, lstatus, islaun, lorder in locations:
        cur.execute("SELECT id FROM locations WHERE id = ?", (lid,))
        if not cur.fetchone():
            cur.execute(
                """INSERT INTO locations (id, name, region, status, is_launch_market, sort_order)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (lid, lname, lreg, lstatus, islaun, lorder)
            )

    # 4. Demo Business Owner 1: Carlos (Has existing website)
    owner1_id = "user_carlos_villas"
    cur.execute("SELECT id FROM users WHERE email = 'carlos@sosuavillas.com'")
    if not cur.fetchone():
        cur.execute(
            """INSERT INTO users (id, email, password_hash, full_name, role)
               VALUES (?, ?, ?, ?, ?)""",
            (owner1_id, "carlos@sosuavillas.com", hash_password("OwnerPass2026!"), "Carlos Martinez", "owner")
        )

    # Business 1: Sosúa Ocean View Villa Rentals
    b1_id = "biz_sosua_villas"
    cur.execute("SELECT id FROM businesses WHERE id = ?", (b1_id,))
    if not cur.fetchone():
        cur.execute(
            """INSERT INTO businesses (
                id, owner_id, trading_name, legal_name, slug, category_id, primary_location_id,
                description_en, description_es, status, has_physical_location, address,
                serves_entire_area, website_url, whatsapp, phone, public_email,
                hours_json, rnc_tax_id, rnc_status, approved_by, approved_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)""",
            (
                b1_id, owner1_id, "Sosúa Ocean View Villa Rentals", "Inversiones Martinez SRL",
                "sosua-ocean-view-villas", "cat_tourism", "loc_sosua",
                "Luxury villa rentals and property management across Sosúa and surrounding beaches. Direct owner booking.",
                "Alquiler de villas de lujo y administración de propiedades en Sosúa y playas cercanas. Reservación directa con el propietario.",
                "approved", 1, "Calle Pedro Clisante #42, El Batey, Sosúa",
                1, "https://example-sosua-villas.com", "+18095550192", "+18095550192", "info@sosuavillas.com",
                json.dumps({"monday_friday": "8:00 AM - 6:00 PM", "saturday": "9:00 AM - 2:00 PM", "sunday": "On Call"}),
                "131-98765-4", "verified", admin_id
            )
        )
        # Service areas
        cur.execute("INSERT OR IGNORE INTO business_service_areas (business_id, location_id) VALUES (?, ?)", (b1_id, "loc_sosua"))
        cur.execute("INSERT OR IGNORE INTO business_service_areas (business_id, location_id) VALUES (?, ?)", (b1_id, "loc_cabarete"))

        # Services for Business 1
        b1_services = [
            ("srv_1_1", b1_id, "3-Bedroom Ocean Villa Rental", "Alquiler Villa 3 Habitaciones Vista al Mar",
             "Private pool, fast Wi-Fi, 5-minute walk to Alicia Beach.", "Piscina privada, Wi-Fi de alta velocidad, a 5 minutos de Playa Alicia.",
             250.0, "USD", 1, 1),
            ("srv_1_2", b1_id, "Full Property Management", "Gestión Integral de Propiedades",
             "Complete turn-key rental hosting, maintenance and guest check-in.", "Administración integral de alquileres, mantenimiento y recepción.",
             None, "USD", 0, 2), # Price on request / hidden
        ]
        for sid, sbid, sname_en, sname_es, sdesc_en, sdesc_es, sprice, scur, sdisp, sord in b1_services:
            cur.execute(
                """INSERT INTO services (id, business_id, name_en, name_es, description_en, description_es, price, currency, display_price, sort_order)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (sid, sbid, sname_en, sname_es, sdesc_en, sdesc_es, sprice, scur, sdisp, sord)
            )

    # 5. Demo Business Owner 2: Rosa (Needs free hosted storefront, no existing website)
    owner2_id = "user_rosa_autofix"
    cur.execute("SELECT id FROM users WHERE email = 'rosa@caribefix.com'")
    if not cur.fetchone():
        cur.execute(
            """INSERT INTO users (id, email, password_hash, full_name, role)
               VALUES (?, ?, ?, ?, ?)""",
            (owner2_id, "rosa@caribefix.com", hash_password("OwnerPass2026!"), "Rosa Perez", "owner")
        )

    # Business 2: Caribe Fix Auto & AC (Hosted storefront at /b/caribe-fix-auto)
    b2_id = "biz_caribe_fix"
    cur.execute("SELECT id FROM businesses WHERE id = ?", (b2_id,))
    if not cur.fetchone():
        cur.execute(
            """INSERT INTO businesses (
                id, owner_id, trading_name, legal_name, slug, category_id, primary_location_id,
                description_en, description_es, status, has_physical_location, address,
                serves_entire_area, website_url, whatsapp, phone, public_email,
                hours_json, rnc_tax_id, rnc_status, approved_by, approved_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)""",
            (
                b2_id, owner2_id, "Caribe Fix Auto & AC", "Caribe Fix SRL",
                "caribe-fix-auto", "cat_auto", "loc_sosua",
                "Certified automotive air conditioning recharge, brake repairs, and mobile roadside diagnostics in Sosúa.",
                "Recarga certificada de aire acondicionado automotriz, frenos y diagnóstico a domicilio en Sosúa.",
                "approved", 1, "Carretera Sosúa - Cabarete Km 2, Sosúa",
                1, None, "+18095550843", "+18095550843", "service@caribefix.com",
                json.dumps({"monday_friday": "7:30 AM - 5:30 PM", "saturday": "8:00 AM - 1:00 PM", "sunday": "Closed"}),
                None, "unverified", admin_id # RNC is optional as specified
            )
        )
        # Service areas
        cur.execute("INSERT OR IGNORE INTO business_service_areas (business_id, location_id) VALUES (?, ?)", (b2_id, "loc_sosua"))

        # Services for Business 2
        b2_services = [
            ("srv_2_1", b2_id, "AC Diagnostic & Gas Recharge", "Diagnóstico y Recarga de Aire Acondicionado",
             "Pressure test, leak check and synthetic refrigerant recharge.", "Prueba de presión, detección de fugas y recarga con refrigerante sintético.",
             2800.0, "DOP", 1, 1),
            ("srv_2_2", b2_id, "Brake Pad Replacement & Rotor Polish", "Cambio de Pastillas de Freno y Rectificado",
             "Front and rear brake inspections with ceramic pad installation.", "Inspección de frenos delanteros y traseros con instalación de pastillas cerámicas.",
             4500.0, "DOP", 1, 2),
            ("srv_2_3", b2_id, "Mobile Emergency Assistance", "Asistencia de Emergencia a Domicilio",
             "Battery jump start, tire puncture assistance anywhere in Sosúa.", "Arranque de batería y reparación de neumáticos en cualquier lugar de Sosúa.",
             1500.0, "DOP", 1, 3),
        ]
        for sid, sbid, sname_en, sname_es, sdesc_en, sdesc_es, sprice, scur, sdisp, sord in b2_services:
            cur.execute(
                """INSERT INTO services (id, business_id, name_en, name_es, description_en, description_es, price, currency, display_price, sort_order)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (sid, sbid, sname_en, sname_es, sdesc_en, sdesc_es, sprice, scur, sdisp, sord)
            )

    conn.commit()
    conn.close()
    print("Database successfully initialized and seeded with Sosúa pilot data!")

if __name__ == "__main__":
    db_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "mavunqo.db")
    seed_database(db_file)
