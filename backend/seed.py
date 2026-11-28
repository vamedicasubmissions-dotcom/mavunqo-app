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
    env_admin_pw = os.environ.get("MAVUNQO_ADMIN_PASSWORD", "").strip()
    admin_pw = env_admin_pw or "AdminPass2026!"
    cur.execute("SELECT id FROM users WHERE email = 'admin@mavunqo.com'")
    existing_admin = cur.fetchone()
    if not existing_admin:
        cur.execute(
            """INSERT INTO users (id, email, password_hash, full_name, role)
               VALUES (?, ?, ?, ?, ?)""",
            (admin_id, "admin@mavunqo.com", hash_password(admin_pw), "Mavunqo Admin", "admin")
        )
    elif env_admin_pw:
        cur.execute(
            "UPDATE users SET password_hash = ? WHERE email = 'admin@mavunqo.com'",
            (hash_password(env_admin_pw),)
        )

    # 1b. Two-Person Outreach Staff Accounts
    staff_pw = os.environ.get("MAVUNQO_STAFF_PASSWORD", "").strip() or "StaffPass2026!"
    for sid, semail, sname in [
        ("user_staff_1", "staff1@mavunqo.com", "Outreach Rep 1"),
        ("user_staff_2", "staff2@mavunqo.com", "Outreach Rep 2"),
    ]:
        cur.execute("SELECT id FROM users WHERE email = ?", (semail,))
        if not cur.fetchone():
            cur.execute(
                """INSERT INTO users (id, email, password_hash, full_name, role)
                   VALUES (?, ?, ?, ?, 'staff')""",
                (sid, semail, hash_password(staff_pw), sname),
            )

    # 1b. Secondary Admin Backup Account (preserves admin@mavunqo.com unchanged)
    admin2_id = "user_admin_backup"
    env_admin2_pw = os.environ.get("MAVUNQO_ADMIN2_PASSWORD", "").strip()
    admin2_pw = env_admin2_pw or "MavunqoAdmin#2026!"
    cur.execute("SELECT id FROM users WHERE email = 'owner@mavunqo.com'")
    if not cur.fetchone():
        cur.execute(
            """INSERT INTO users (id, email, password_hash, full_name, role)
               VALUES (?, ?, ?, ?, 'admin')""",
            (admin2_id, "owner@mavunqo.com", hash_password(admin2_pw), "Mavunqo Secondary Admin")
        )
    elif env_admin2_pw:
        cur.execute(
            "UPDATE users SET password_hash = ? WHERE email = 'owner@mavunqo.com'",
            (hash_password(env_admin2_pw),)
        )

    # 2. Categories
    categories = [
        ("cat_health", "health-wellness", "Health & Wellness", "Salud y Bienestar", "heart-pulse", 1, None, "health, clinic, medical, farmacia"),
        ("cat_wellness_massage", "massage-wellness", "Massage & Wellness", "Masajes y Bienestar", "spa", 2, "cat_health", "massage, masajes, spa, mobile massage, masajista"),
        ("cat_beauty", "beauty-personal-care", "Beauty & Personal Care", "Belleza y Cuidado Personal", "scissors", 2, None, "barber, salon, nails, peluqueria, unas"),
        ("cat_fashion", "clothing-fashion", "Clothing & Accessories", "Ropa y Accesorios", "shirt", 3, None, "boutique, clothes, shoes, vestidos, trajes de bano"),
        ("cat_grocery", "groceries-colmados", "Groceries & Colmados", "Supermercados y Colmados", "shopping-cart", 4, None, "supermarket, colmado, drinks, beer, snacks, viveres"),
        ("cat_tourism", "hospitality-tourism", "Hotels & Lodging", "Hoteles y Alojamientos", "palmtree", 5, None, "hotel, villa, lodging, room, stays, hospedaje"),
        ("cat_tours", "tours-activities", "Tours & Activities", "Tours y Actividades", "compass", 6, None, "tours, atv, excursions, excursion, surfing"),
        ("cat_transport", "transportation-rentals", "Transportation & Rentals", "Transporte y Alquileres", "bike", 7, None, "car rental, scooter, moto rental, taxi, airport transfer"),
        ("cat_auto", "auto-transport", "Auto Repair & Services", "Talleres y Servicios Automotrices", "car", 8, None, "mechanic, auto repair, taller, frenos, aire acondicionado"),
        ("cat_home", "home-services", "Home & Property Services", "Servicios para el Hogar y Propiedades", "wrench", 9, None, "cleaning, laundry, repairs, villa maintenance, plomero"),
        ("cat_events", "events-catering", "Events & Catering", "Eventos y Catering", "music", 10, None, "dj, venue, catering, sound, eventos, bodas"),
        ("cat_dining", "dining-food", "Dining & Restaurants", "Restaurantes y Comida", "utensils", 11, None, "restaurant, food, pizza, grill, comida, delivery"),
        ("cat_veterinary", "veterinary-pet-care", "Veterinary & Pet Care", "Veterinaria y Mascotas", "heart", 12, None, "vet, veterinarian, veterinario, pet, dog, cat, mascota, clinic, klinickey"),
        ("cat_prof", "professional-services", "Professional Services", "Servicios Profesionales", "briefcase", 13, None, "legal, accounting, translator"),
        ("cat_legal", "legal-lawyers", "Legal & Lawyers", "Abogados y Legal", "scale", 14, "cat_prof", "lawyer, attorney, abogado, legal, notary, title check, residency, immigration, srl"),
    ]
    for item in categories:
        cid, cslug, cname_en, cname_es, cicon, corder = item[0], item[1], item[2], item[3], item[4], item[5]
        parent_id = item[6] if len(item) > 6 else None
        aliases = item[7] if len(item) > 7 else ""
        cur.execute("SELECT id FROM categories WHERE id = ?", (cid,))
        if not cur.fetchone():
            cur.execute(
                """INSERT INTO categories (id, slug, name_en, name_es, icon, sort_order, parent_category_id, search_aliases)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (cid, cslug, cname_en, cname_es, cicon, corder, parent_id, aliases)
            )
        else:
            cur.execute("UPDATE categories SET name_en = ?, name_es = ?, search_aliases = ? WHERE id = ?", (cname_en, cname_es, aliases, cid))

    # 3. Locations (Sosúa is active launch market, others upcoming)
    locations = [
        ("loc_sosua", "Sosúa", "Puerto Plata Province", "active", 1, 1, "Sosua, El Batey, Los Charamicos"),
        ("loc_montellano", "Villa Montellano", "Puerto Plata Province", "active", 1, 2, "Montellano, Villa Montellano"),
        ("loc_cabarete", "Cabarete", "Puerto Plata Province", "upcoming", 0, 3, "Cabarete, Encuentro"),
        ("loc_puerto_plata", "Puerto Plata", "Puerto Plata Province", "active", 1, 4, "Puerto Plata, Playa Dorada, Puente Seco"),
    ]
    for item in locations:
        lid, lname, lreg, lstatus, islaun, lorder = item[0], item[1], item[2], item[3], item[4], item[5]
        aliases = item[6] if len(item) > 6 else ""
        cur.execute("SELECT id FROM locations WHERE id = ?", (lid,))
        if not cur.fetchone():
            cur.execute(
                """INSERT INTO locations (id, name, region, status, is_launch_market, sort_order, search_aliases)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (lid, lname, lreg, lstatus, islaun, lorder, aliases)
            )
        else:
            cur.execute("UPDATE locations SET search_aliases = ?, status = ?, is_launch_market = ? WHERE id = ?", (aliases, lstatus, islaun, lid))

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
                description_en, description_es, status, requests_enabled, has_physical_location, address,
                serves_entire_area, website_url, whatsapp, phone, public_email,
                hours_json, rnc_tax_id, rnc_status, approved_by, approved_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)""",
            (
                b1_id, owner1_id, "Sosúa Ocean View Villa Rentals", "Inversiones Martinez SRL",
                "sosua-ocean-view-villas", "cat_tourism", "loc_sosua",
                "Luxury villa rentals and property management across Sosúa and surrounding beaches. Direct owner booking.",
                "Alquiler de villas de lujo y administración de propiedades en Sosúa y playas cercanas. Reservación directa con el propietario.",
                "pending", 0, 1, "Calle Pedro Clisante #42, El Batey, Sosúa",
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
                description_en, description_es, status, requests_enabled, has_physical_location, address,
                serves_entire_area, website_url, whatsapp, phone, public_email,
                hours_json, rnc_tax_id, rnc_status, approved_by, approved_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)""",
            (
                b2_id, owner2_id, "Caribe Fix Auto & AC", "Caribe Fix SRL",
                "caribe-fix-auto", "cat_auto", "loc_sosua",
                "Certified automotive air conditioning recharge, brake repairs, and mobile roadside diagnostics in Sosúa.",
                "Recarga certificada de aire acondicionado automotriz, frenos y diagnóstico a domicilio en Sosúa.",
                "pending", 0, 1, "Carretera Sosúa - Cabarete Km 2, Sosúa",
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

    # -------------------------------------------------------------
    # Phase 2: Pilot Restaurants in Sosúa
    # -------------------------------------------------------------
    # Pilot Restaurant 1: El Batey Bistro & Grill
    r1_owner_id = "user_rest1_marco"
    cur.execute("SELECT id FROM users WHERE email = 'marco@elbateybistro.com'")
    if not cur.fetchone():
        cur.execute(
            """INSERT INTO users (id, email, password_hash, full_name, role)
               VALUES (?, ?, ?, ?, ?)""",
            (r1_owner_id, "marco@elbateybistro.com", hash_password("PilotPass2026!"), "Marco Rossi", "owner")
        )

    r1_id = "biz_el_batey_bistro"
    cur.execute("SELECT id FROM businesses WHERE id = ?", (r1_id,))
    if not cur.fetchone():
        cur.execute(
            """INSERT INTO businesses (
                id, owner_id, trading_name, legal_name, slug, category_id, primary_location_id,
                description_en, description_es, status, has_physical_location, address,
                serves_entire_area, website_url, whatsapp, phone, public_email,
                hours_json, rnc_tax_id, rnc_status, approved_by, approved_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)""",
            (
                r1_id, r1_owner_id, "El Batey Bistro & Grill", "Bistro del Sol SRL",
                "el-batey-bistro", "cat_dining", "loc_sosua",
                "Sosúa seafood, steaks, fresh pasta and handcrafted Caribbean cocktails on Calle Pedro Clisante.",
                "Mariscos frescos de Sosúa, carnes a la parrilla, pastas artesanales y cocteles caribeños en Calle Pedro Clisante.",
                "approved", 1, "Calle Pedro Clisante #18, El Batey, Sosúa",
                1, None, "+18095550211", "+18095550211", "orders@elbateybistro.com",
                json.dumps({"monday_sunday": "11:30 AM - 10:30 PM"}),
                "132-44556-1", "verified", admin_id
            )
        )
        cur.execute("INSERT OR IGNORE INTO business_service_areas (business_id, location_id) VALUES (?, ?)", (r1_id, "loc_sosua"))

        # Menu categories
        cat_mains = "mcat_bistro_mains"
        cat_drinks = "mcat_bistro_drinks"
        cur.execute("INSERT INTO menu_categories (id, business_id, name_en, name_es, sort_order) VALUES (?, ?, ?, ?, ?)",
                    (cat_mains, r1_id, "Fresh Catch & Grill", "Pescados y Parrilla", 1))
        cur.execute("INSERT INTO menu_categories (id, business_id, name_en, name_es, sort_order) VALUES (?, ?, ?, ?, ?)",
                    (cat_drinks, r1_id, "Tropical Beverages", "Bebidas Tropicales", 2))

        # Menu items
        m1 = "mi_red_snapper"
        cur.execute("""INSERT INTO menu_items (id, business_id, category_id, name_en, name_es, description_en, description_es, price, currency, is_available, sort_order)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'DOP', 1, 1)""",
                    (m1, r1_id, cat_mains, "Whole Red Snapper with Tostones", "Chillo Entero con Tostones",
                     "Freshly fried or grilled local red snapper served with garlic tostones and green salad.",
                     "Chillo fresco frito o a la parrilla con tostones al ajillo y ensalada verde.", 750.0))
        cur.execute("""INSERT INTO menu_modifiers (id, menu_item_id, group_name_en, group_name_es, name_en, name_es, price_delta, is_required)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    ("mod_chillo_garlic", m1, "Preparation", "Preparación", "Garlic Butter Glaze", "Al Ajillo", 50.0, 0))

        m2 = "mi_churrasco"
        cur.execute("""INSERT INTO menu_items (id, business_id, category_id, name_en, name_es, description_en, description_es, price, currency, is_available, sort_order)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'DOP', 1, 2)""",
                    (m2, r1_id, cat_mains, "Grilled Churrasco Steak 10oz", "Churrasco a la Parrilla 10oz",
                     "Certified Angus skirt steak served with chimichurri sauce and yucca fries.",
                     "Falda Angus a la parrilla con chimichurri casero y yuca frita.", 950.0))

        m3 = "mi_passion_juice"
        cur.execute("""INSERT INTO menu_items (id, business_id, category_id, name_en, name_es, description_en, description_es, price, currency, is_available, sort_order)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'DOP', 1, 1)""",
                    (m3, r1_id, cat_drinks, "Fresh Passion Fruit Juice", "Jugo Natural de Chinola",
                     "Chilled natural Dominican passion fruit juice.", "Jugo natural frío de chinola dominicana.", 180.0))

    # Pilot Restaurant 2: Playa Alicia Woodfire Pizza
    r2_owner_id = "user_rest2_giovanni"
    cur.execute("SELECT id FROM users WHERE email = 'giovanni@aliciapizza.com'")
    if not cur.fetchone():
        cur.execute(
            """INSERT INTO users (id, email, password_hash, full_name, role)
               VALUES (?, ?, ?, ?, ?)""",
            (r2_owner_id, "giovanni@aliciapizza.com", hash_password("PilotPass2026!"), "Giovanni Moretti", "owner")
        )

    r2_id = "biz_playa_alicia_pizza"
    cur.execute("SELECT id FROM businesses WHERE id = ?", (r2_id,))
    if not cur.fetchone():
        cur.execute(
            """INSERT INTO businesses (
                id, owner_id, trading_name, legal_name, slug, category_id, primary_location_id,
                description_en, description_es, status, has_physical_location, address,
                serves_entire_area, website_url, whatsapp, phone, public_email,
                hours_json, rnc_tax_id, rnc_status, approved_by, approved_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)""",
            (
                r2_id, r2_owner_id, "Playa Alicia Woodfire Pizza", "Alicia Pizza SRL",
                "playa-alicia-woodfire-pizza", "cat_dining", "loc_sosua",
                "Authentic artisanal sourdough pizza baked in our oak wood-fired stone oven overlooking Playa Alicia.",
                "Auténtica pizza artesanal con masa madre horneada en leña con vista a Playa Alicia.",
                "approved", 1, "Calle Dr. Rosen #5, Playa Alicia, Sosúa",
                1, None, "+18095550322", "+18095550322", "ciao@aliciapizza.com",
                json.dumps({"tuesday_sunday": "12:00 PM - 11:00 PM"}),
                "132-77889-2", "verified", admin_id
            )
        )
        cur.execute("INSERT OR IGNORE INTO business_service_areas (business_id, location_id) VALUES (?, ?)", (r2_id, "loc_sosua"))

        cat_pizzas = "mcat_pizza_pies"
        cur.execute("INSERT INTO menu_categories (id, business_id, name_en, name_es, sort_order) VALUES (?, ?, ?, ?, ?)",
                    (cat_pizzas, r2_id, "Artisan Woodfire Pizzas", "Pizzas a la Leña", 1))

        p1 = "mi_margherita_dop"
        cur.execute("""INSERT INTO menu_items (id, business_id, category_id, name_en, name_es, description_en, description_es, price, currency, is_available, sort_order)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'DOP', 1, 1)""",
                    (p1, r2_id, cat_pizzas, "Margherita Bufala", "Margarita con Mozzarella de Búfala",
                     "San Marzano tomato sauce, fresh buffalo mozzarella, basil, extra virgin olive oil.",
                     "Salsa San Marzano, mozzarella fresca de búfala, albahaca y aceite de oliva virgen extra.", 620.0))
        cur.execute("""INSERT INTO menu_modifiers (id, menu_item_id, group_name_en, group_name_es, name_en, name_es, price_delta, is_required)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    ("mod_extra_bufala", p1, "Extra Cheese", "Queso Extra", "Extra Buffalo Mozzarella", "Doble Mozzarella", 120.0, 0))

        p2 = "mi_diavola"
        cur.execute("""INSERT INTO menu_items (id, business_id, category_id, name_en, name_es, description_en, description_es, price, currency, is_available, sort_order)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'DOP', 1, 2)""",
                    (p2, r2_id, cat_pizzas, "Spicy Diavola Pizza", "Pizza Diavola Picante",
                     "Spicy Italian salami, crushed red pepper flakes, mozzarella, San Marzano tomatoes.",
                     "Salami italiano picante, hojuelas de chile, mozzarella y salsa San Marzano.", 680.0))

    # Pilot Restaurant 3: D'Sabor Criollo Dominicano
    r3_owner_id = "user_rest3_juana"
    cur.execute("SELECT id FROM users WHERE email = 'juana@saborcriollo.do'")
    if not cur.fetchone():
        cur.execute(
            """INSERT INTO users (id, email, password_hash, full_name, role)
               VALUES (?, ?, ?, ?, ?)""",
            (r3_owner_id, "juana@saborcriollo.do", hash_password("PilotPass2026!"), "Juana Santana", "owner")
        )

    r3_id = "biz_sabor_criollo"
    cur.execute("SELECT id FROM businesses WHERE id = ?", (r3_id,))
    if not cur.fetchone():
        cur.execute(
            """INSERT INTO businesses (
                id, owner_id, trading_name, legal_name, slug, category_id, primary_location_id,
                description_en, description_es, status, has_physical_location, address,
                serves_entire_area, website_url, whatsapp, phone, public_email,
                hours_json, rnc_tax_id, rnc_status, approved_by, approved_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)""",
            (
                r3_id, r3_owner_id, "D'Sabor Criollo Dominicano", "Comidas del Norte SRL",
                "sabor-criollo-dominicano", "cat_dining", "loc_sosua",
                "Traditional Dominican homestyle cooking, famous mofongos, and fresh daily plato del día in Sosúa.",
                "Comida típica dominicana casera, los mejores mofongos de chicharrón y plato del día en Sosúa.",
                "approved", 1, "Calle Dr. Alejo Martínez #8, Los Charamicos, Sosúa",
                1, None, "+18095550433", "+18095550433", "contacto@saborcriollo.do",
                json.dumps({"monday_saturday": "10:30 AM - 9:00 PM", "sunday": "11:00 AM - 5:00 PM"}),
                "132-99123-3", "verified", admin_id
            )
        )
        cur.execute("INSERT OR IGNORE INTO business_service_areas (business_id, location_id) VALUES (?, ?)", (r3_id, "loc_sosua"))

        cat_criollo = "mcat_criollo_specials"
        cur.execute("INSERT INTO menu_categories (id, business_id, name_en, name_es, sort_order) VALUES (?, ?, ?, ?, ?)",
                    (cat_criollo, r3_id, "Dominican Specialties", "Especialidades Criollas", 1))

        d1 = "mi_mofongo_chicharron"
        cur.execute("""INSERT INTO menu_items (id, business_id, category_id, name_en, name_es, description_en, description_es, price, currency, is_available, sort_order)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'DOP', 1, 1)""",
                    (d1, r3_id, cat_criollo, "Crispy Pork Belly Mofongo", "Mofongo de Chicharrón con Caldo",
                     "Fried green plantains mashed with garlic, crispy pork belly cracklings, served with rich bone broth.",
                     "Plátano verde majado con ajo y crujiente chicharrón de cerdo, servido con caldo caliente.", 480.0))
        cur.execute("""INSERT INTO menu_modifiers (id, menu_item_id, group_name_en, group_name_es, name_en, name_es, price_delta, is_required)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    ("mod_extra_caldo", d1, "Broth & Gravy", "Caldo", "Extra Garlic Pork Broth", "Caldo Extra al Ajillo", 40.0, 0))

        d2 = "mi_chivo_liniero"
        cur.execute("""INSERT INTO menu_items (id, business_id, category_id, name_en, name_es, description_en, description_es, price, currency, is_available, sort_order)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'DOP', 1, 2)""",
                    (d2, r3_id, cat_criollo, "Braised Spicy Goat (Chivo Liniero)", "Chivo Liniero Guisado",
                     "Tender goat meat slow-braised with oregano, scotch bonnet and dark Dominican rum, served with moro de guandules.",
                     "Chivo tierno guisado a fuego lento con orégano criollo, servido con moro de guandules.", 540.0))

    # -------------------------------------------------------------
    # Multi-Vertical Benchmark: City Lights Sosúa (Hotel & Rooftop Lounge)
    # -------------------------------------------------------------
    cl_owner_id = "user_city_lights_owner"
    cur.execute("SELECT id FROM users WHERE email = 'stay@citylightssosua.com'")
    if not cur.fetchone():
        cur.execute(
            """INSERT INTO users (id, email, password_hash, full_name, role)
               VALUES (?, ?, ?, ?, ?)""",
            (cl_owner_id, "stay@citylightssosua.com", hash_password("CityLights2026!"), "City Lights Management", "owner")
        )

    cl_id = "biz_city_lights"
    cur.execute("SELECT id FROM businesses WHERE id = ?", (cl_id,))
    if not cur.fetchone():
        cur.execute(
            """INSERT INTO businesses (
                id, owner_id, trading_name, legal_name, slug, category_id, primary_location_id,
                description_en, description_es, status, has_physical_location, address,
                serves_entire_area, website_url, whatsapp, phone, public_email,
                hours_json, rnc_tax_id, rnc_status, approved_by, approved_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)""",
            (
                cl_id, cl_owner_id, "City Lights Boutique Hotel & Lounge", "City Lights Hospitality SRL",
                "city-lights-sosua", "cat_tourism", "loc_sosua",
                "Sosúa boutique hotel, rooftop pool lounge, premium private suites and comfortable dorm beds in El Batey.",
                "Hotel boutique en Sosúa, terraza con piscina, suites privadas y cómodas camas de hospedaje en El Batey.",
                "approved", 1, "Calle Dr. Rosen #22, El Batey, Sosúa",
                1, None, "+18095550999", "+18095550999", "frontdesk@citylightssosua.com",
                json.dumps({"reception": "24/7 Front Desk", "rooftop_lounge": "4:00 PM - 1:00 AM"}),
                "133-11223-4", "verified", admin_id
            )
        )
        cur.execute("INSERT OR IGNORE INTO business_service_areas (business_id, location_id) VALUES (?, ?)", (cl_id, "loc_sosua"))

        # Lodging Units
        units = [
            ("unit_cl_101", cl_id, "Room 101", "suite", "Deluxe Ocean View Balcony Suite", "Suite Deluxe con Balcón y Vista al Mar",
             "King bed, private balcony, air conditioning, smart TV, rainfall shower.",
             "Cama king, balcón privado, aire acondicionado, smart TV, ducha de lluvia.", 2, 75.0, 1),
            ("unit_cl_102", cl_id, "Room 102", "private_room", "Standard Garden Queen Room", "Habitación Estándar Queen con Vista al Jardín",
             "Queen bed, silent inverter AC, mini-fridge, workspace, high-speed fiber Wi-Fi.",
             "Cama queen, aire acondicionado silencioso, mini-nevera, escritorio, Wi-Fi fibra óptica.", 2, 55.0, 2),
            ("unit_cl_b01", cl_id, "Bed B-1", "dorm_bed", "Traveler Single Bed in 4-Bed Co-living Dorm", "Cama Individual en Habitación Compartida de 4",
             "Individual bunk with privacy curtain, personal reading light, power socket, and locked luggage drawer.",
             "Litera con cortina de privacidad, lámpara de lectura, toma de corriente y gaveta con candado.", 1, 22.0, 3)
        ]
        for uid, ubid, unum, utype, uname_en, uname_es, udesc_en, udesc_es, ucap, uprice, uord in units:
            cur.execute(
                """INSERT INTO lodging_units (
                    id, business_id, unit_number, unit_type, name_en, name_es, description_en, description_es,
                    capacity, base_price_night, currency, is_available, sort_order
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'USD', 1, ?)""",
                (uid, ubid, unum, utype, uname_en, uname_es, udesc_en, udesc_es, ucap, uprice, uord)
            )

        # Seed sample reservation for staff check-in test
        cur.execute(
            """INSERT INTO reservations (
                id, reservation_code, business_id, unit_id, guest_name, guest_contact, guest_email,
                check_in_date, check_out_date, nights, guest_count, nightly_rate, total_amount, currency,
                status, payment_method, cash_collected, status_token
            ) VALUES (?, ?, ?, ?, ?, ?, ?, '2026-11-15', '2026-11-18', 3, 2, 75.0, 225.0, 'USD',
                      'confirmed', 'cash_on_arrival', 0.0, ?)""",
            (
                "res_cl_demo1", "CL-2611-9842", cl_id, "unit_cl_101", "David Miller", "+18295551122",
                "david@example.com", "tok_cl_demo_status_token"
            )
        )


    # -------------------------------------------------------------
    # Supermarkets & Colmados (Sosúa Grocery & Convenience Delivery)
    # -------------------------------------------------------------
    # Business 1: Supermercado Playero (Premier Supermarket & Imported Goods)
    sup1_owner = "user_sup1_playero"
    cur.execute("SELECT id FROM users WHERE email = 'orders@superplayero.com'")
    if not cur.fetchone():
        cur.execute(
            """INSERT INTO users (id, email, password_hash, full_name, role)
               VALUES (?, ?, ?, ?, ?)""",
            (sup1_owner, "orders@superplayero.com", hash_password("PlayeroPass2026!"), "Supermercado Playero Admin", "owner")
        )

    b_playero = "biz_super_playero"
    cur.execute("SELECT id FROM businesses WHERE id = ?", (b_playero,))
    if not cur.fetchone():
        cur.execute(
            """INSERT INTO businesses (
                id, owner_id, trading_name, legal_name, slug, category_id, primary_location_id,
                description_en, description_es, status, has_physical_location, address,
                serves_entire_area, website_url, whatsapp, phone, public_email,
                hours_json, rnc_tax_id, rnc_status, approved_by, approved_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)""",
            (
                b_playero, sup1_owner, "Supermercado Playero", "Supermercado Playero SAS",
                "supermercado-playero", "cat_grocery", "loc_sosua",
                "Sosúa's primary full-scale supermarket: fresh produce, prime meats, European & US imported specialties, bakery and pantry staples.",
                "El supermercado principal de Sosúa: carnes de primera, productos importados, panadería fresca y víveres.",
                "approved", 1, "Carretera Sosúa - Cabarete Km 1, El Batey, Sosúa",
                1, None, "+18095550611", "+18095550611", "deliveries@superplayero.com",
                json.dumps({"monday_saturday": "8:00 AM - 9:00 PM", "sunday": "9:00 AM - 6:00 PM"}),
                "101-55443-1", "verified", admin_id
            )
        )
        cur.execute("INSERT OR IGNORE INTO business_service_areas (business_id, location_id) VALUES (?, ?)", (b_playero, "loc_sosua"))

        cat_essentials = "gcat_playero_essentials"
        cat_pantry = "gcat_playero_pantry"
        cat_drinks = "gcat_playero_beverages"
        cur.execute("INSERT INTO menu_categories (id, business_id, name_en, name_es, sort_order) VALUES (?, ?, ?, ?, ?)",
                    (cat_essentials, b_playero, "Fresh Essentials & Dairy", "Lácteos y Frescos", 1))
        cur.execute("INSERT INTO menu_categories (id, business_id, name_en, name_es, sort_order) VALUES (?, ?, ?, ?, ?)",
                    (cat_pantry, b_playero, "Pantry, Bread & Snacks", "Despensa, Pan y Snacks", 2))
        cur.execute("INSERT INTO menu_categories (id, business_id, name_en, name_es, sort_order) VALUES (?, ?, ?, ?, ?)",
                    (cat_drinks, b_playero, "Water, Juices & Spirits", "Agua, Bebidas y Licores", 3))

        # Items
        cur.execute("""INSERT INTO menu_items (id, business_id, category_id, name_en, name_es, description_en, description_es, price, currency, is_available, sort_order)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'DOP', 1, 1)""",
                    ("gi_water_botellon", b_playero, cat_drinks, "5-Gallon Drinking Water Jug (Refill / Delivery)", "Botellón de Agua 5 Galones (Recarga)",
                     "Pure filtered drinking water 5-gallon jug delivered to your villa or condo.",
                     "Botellón de 5 galones de agua purificada entregado a su villa o apartamento.", 95.0))

        cur.execute("""INSERT INTO menu_items (id, business_id, category_id, name_en, name_es, description_en, description_es, price, currency, is_available, sort_order)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'DOP', 1, 2)""",
                    ("gi_presidente_pack", b_playero, cat_drinks, "Presidente Beer 6-Pack (Cold)", "Cerveza Presidente 6-Pack (Bien Fría)",
                     "Dominican iconic pilsner beer, delivered cold.",
                     "La cerveza insignia dominicana, entregada vestida de novia.", 540.0))

        cur.execute("""INSERT INTO menu_items (id, business_id, category_id, name_en, name_es, description_en, description_es, price, currency, is_available, sort_order)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'DOP', 1, 1)""",
                    ("gi_milk_dos_pinos", b_playero, cat_essentials, "Dos Pinos Whole Milk 1L", "Leche Entera Dos Pinos 1L",
                     "Pasteurized whole dairy milk box.", "Leche entera pasteurizada 1 litro.", 115.0))

        cur.execute("""INSERT INTO menu_items (id, business_id, category_id, name_en, name_es, description_en, description_es, price, currency, is_available, sort_order)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'DOP', 1, 2)""",
                    ("gi_eggs_crate", b_playero, cat_essentials, "Farm Fresh Eggs (Crate of 12)", "Huevos Frescos de Granja (Docena)",
                     "Grade A fresh domestic eggs.", "Docena de huevos frescos de granja.", 145.0))

        cur.execute("""INSERT INTO menu_items (id, business_id, category_id, name_en, name_es, description_en, description_es, price, currency, is_available, sort_order)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'DOP', 1, 1)""",
                    ("gi_bread_pan_sobao", b_playero, cat_pantry, "Fresh Artisanal Pan Sobao Loaf", "Pan Sobao Artesanal Fresco",
                     "Freshly baked soft Dominican bakery loaf.", "Pan sobao tradicional recién horneado.", 80.0))

        cur.execute("""INSERT INTO menu_items (id, business_id, category_id, name_en, name_es, description_en, description_es, price, currency, is_available, sort_order)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'DOP', 1, 2)""",
                    ("gi_cafe_santo_domingo", b_playero, cat_pantry, "Café Santo Domingo Ground 1lb (453g)", "Café Santo Domingo Molido 1lb",
                     "Iconic Dominican aromatic dark roasted ground coffee.", "Café dominicano tostado y molido de primera calidad.", 320.0))

    # Business 2: Colmado La Tambora (Fast 20-Min Neighborhood Corner Store Delivery)
    sup2_owner = "user_sup2_colmado"
    cur.execute("SELECT id FROM users WHERE email = 'tambora@colmadososua.com'")
    if not cur.fetchone():
        cur.execute(
            """INSERT INTO users (id, email, password_hash, full_name, role)
               VALUES (?, ?, ?, ?, ?)""",
            (sup2_owner, "tambora@colmadososua.com", hash_password("ColmadoPass2026!"), "Colmado La Tambora", "owner")
        )

    b_tambora = "biz_colmado_tambora"
    cur.execute("SELECT id FROM businesses WHERE id = ?", (b_tambora,))
    if not cur.fetchone():
        cur.execute(
            """INSERT INTO businesses (
                id, owner_id, trading_name, legal_name, slug, category_id, primary_location_id,
                description_en, description_es, status, has_physical_location, address,
                serves_entire_area, website_url, whatsapp, phone, public_email,
                hours_json, rnc_tax_id, rnc_status, approved_by, approved_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)""",
            (
                b_tambora, sup2_owner, "Colmado La Tambora (Express Delivery)", "La Tambora Delivery SRL",
                "colmado-la-tambora-express", "cat_grocery", "loc_sosua",
                "Traditional Dominican neighborhood colmado: 20-minute express motorcycle delivery of cold ice bags, cold beers, sodas, plantains, snacks and phone recargas in Sosúa.",
                "Colmado tradicional con servicio a domicilio en 20 minutos: fundas de hielo, cervezas vestidas de novia, plátanos, víveres y recargas.",
                "approved", 1, "Calle Ayuntamiento #14, El Batey, Sosúa",
                1, None, "+18095550722", "+18095550722", "pedidos@colmadososua.com",
                json.dumps({"monday_sunday": "7:00 AM - 12:00 AM"}),
                "101-88992-4", "verified", admin_id
            )
        )
        cur.execute("INSERT OR IGNORE INTO business_service_areas (business_id, location_id) VALUES (?, ?)", (b_tambora, "loc_sosua"))

        cat_col_rapid = "gcat_col_rapid"
        cat_col_pantry = "gcat_col_pantry"
        cur.execute("INSERT INTO menu_categories (id, business_id, name_en, name_es, sort_order) VALUES (?, ?, ?, ?, ?)",
                    (cat_col_rapid, b_tambora, "Fast Delivery Essentials", "Lo Más Pedido al Colmado", 1))
        cur.execute("INSERT INTO menu_categories (id, business_id, name_en, name_es, sort_order) VALUES (?, ?, ?, ?, ?)",
                    (cat_col_pantry, b_tambora, "Daily Produce & Kitchen", "Víveres y Cocina", 2))

        cur.execute("""INSERT INTO menu_items (id, business_id, category_id, name_en, name_es, description_en, description_es, price, currency, is_available, sort_order)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'DOP', 1, 1)""",
                    ("ci_ice_bag", b_tambora, cat_col_rapid, "Large Bag of Tube Ice (Funda de Hielo)", "Funda de Hielo en Tubitos",
                     "Clean tube ice bag delivered cold in minutes.", "Funda grande de hielo en tubo limpio y purificado.", 75.0))

        cur.execute("""INSERT INTO menu_items (id, business_id, category_id, name_en, name_es, description_en, description_es, price, currency, is_available, sort_order)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'DOP', 1, 2)""",
                    ("ci_presidente_grande", b_tambora, cat_col_rapid, "Presidente Grande (Cerveza Vestida de Novia)", "Presidente Grande Fría",
                     "650ml Grande Presidente, sub-zero cold.", "Cerveza grande bien fría.", 200.0))

        cur.execute("""INSERT INTO menu_items (id, business_id, category_id, name_en, name_es, description_en, description_es, price, currency, is_available, sort_order)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'DOP', 1, 3)""",
                    ("ci_ron_barcelo", b_tambora, cat_col_rapid, "Ron Barceló Imperial 700ml", "Ron Barceló Imperial 700ml",
                     "Premium aged Dominican dark sipping rum.", "Ron dominicano prémium añejado.", 1150.0))

        cur.execute("""INSERT INTO menu_items (id, business_id, category_id, name_en, name_es, description_en, description_es, price, currency, is_available, sort_order)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'DOP', 1, 1)""",
                    ("ci_platanos_pack", b_tambora, cat_col_pantry, "Fresh Green Plantains (Pack of 5)", "Plátanos Verdes (Ramillete de 5)",
                     "Freshly harvested Cibao green plantains for tostones or mangú.", "Plátanos verdes frescos ideales para tostones o mangú.", 125.0))

        cur.execute("""INSERT INTO menu_items (id, business_id, category_id, name_en, name_es, description_en, description_es, price, currency, is_available, sort_order)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'DOP', 1, 2)""",
                    ("ci_salami_induveca", b_tambora, cat_col_pantry, "Induveca Super Especial Salami 1lb", "Salami Induveca Súper Especial 1lb",
                     "Dominican household favorite salami for breakfast or frito combo.", "El salami preferido de las familias dominicanas.", 185.0))

    # -------------------------------------------------------------
    # Clothing Store: Yaha Style RD (Real Boutique Catalog)
    # -------------------------------------------------------------

    # -------------------------------------------------------------
    # Demo Client: Shopper for Clothing & Food
    # -------------------------------------------------------------
    shopper_id = "user_shopper_demo"
    cur.execute("SELECT id FROM users WHERE email = 'shopper@mavunqo.com'")
    if not cur.fetchone():
        cur.execute(
            """INSERT INTO users (id, email, password_hash, full_name, role)
               VALUES (?, ?, ?, ?, ?)""",
            (shopper_id, "shopper@mavunqo.com", hash_password("Shopper2026!"), "Elena Rodriguez", "owner")
        )

    cloth_owner = "user_clothe_yahaira"
    cur.execute("SELECT id FROM users WHERE email = 'yahastylerd@gmail.com' OR email = 'yahaira@tropicalwavesboutique.com'")
    if not cur.fetchone():
        cur.execute(
            """INSERT INTO users (id, email, password_hash, full_name, role)
               VALUES (?, ?, ?, ?, ?)""",
            (cloth_owner, "yahastylerd@gmail.com", hash_password("YahaStyle2026!"), "Yahaira Garcia", "owner")
        )

    b_clothe = "biz_tropical_waves_boutique"
    cur.execute("SELECT id FROM businesses WHERE id = ? OR slug = 'yaha-style-rd'", (b_clothe,))
    existing_biz = cur.fetchone()
    if not existing_biz:
        cur.execute(
            """INSERT INTO businesses (
                id, owner_id, trading_name, legal_name, slug, category_id, primary_location_id,
                description_en, description_es, status, has_physical_location, address,
                serves_entire_area, website_url, whatsapp, phone, public_email,
                logo_url, cover_image_url,
                hours_json, rnc_tax_id, rnc_status, service_modes_supported, pickup_pin_note,
                approved_by, approved_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)""",
            (
                b_clothe, cloth_owner, "Yaha Style RD", "Yaha Style RD - Yahaira Garcia",
                "yaha-style-rd", "cat_fashion", "loc_sosua",
                "Online clothing store delivering across Puerto Plata and Sosúa.",
                "Tienda de ropa online con entregas en Puerto Plata y Sosúa.",
                "approved", 0, "Online Clothing Store (Puerto Plata & Sosúa Delivery)",
                1, None, "+18296414722", "+18296414722", "yahastylerd@gmail.com",
                "/frontend/uploads/yahastyle/yaha_01.jpg",
                "/frontend/uploads/yahastyle/yaha_02.jpg",
                json.dumps({"monday_saturday": "9:30 AM - 8:00 PM", "sunday": "10:00 AM - 4:00 PM"}),
                "131-44781-9", "verified",
                json.dumps(["delivery"]),
                "Pickup only (items ship from Puerto Plata): Puerto Plata (Sosúa transport parada) or Sosúa (taxi stand across from the Texaco gas station).",
                admin_id
            )
        )
        cur.execute("INSERT OR IGNORE INTO business_service_areas (business_id, location_id) VALUES (?, ?)", (b_clothe, "loc_sosua"))
        cur.execute("INSERT OR IGNORE INTO business_service_areas (business_id, location_id) VALUES (?, ?)", (b_clothe, "loc_puerto_plata"))

    # Seed all boutique categories
    boutique_cats = [('ccat_swimwear', 'Swimwear & Boardshorts', 'Trajes de Baño y Bañadores', 1), ('ccat_linen_apparel', 'Linen Dresses & Beach Shirts', 'Vestidos de Lino y Camisas Playeras', 2), ('ccat_yaha_dresses', 'Chic Dresses & Evening Outfits', 'Vestidos Elegantes y de Noche', 1), ('ccat_yaha_casual', 'Casual Wear & Pants', 'Ropa Casual, Joggers y Tops', 2), ('ccat_yaha_denim', 'Denim, Jeans & Skirts', 'Jeans, Pantalones y Faldas Denim', 3), ('ccat_yaha_swim', 'Swimwear & One-Pieces', 'Trajes de Baño y Monokinis', 4), ('ccat_yaha_tops', 'Glitter Sets, Tanks & Tops', 'Conjuntos Brillantes y Tops Urbanos', 5)]
    for cid, cname_en, cname_es, csort in boutique_cats:
        cur.execute("INSERT OR REPLACE INTO menu_categories (id, business_id, name_en, name_es, sort_order) VALUES (?, ?, ?, ?, ?)",
                    (cid, b_clothe, cname_en, cname_es, csort))

    # Seed all 43 boutique items with photos and descriptions
    boutique_items = [('yaha_01', 'ccat_yaha_dresses', 'Red Twist-Front Ribbed Long Sleeve Dress', 'Vestido Rojo Manga Larga con Nudo Delantero', 'Fitted ribbed bodycon dress with knot detail and plunge V-neckline.', 'Vestido acanalado entallado de manga larga con elegante nudo al frente.', 1850.0, 'DOP', '/frontend/uploads/yahastyle/yaha_01.jpg', 1, 1), ('yaha_02', 'ccat_yaha_dresses', 'Red Strapless Asymmetric Cocktail Dress', 'Vestido Rojo Asimétrico sin Tirantes', 'Sleek strapless cowl neck party dress with modern geometric hemline.', 'Vestido de fiesta sin tirantes con escote fluido y bajo asimétrico.', 1650.0, 'DOP', '/frontend/uploads/yahastyle/yaha_02.jpg', 1, 2), ('yaha_03', 'ccat_yaha_dresses', 'Black & White Off-Shoulder Grid Check Dress', 'Vestido Cuadriculado Blanco y Negro Off-Shoulder', 'Chic off-the-shoulder fitted check dress with discreet front leg slit.', 'Vestido a cuadros blanco y negro con hombros descubiertos y abertura frontal.', 1750.0, 'DOP', '/frontend/uploads/yahastyle/yaha_03.jpg', 1, 3), ('yaha_04', 'ccat_yaha_dresses', 'Red Cutout Knot Mini Sun Dress', 'Vestido Corto Rojo con Abertura Frontal', 'Flirty summer bodycon dress with front twist knot and waist cutout.', 'Vestido veraniego fresco con nudo y abertura estilizada en la cintura.', 1550.0, 'DOP', '/frontend/uploads/yahastyle/yaha_04.jpg', 1, 4), ('yaha_05', 'ccat_yaha_dresses', 'Black Ruched Off-Shoulder Midi Dress', 'Vestido Negro Drapeado Hombro Caído', 'Elegant draped and ruched evening dress with one-shoulder silhouette.', 'Vestido de noche drapeado elegante con silueta asimétrica de hombro caído.', 1950.0, 'DOP', '/frontend/uploads/yahastyle/yaha_05.jpg', 1, 5), ('yaha_06', 'ccat_yaha_dresses', 'Emerald Green Ribbed Racerback Mini Dress', 'Vestido Verde Esmeralda Acanalado Espalda Deportiva', 'Sleeveless high-neck ribbed knit casual mini dress with racerback straps.', 'Vestido mini acanalado verde esmeralda con tirantes deportivos en la espalda.', 1450.0, 'DOP', '/frontend/uploads/yahastyle/yaha_06.jpg', 1, 6), ('yaha_07', 'ccat_yaha_dresses', 'Sporty Trio Ribbed Tank Dresses (Yellow/Red/Black)', 'Vestido Deportivo Tricolor a Rayas (Set / Unitario)', 'Athletic ribbed cotton tank dress with contrast piping borders.', 'Vestido deportivo de tirantes con detalles en contraste.', 1350.0, 'DOP', '/frontend/uploads/yahastyle/yaha_07.jpg', 1, 7), ('yaha_08', 'ccat_yaha_dresses', 'Peach Halter Cutout Bodycon Dress', 'Vestido Melocotón Halter con Espalda Cruzada', 'Vibrant ribbed stretch dress with unique halter neck and strap details.', 'Vestido entallado color melocotón con cuello halter y tirantes ajustables.', 1550.0, 'DOP', '/frontend/uploads/yahastyle/yaha_08.jpg', 1, 8), ('yaha_09', 'ccat_yaha_dresses', 'Summer Ribbed Cutout Dresses (Pink & Red)', 'Vestidos Veraniegos de Tirantes con Nudo (Rosa y Rojo)', 'Sleeveless spaghetti-strap bodycon midi dress in vibrant tropical shades.', 'Vestidos frescos de verano con tirantes finos en tonos rosa y rojo.', 1500.0, 'DOP', '/frontend/uploads/yahastyle/yaha_09.jpg', 1, 9), ('yaha_10', 'ccat_yaha_dresses', 'Black Sweetheart Mini Dress with Gold Button Accent', 'Vestido Negro Escote Corazón con Botón Dorado', 'Tailored long-sleeve evening mini dress with notched sweetheart neckline.', 'Elegante vestido negro entallado de manga larga con escote corazón y botón dorado.', 2100.0, 'DOP', '/frontend/uploads/yahastyle/yaha_10.jpg', 1, 10), ('yaha_11', 'ccat_yaha_casual', 'Black Long-Sleeve Active Romper / Jumpsuit', 'Enterizo Deportivo Negro de Manga Larga con Cremallera', 'Full-body stretch athletic activewear romper with front half-zip and mock collar.', 'Enterizo elástico de compresión para entrenamiento y estilo urbano.', 1950.0, 'DOP', '/frontend/uploads/yahastyle/yaha_11.jpg', 1, 11), ('yaha_12', 'ccat_yaha_dresses', 'Emerald Green Satin Sparkle Cocktail Dress', 'Vestido Satinado Verde Esmeralda con Tirantes Brillantes', 'Glamorous liquid satin slip dress featuring rhinestone sparkle straps.', 'Vestido de satén fluido verde esmeralda con tirantes brillantes de pedrería.', 2250.0, 'DOP', '/frontend/uploads/yahastyle/yaha_12.jpg', 1, 12), ('yaha_13', 'ccat_yaha_dresses', 'Liquid Black Satin Cocktail Duo Dresses', 'Vestido Corto de Satén Negro para Coctel', 'Seductive black satin body-skimming cocktail dress with sweetheart bust cups.', 'Vestido de satén negro suave con copas estilo corsé para veladas y eventos.', 2150.0, 'DOP', '/frontend/uploads/yahastyle/yaha_13.jpg', 1, 13), ('yaha_14', 'ccat_yaha_dresses', 'Blush Velvet Marble Choker Neck Midi Dress', 'Vestido Terciopelo Rosa Marmolado con Cuello Choker', 'Crushed velvet wrap midi dress with matching choker neck and high side slit.', 'Vestido de terciopelo marmolado con gargantilla a juego y abertura en la pierna.', 2350.0, 'DOP', '/frontend/uploads/yahastyle/yaha_14.jpg', 1, 14), ('yaha_15', 'ccat_yaha_casual', "Grey 'Faith' Cross Oversized Relaxed T-Shirt", "Camiseta Gris 'Faith' Estampada de Cruz", 'Soft cotton relaxed drop-shoulder graphic tee with calligraphic cross print.', "Camiseta de algodón suave estilo holgado con diseño de cruz 'Faith'.", 950.0, 'DOP', '/frontend/uploads/yahastyle/yaha_15.jpg', 1, 15), ('yaha_16', 'ccat_yaha_casual', 'Mustard Khaki Slim-Fit Cargo Joggers', 'Pantalón Cargo Jogger Mostaza con Bolsillos', 'Trendy high-waisted cargo pants with side flap utility pockets and elastic cuffs.', 'Pantalón cargo estilo jogger con bolsillos laterales y puños elásticos.', 1650.0, 'DOP', '/frontend/uploads/yahastyle/yaha_16.jpg', 1, 16), ('yaha_17', 'ccat_yaha_swim', 'Tropical Red & Black Leaves Halter Swimsuit', 'Traje de Baño Enterizo Hojas Rojas Tropicales', 'High-cut halter one-piece swimsuit with bold Caribbean botanical leaf print.', 'Traje de baño enterizo con cuello halter y estampado botánico tropical en rojo y negro.', 1650.0, 'DOP', '/frontend/uploads/yahastyle/yaha_17.jpg', 1, 1), ('yaha_18', 'ccat_yaha_swim', 'Classic Leopard Print High-Neck Monokini', 'Bañador Enterizo Estampado de Leopardo', 'Sleek halter animal-print one-piece with slimming high leg cut.', 'Traje de baño de animal print clásico con corte estilizado para la playa.', 1650.0, 'DOP', '/frontend/uploads/yahastyle/yaha_18.jpg', 1, 2), ('yaha_19', 'ccat_yaha_denim', 'Vintage Washed Khaki Skinny Jeans', 'Jeans Skinny Lavado Vintage Khaki', 'Comfort-stretch slim fit colored denim jeans with classic 5-pocket styling.', 'Pantalón jeans skinny en tono khaki envejecido con tela elástica cómoda.', 1850.0, 'DOP', '/frontend/uploads/yahastyle/yaha_19.jpg', 1, 3), ('yaha_20', 'ccat_yaha_denim', 'Classic Blue Wash High-Rise Skinny Jeans', 'Jeans Skinny Azul Clásico Tiro Alto', 'Flattering dark-washed body sculpting stretch jeans with double back pockets.', 'Jeans entallados azul clásico de tiro alto con efecto moldeador.', 1950.0, 'DOP', '/frontend/uploads/yahastyle/yaha_20.jpg', 1, 4), ('yaha_21', 'ccat_yaha_denim', 'White Distressed Ripped Straight Leg Jeans', 'Jeans Blancos Rasgados Estilo Urbano', 'Clean white denim jeans featuring trendy front slit distressing and raw edge hems.', 'Jeans blancos de corte recto moderno con roturas frontales a la moda.', 2100.0, 'DOP', '/frontend/uploads/yahastyle/yaha_21.jpg', 1, 5), ('yaha_22', 'ccat_yaha_denim', 'Acid Wash Grey Cropped Raw Hem Jeans', 'Jeans Grises Lavado Ácido con Bajo Deshilachado', 'Edgy grey wash high-waisted denim pants with trendy ankle crop and frayed edge.', 'Jeans grises lavado ácido de tiro alto con terminación rústica deshilachada.', 1950.0, 'DOP', '/frontend/uploads/yahastyle/yaha_22.jpg', 1, 6), ('yaha_23', 'ccat_yaha_denim', 'Distressed Washed Denim Mini Skirt', 'Minifalda Denim con Roturas y Desgaste', 'Classic casual denim mini skirt with front rips, whiskers, and raw fringe hem.', 'Minifalda vaquera de corte clásico con roturas frontales y flecos.', 1450.0, 'DOP', '/frontend/uploads/yahastyle/yaha_23.jpg', 1, 7), ('yaha_24', 'ccat_yaha_tops', 'Metallic Silver Glitter Crop Top & Belted Pant Set', 'Conjunto 2 Piezas Plateado Brillante con Cinturón', 'Showstopping metallic shimmer plunge bralette top paired with belted wide-leg trousers.', 'Conjunto brillante de fiesta de 2 piezas: top escotado y pantalón con hebilla dorada.', 2850.0, 'DOP', '/frontend/uploads/yahastyle/yaha_24.jpg', 1, 8), ('yaha_25', 'ccat_yaha_tops', 'Glitter Shimmer Halter Crop & Ruched Skirt Set', 'Conjunto Glitter Top Halter y Falda Drapeada', 'Two-piece night-out club set with halter crop top and side-ruched bodycon mini skirt.', 'Conjunto de fiesta de 2 piezas con top halter brillante y minifalda fruncida.', 2450.0, 'DOP', '/frontend/uploads/yahastyle/yaha_25.jpg', 1, 9), ('yaha_26', 'ccat_yaha_tops', "Studded Black Streetwear Tank ('Liquid 67')", "Camiseta sin Mangas Negra con Tachuelas '67'", 'Sleeveless edgy black drop tee with metallic shoulder studs and psychedelic drip number print.', 'Camiseta de tirantes negra estilo urbano con tachuelas plateadas y gráfico líquido 67.', 1250.0, 'DOP', '/frontend/uploads/yahastyle/yaha_26.jpg', 1, 10), ('yaha_27', 'ccat_yaha_tops', "Studded Royal Blue Racing Tank ('15')", "Camiseta Deportiva Azul Rey con Tachuelas '15'", 'Vibrant royal blue athletic tank top with studded neckline and racing graphics.', 'Camiseta azul rey estilo motorsport con tachuelas metálicas y número 15.', 1250.0, 'DOP', '/frontend/uploads/yahastyle/yaha_27.jpg', 1, 11), ('yaha_28', 'ccat_yaha_tops', 'Metallic Gold Crocodile Scale Crop Tank', 'Top Corto Dorado Efecto Escamas de Cocodrilo', 'Eye-catching high-neck metallic textured crop top in luxury gold finish.', 'Top brillante dorado con textura en relieve tipo escamas para ocasiones especiales.', 1350.0, 'DOP', '/frontend/uploads/yahastyle/yaha_28.jpg', 1, 12), ('yaha_29', 'ccat_yaha_tops', 'OXOX Floral Lips Graphic Crop T-Shirt', "Camiseta Crop 'OXOX' con Labios Florales", 'Cream soft cotton crewneck boxy crop tee with vibrant botanical floral kiss print.', 'Camiseta crop color crema con diseño estampado de labios florales estilo urbano.', 950.0, 'DOP', '/frontend/uploads/yahastyle/yaha_29.jpg', 1, 13), ('yaha_30', 'ccat_yaha_tops', 'Neon Yellow Asymmetric Shoulder Cutout Tank', 'Top Neón Amarillo con Escote Asimétrico', 'Electric neon yellow ribbed stretch tank top featuring modern double-strap shoulder cutout.', 'Top acanalado amarillo neón con tirante doble asimétrico para look llamativo.', 1150.0, 'DOP', '/frontend/uploads/yahastyle/yaha_30.jpg', 1, 14), ('yaha_31', 'ccat_yaha_tops', 'White Crewneck Tee with Silver Sequin Bow', 'Camiseta Blanca con Lazo Brillante de Lentejuelas', 'Classic premium white cotton short-sleeve tee adorned with a hand-stitched silver sequin bow.', 'Camiseta blanca clásica decorada con un hermoso lazo brillante de lentejuelas.', 1250.0, 'DOP', '/frontend/uploads/yahastyle/yaha_31.jpg', 1, 15), ('yaha_32', 'ccat_yaha_tops', 'Bronze Satin Asymmetric Wrap Tie Halter Top', 'Top de Satén Bronce con Lazos y Cuello Halter', 'Lustrous copper bronze satin wrap crop top with extended wrap-around tie ribbons.', 'Top brillante de satén color bronce con cuello halter y lazos largos ajustables.', 1450.0, 'DOP', '/frontend/uploads/yahastyle/yaha_32.jpg', 1, 16), ('yaha_33', 'ccat_yaha_swim', 'Neon Lime Underwire Push-Up Bikini Set', 'Bikini 2 Piezas Verde Neón con Soporte', 'Vibrant 2-piece neon lime swimsuit featuring supportive underwire cups and tie-side cheeky bottoms.', 'Bikini de dos piezas verde neón con copas armadas y lazos laterales ajustables.', 1850.0, 'DOP', '/frontend/uploads/yahastyle/yaha_33.jpg', 1, 3), ('yaha_34', 'ccat_yaha_swim', 'Classic Black Underwire Halter Monokini', 'Bañador Enterizo Negro con Copas y Escote Profundo', 'Sophisticated black one-piece swimsuit with sculpted bust cups and halter neck strap.', 'Elegante traje de baño enterizo negro con escote corazón y soporte de busto.', 1750.0, 'DOP', '/frontend/uploads/yahastyle/yaha_34.jpg', 1, 4), ('yaha_35', 'ccat_yaha_tops', "Burgundy 'Positive Life Attitude' Graphic Tee", "Camiseta Borgoña 'Positive Life Attitude'", 'Casual maroon soft-knit t-shirt with brushstroke inspirational typographic print.', 'Camiseta casual color vino con mensaje motivacional y corte clásico cómodo.', 950.0, 'DOP', '/frontend/uploads/yahastyle/yaha_35.jpg', 1, 17), ('yaha_36', 'ccat_yaha_tops', 'Royal Blue Front-Zip Ribbed Crop Tank', 'Top Corto Azul Rey con Cremallera y Argolla', 'Cobalt blue ribbed crop tank with full functional silver ring zipper down the front.', 'Top acanalado azul eléctrico con cremallera frontal decorativa y argolla plateada.', 1200.0, 'DOP', '/frontend/uploads/yahastyle/yaha_36.jpg', 1, 18), ('yaha_37', 'ccat_yaha_swim', 'Celestial Sun & Moon Mystic Print One-Piece', 'Traje de Baño Místico Estampado Sol y Luna', 'Artistic black and cream celestial astrology print swimsuit with athletic scoop neck.', 'Traje de baño enterizo con diseño celestial astrológico de sol, luna y constelaciones.', 1750.0, 'DOP', '/frontend/uploads/yahastyle/yaha_37.jpg', 1, 5), ('yaha_38', 'ccat_yaha_tops', 'Vanilla Cream Lettuce-Edge Ribbed Cami Top', 'Top de Tirantes Crema con Bordes Ondulados', 'Dainty ribbed knit sleeveless camisole with romantic ruffled lettuce-edge trims.', 'Top corto fresco color crema con textura acanalada y bordes ondulados.', 950.0, 'DOP', '/frontend/uploads/yahastyle/yaha_38.jpg', 1, 19), ('yaha_39', 'ccat_yaha_casual', "Acid Wash 'Faith Over Fear' Raw Cut Shorts", "Bermuda de Algodón Lavado Ácido 'Faith Over Fear'", 'Heavyweight mineral washed dark grey sweat shorts with drawstring and spiritual graphic.', 'Short bermuda estilo urbano gris lavado ácido con cordón ajustable y diseño impreso.', 1450.0, 'DOP', '/frontend/uploads/yahastyle/yaha_39.jpg', 1, 4), ('yaha_40', 'ccat_yaha_tops', 'Black Patent Crocodile Structured Corset Bustier', 'Corset Bustier Negro Efecto Piel de Cocodrilo', 'Glossy embossed croc-textured structured corset top with underwire cups and adjustable straps.', 'Top corset estructurado negro brillante textura cocodrilo para veladas y eventos.', 1950.0, 'DOP', '/frontend/uploads/yahastyle/yaha_40.jpg', 1, 20), ('yaha_41', 'ccat_yaha_tops', 'Mint Satin Backless Cowl Neck Handkerchief Top', 'Top Satinado Verde Menta con Espalda Descubierta', 'Silky pastel mint green draped cowl front top with open back criss-cross ties.', 'Top de satén verde menta con escote fluido y sensuales lazos cruzados en la espalda.', 1450.0, 'DOP', '/frontend/uploads/yahastyle/yaha_41.jpg', 1, 21), ('yaha_42', 'ccat_yaha_tops', 'Heather Grey Studded V-Neck Ribbed Tie-Back Tank', "Top Gris Claro con Tachuelas en 'V' y Lazo", 'Soft grey ribbed knit crop top with silver stud embellishments and waist tie bow.', 'Top acanalado gris con detalle de tachuelas plateadas en escote V y lazo decorativo.', 1350.0, 'DOP', '/frontend/uploads/yahastyle/yaha_42.jpg', 1, 22), ('yaha_43', 'ccat_yaha_tops', 'Ivory Ribbed Long-Sleeve Boatneck Crop Top', 'Top Manga Larga Blanco Marfil Cuello Barco', 'Minimalist long sleeve body-contour ribbed crop top with wide boat neckline.', 'Top blanco marfil de manga larga con escote barco elegante y tela elástica suave.', 1350.0, 'DOP', '/frontend/uploads/yahastyle/yaha_43.jpg', 1, 23)]
    for iid, icat, iname_en, iname_es, idesc_en, idesc_es, iprice, icurr, iimg, iavail, isort in boutique_items:
        cur.execute("""INSERT OR REPLACE INTO menu_items (id, business_id, category_id, name_en, name_es, description_en, description_es, price, currency, image_url, is_available, sort_order)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (iid, b_clothe, icat, iname_en, iname_es, idesc_en, idesc_es, iprice, icurr, iimg, iavail, isort))

    # Seed expanded size modifiers (including 2XL, 3XL Plus sizes with price deltas)
    boutique_mods = []
    for iid, icat, _, _, _, _, _, _, _, _, _ in boutique_items:
        is_denim = ('denim' in icat) or ('cargo' in iid)
        if is_denim:
            sizes = [
                ("Size 1 / 26 (XS)", "Talla 1 / 26 (XS)", 0.0),
                ("Size 3 / 28 (S)", "Talla 3 / 28 (S)", 0.0),
                ("Size 5 / 30 (M)", "Talla 5 / 30 (M)", 0.0),
                ("Size 7 / 32 (L)", "Talla 7 / 32 (L)", 0.0),
                ("Size 9 / 34 (XL)", "Talla 9 / 34 (XL)", 0.0),
                ("Size 11 / 36 (2XL Plus)", "Talla 11 / 36 (2XL Plus)", 150.0),
                ("Size 13 / 38 (3XL Plus)", "Talla 13 / 38 (3XL Plus)", 250.0),
            ]
        else:
            sizes = [
                ("Size S (Small)", "Talla S (Pequena)", 0.0),
                ("Size M (Medium)", "Talla M (Mediana)", 0.0),
                ("Size L (Large)", "Talla L (Grande)", 0.0),
                ("Size XL (Extra Large)", "Talla XL (Extra Grande)", 0.0),
                ("Size 2XL (Plus Size)", "Talla 2XL (Talla Plus)", 150.0),
                ("Size 3XL (Plus Size)", "Talla 3XL (Talla Plus)", 250.0),
            ]
        for idx, (s_en, s_es, pdelta) in enumerate(sizes):
            mid = f"mod_{iid}_{idx}"
            boutique_mods.append((mid, iid, 'Select Size', 'Seleccionar Talla', s_en, s_es, pdelta, 'DOP', 1, idx))

    for mid, miid, g_en, g_es, men, mes, pdelta, mcurr, mreq, msort in boutique_mods:
        cur.execute("""INSERT OR REPLACE INTO menu_modifiers (id, menu_item_id, group_name_en, group_name_es, name_en, name_es, price_delta, currency, is_required, sort_order)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (mid, miid, g_en, g_es, men, mes, pdelta, mcurr, mreq, msort))

    # -------------------------------------------------------------
    # Phase 2 Pilot Businesses (1 per target category across locations)
    # Includes Villa Montellano and Sosúa
    # -------------------------------------------------------------

    cur.execute("DELETE FROM businesses WHERE id = 'biz_montellano_massage'")

    pilot_businesses = [
        # 1b. Clara Light Spa (Claribel Batista Ferreira) - Puerto Plata (Mobile launch; studio conditional)
        {
            "id": "biz_clara_light_spa",
            "owner_email": "claralightspa@mavunqo.com",
            "owner_name": "Claribel Batista Ferreira",
            "trading_name": "Clara Light Spa",
            "legal_name": "Clara Light Spa",
            "slug": "clara-light-spa",
            "category_id": "cat_wellness_massage",
            "primary_location_id": "loc_puerto_plata",
            "description_en": "4x INFOTEP-certified massage therapist & aesthetician offering mobile home/villa spa, facials, nail care, and therapeutic massage across Puerto Plata, Montellano, and Sosúa.",
            "description_es": "Masajista terapéutica y esteticista certificada 4x por INFOTEP. Masajes a domicilio, faciales, manicure/pedicure y cuidado corporal en Puerto Plata, Montellano y Sosúa.",
            "has_physical_location": 0,
            "address": "Puerto Plata (Mobile / Home Visits)",
            "serves_entire_area": 1,
            "whatsapp": "+18299414894",
            "phone": "+18299584064",
            "public_email": "claralightspa@mavunqo.com",
            "logo_url": "/frontend/uploads/wellness/claribel_clara_spa.jpg",
            "cover_image_url": "/frontend/uploads/wellness/clara_light_spa_cover.jpg",
            "hours_json": json.dumps({"monday_saturday": "9:00 AM - 7:00 PM", "sunday": "Closed"}),
            "custom_commission_rate": 0.10,
            "requests_enabled": 1,
            "request_action_label_en": "Request an appointment",
            "request_action_label_es": "Solicitar una cita",
            "whatsapp_alerts_consent": 1,
            "whatsapp_alerts_phone": "+18299414894",
            "service_modes_supported": json.dumps(["mobile_visit"]),
            "storefront_pin_lat": None,
            "storefront_pin_lng": None,
            "pickup_pin_lat": None,
            "pickup_pin_lng": None,
            "pickup_pin_note": "Mobile / Home Visits only (Studio conditional)",
            "services": [
                ("srv_cls_1", "Express / Targeted Massage (30 min)", "Masaje Express / Localizado (30 min)", "Back, neck & shoulders mobile visit.", 1800.0, 1, "Visita a domicilio enfocada en espalda, cuello y hombros."),
                ("srv_cls_2", "Relaxation / Swedish Massage (60 min)", "Masaje Relajante / Sueco (60 min)", "Full-body relaxation at your home or villa.", 3000.0, 1, "Relajación de cuerpo completo en tu hogar o villa."),
                ("srv_cls_3", "Relaxation / Swedish Massage (90 min)", "Masaje Relajante / Sueco (90 min)", "Extended full-body relaxation session.", 4000.0, 1, "Sesión extendida de relajación corporal completa."),
                ("srv_cls_4", "Deep Tissue / Muscle-Release Massage (60 min)", "Masaje Descontracturante / Tejido Profundo (60 min)", "Targeted chronic tension and muscle relief.", 3500.0, 1, "Alivio focalizado de tensión crónica y nudos musculares."),
                ("srv_cls_5", "Sports / Muscle-Release Massage (90 min)", "Masaje Deportivo / Descontracturante (90 min)", "Extended deep muscle recovery session.", 4500.0, 1, "Sesión extendida de recuperación muscular profunda."),
                ("srv_cls_6", "Lymphatic Drainage (60 min)", "Drenaje Linfático (60 min)", "Gentle therapeutic lymphatic drainage.", 3400.0, 1, "Drenaje linfático terapéutico suave."),
                ("srv_cls_7", "Hot Stone Massage (60 min)", "Masaje con Piedras Calientes (60 min)", "Warm volcanic stone tension release.", 3800.0, 1, "Liberación de tensión con piedras volcánicas tibias."),
                ("srv_cls_8", "Couples Massage (60 min)", "Masaje en Pareja (60 min)", "Simultaneous two-therapist mobile session.", 5500.0, 1, "Sesión simultánea a domicilio con dos terapeutas."),
                ("srv_cls_9", "4-Hand Massage (60 min)", "Masaje a 4 Manos (60 min)", "Synchronized two-therapist luxury session.", 6000.0, 1, "Sesión de lujo sincronizada con dos terapeutas."),
                ("srv_cls_10", "Basic Facial", "Facial Básico", "Cleansing, exfoliation & hydration facial.", 3000.0, 1, "Limpieza facial, exfoliación e hidratación."),
                ("srv_cls_11", "Pedicure & Manicure", "Pedicure y Manicure", "Complete mobile hand and foot care.", 2000.0, 1, "Cuidado completo de manos y pies a domicilio."),
                ("srv_cls_12", "Hair Removal (Arms, Legs, Underarms)", "Depilación (Brazos, Piernas, Axilas)", "Price quoted by area and hair density.", 0.0, 0, "Precio cotizado según el área y densidad del vello."),
            ],
            "service_areas": ["loc_puerto_plata", "loc_montellano", "loc_sosua"]
        },
        # 1c. Nelfa López García (Therapeutic Massage & Physical Therapy) - Puerto Plata (Mobile-Only)
        {
            "id": "biz_nelfa_lopez",
            "owner_email": "nelfa@mavunqo.com",
            "owner_name": "Nelfa López García",
            "trading_name": "Nelfa López García — Masajes y Terapia Física",
            "legal_name": "Nelfa López García",
            "slug": "nelfa-lopez-terapia",
            "category_id": "cat_wellness_massage",
            "primary_location_id": "loc_puerto_plata",
            "description_en": "INFOTEP-certified massage therapist & physical therapist specializing in mobile therapeutic massage, sports recovery, and physical rehabilitation across Puerto Plata, Montellano, and Sosúa.",
            "description_es": "Masajista profesional y terapista físico certificada por INFOTEP. Especializada en masajes terapéuticos, recuperación deportiva y rehabilitación física a domicilio en Puerto Plata, Montellano y Sosúa.",
            "has_physical_location": 0,
            "address": "Puerto Plata (Mobile / Home Visits Only)",
            "serves_entire_area": 1,
            "whatsapp": "+18299414894",
            "phone": "+18495282828",
            "public_email": "nelfa@mavunqo.com",
            "logo_url": "/frontend/uploads/wellness/nelfa_lopez.jpg",
            "cover_image_url": "/frontend/uploads/wellness/nelfa_lopez.jpg",
            "hours_json": json.dumps({"daily": "8:00 AM - 4:00 PM"}),
            "custom_commission_rate": 0.10,
            "requests_enabled": 1,
            "request_action_label_en": "Request an appointment",
            "request_action_label_es": "Solicitar una cita",
            "whatsapp_alerts_consent": 1,
            "whatsapp_alerts_phone": "+18299414894",
            "service_modes_supported": json.dumps(["mobile_visit"]),
            "storefront_pin_lat": None,
            "storefront_pin_lng": None,
            "pickup_pin_lat": None,
            "pickup_pin_lng": None,
            "pickup_pin_note": "Mobile / Home Visits only (Studio conditional)",
            "services": [
                ("srv_nlg_1", "Express / Targeted Massage (30 min)", "Masaje Express / Localizado (30 min)", "Focused neck, back & shoulder relief at home.", 1800.0, 1),
                ("srv_nlg_2", "Relaxing / Swedish Massage (60 min)", "Masaje Relajante / Sueco (60 min)", "Full-body relaxing mobile massage.", 3000.0, 1),
                ("srv_nlg_3", "Relaxing / Swedish Massage (90 min)", "Masaje Relajante / Sueco (90 min)", "Extended full-body relaxing mobile session.", 4000.0, 1),
                ("srv_nlg_4", "Deep Tissue / Descontracturante (60 min)", "Masaje Descontracturante / Tejido Profundo (60 min)", "Deep muscle tension & knot release.", 3500.0, 1),
                ("srv_nlg_5", "Deep Tissue / Descontracturante (90 min)", "Masaje Descontracturante / Tejido Profundo (90 min)", "Extended deep tissue therapeutic session.", 4500.0, 1),
                ("srv_nlg_6", "Sports / Recovery Massage (60 min)", "Masaje Deportivo / Recuperación (60 min)", "Athletic muscle recovery & mobility.", 3500.0, 1),
                ("srv_nlg_7", "Lymphatic Drainage (60 min)", "Drenaje Linfático (60 min)", "Therapeutic lymphatic drainage session.", 3400.0, 1),
                ("srv_nlg_8", "Initial Assessment + Physical Therapy Session (60 min)", "Evaluación Inicial + Sesión de Terapia Física (60 min)", "Full evaluation and first mobile rehab session.", 3200.0, 1),
                ("srv_nlg_9", "Standard Physical Therapy / Rehab Session (45–60 min)", "Sesión Estándar de Terapia Física / Rehabilitación (45–60 min)", "Targeted physical therapy & mobility rehab.", 3000.0, 1),
                ("srv_nlg_10", "Extended Manual Therapy + Exercise (75–90 min)", "Terapia Manual Extendida + Ejercicios (75–90 min)", "Comprehensive manual therapy & guided rehab.", 4200.0, 1),
                ("srv_nlg_11", "Post-Op / Sports Injury Rehab (60 min)", "Rehabilitación Post-Operatoria / Lesiones Deportivas (60 min)", "Post-surgery and injury recovery protocol.", 3500.0, 1),
            ],
            "service_areas": ["loc_puerto_plata", "loc_montellano", "loc_sosua"]
        },
        # 2. Beauty & Personal Care (Activated) - Sosúa
        {
            "id": "biz_batey_barber",
            "owner_email": "danny@bateybarber.com",
            "owner_name": "Danny Rodriguez",
            "trading_name": "Batey Cuts Barber & Lounge",
            "legal_name": "Batey Barber Style SRL",
            "slug": "batey-cuts-barber",
            "category_id": "cat_beauty",
            "primary_location_id": "loc_sosua",
            "description_en": "Master fades, hot towel beard grooming, styling, and executive haircuts in central Sosúa.",
            "description_es": "Cortes clásicos y modernos, afeitado con toalla caliente y estilismo profesional en El Batey, Sosúa.",
            "has_physical_location": 1,
            "address": "Calle Dr. Rosen #12, El Batey, Sosúa",
            "serves_entire_area": 0,
            "whatsapp": "+18095553102",
            "phone": "+18095553102",
            "public_email": "info@bateybarber.com",
            "requests_enabled": 1,
            "request_action_label_en": "Request an appointment",
            "request_action_label_es": "Solicitar una cita",
            "whatsapp_alerts_consent": 1,
            "whatsapp_alerts_phone": "+18095553102",
            "service_modes_supported": json.dumps(["in_shop"]),
            "storefront_pin_lat": 19.7562,
            "storefront_pin_lng": -70.5142,
            "pickup_pin_lat": 19.7562,
            "pickup_pin_lng": -70.5142,
            "pickup_pin_note": "Ground floor glass door on Dr. Rosen next to cafe",
            "services": [
                ("srv_barb_1", "Signature Fade & Beard Sculpting", "Corte Fade y Perfilado de Barba", "Precision fade haircut with razor line and beard oil.", 700.0, 1),
                ("srv_barb_2", "Hot Towel Shave & Facial Scrub", "Afeitado con Toalla Caliente y Exfoliación", "Traditional barbershop hot towel shave.", 600.0, 1),
            ],
            "service_areas": ["loc_sosua"]
        },
        # 3. Tours & Activities (Activated: Pickup & Meeting Point) - Puerto Plata, Sosúa & Cabarete
        {
            "id": "biz_make_it_happen_tours",
            "owner_email": "bookings@makeithappentours.do",
            "owner_name": "Eddie Valerio",
            "trading_name": "Make It Happen Tours",
            "legal_name": "Make It Happen Tours",
            "slug": "make-it-happen-tours",
            "category_id": "cat_tours",
            "primary_location_id": "loc_puerto_plata",
            "description_en": "City tours & adventures across Puerto Plata, Sosúa, and Cabarete—27 Waterfalls, ATV & Buggy trails, Horse Riding, Party Boat, Paradise Island, Deep Sea Fishing, Snorkeling, and rentals. Operator pickup included.",
            "description_es": "Tours y aventuras en Puerto Plata, Sosúa y Cabarete—27 Charcos de Damajagua, ATV y Buggy, Cabalgata, Party Boat, Cayo Arena, Pesca en Alta Mar, Snorkel y alquileres. Transporte/recogida incluido.",
            "has_physical_location": 0,
            "address": "Puerto Plata • Sosúa • Cabarete (Operator Pickup Included)",
            "serves_entire_area": 1,
            "whatsapp": "+18495550000",
            "phone": "+18495550000",
            "public_email": "bookings@makeithappentours.do",
            "requests_enabled": 1,
            "request_action_label_en": "Request a tour booking",
            "request_action_label_es": "Solicitar reserva de tour",
            "whatsapp_alerts_consent": 1,
            "whatsapp_alerts_phone": "+18495550000",
            "service_modes_supported": json.dumps(["meeting_point", "mobile_visit"]),
            "storefront_pin_lat": 19.7934,
            "storefront_pin_lng": -70.6884,
            "pickup_pin_lat": 19.7934,
            "pickup_pin_lng": -70.6884,
            "pickup_pin_note": "Operator pickup from Puerto Plata, Sosúa & Cabarete (or designated highway meeting point)",
            "services": [
                ("srv_mih_city", "Puerto Plata City Tour ($60 USD)", "City Tour Puerto Plata ($60 USD)", "Fort San Felipe, Cable Car, local market & culture.", 3600.0, 1),
                ("srv_mih_waterfalls", "27 Waterfalls Damajagua ($80 USD)", "27 Charcos de Damajagua ($80 USD)", "Natural waterfall slides & pools, gear included.", 4800.0, 1),
                ("srv_mih_fishing", "Deep Sea Fishing ($120 USD)", "Pesca en Alta Mar ($120 USD)", "Shared 50ft fishing boat (Max 9 passengers + crew). Beers, sandwiches & equipment included.", 7200.0, 1),
                ("srv_mih_horse", "Horse Riding ($80 USD)", "Paseo a Caballo ($80 USD)", "Scenic beach ride suitable for all skill levels.", 4800.0, 1),
                ("srv_mih_buggy", "Buggy Adventure ($80 USD)", "Aventura en Buggy ($80 USD)", "Off-road countryside & trail adventure.", 4800.0, 1),
                ("srv_mih_lagoon", "Blue Lagoon ($80 USD)", "Laguna Azul ($80 USD)", "Crystal-clear natural pool & relaxation.", 4800.0, 1),
                ("srv_mih_atv", "ATV Tour ($75 USD)", "Tour en ATV / Four Wheels ($75 USD)", "Coastal & jungle trails guided experience.", 4500.0, 1),
                ("srv_mih_paradise", "Paradise Island Punta Rucia ($85 USD)", "Cayo Arena Punta Rucia ($85 USD)", "White sandbar, boat ride & lobster lunch included.", 5100.0, 1),
                ("srv_mih_partyboat", "Party Boat ($100 USD)", "Party Boat ($100 USD)", "60ft double-decker catamaran (Max 50 passengers). Food, drinks & snorkel stop included.", 6000.0, 1),
                ("srv_mih_private_party_boat", "Private Party Boat ($800 USD)", "Party Boat Privado ($800 USD)", "Private 60ft double-decker catamaran (Max 50 passengers). Food, drinks & snorkel stop included.", 48000.0, 1),
                ("srv_mih_charter", "Private Fishing Charter ($750 USD)", "Charter Privado de Pesca ($750 USD)", "Private 50ft fishing boat (Max 9 passengers + crew). Beers, sandwiches & all equipment included.", 45000.0, 1),
                ("srv_mih_snorkel", "Snorkeling Tour ($50 USD)", "Tour de Snorkel ($50 USD)", "Coral reef snorkeling with gear included.", 3000.0, 1),
                ("srv_mih_car", "Car Rental 24 Hours — Eddie Direct ($50 USD)", "Alquiler de Carro 24 Horas — Eddie Direct ($50 USD)", "General car rental (Eddie Direct ad — call Eddie directly for availability & pickup details).", 3000.0, 1),
                ("srv_mih_scooter", "Scooter Rental 24 Hours — Eddie Direct ($25 USD)", "Alquiler de Pasola 24 Horas — Eddie Direct ($25 USD)", "General scooter rental (Eddie Direct ad — call Eddie directly for availability & pickup details).", 1500.0, 1),
            ],
            "service_areas": ["loc_puerto_plata", "loc_sosua", "loc_cabarete"]
        },
        # 4. Transportation & Rentals (Activated) - Sosúa
        {
            "id": "biz_caribbean_ride_rentals",
            "owner_email": "rentals@caribbeanridesosua.com",
            "owner_name": "Eduardo Morales",
            "trading_name": "Caribbean Rides Scooter & Car Rental",
            "legal_name": "Carib Rides SRL",
            "slug": "caribbean-rides-rentals",
            "category_id": "cat_transport",
            "primary_location_id": "loc_sosua",
            "description_en": "Reliable 150cc scooter rentals, compact SUV rentals, and private airport transfers to Puerto Plata POP & Santiago STI.",
            "description_es": "Alquiler de pasolas y motonetas 150cc, vehículos compactos y traslados privados a los aeropuertos POP y STI.",
            "has_physical_location": 1,
            "address": "Calle Alejo Martínez #8, El Batey, Sosúa",
            "serves_entire_area": 1,
            "whatsapp": "+18095553104",
            "phone": "+18095553104",
            "public_email": "res@caribbeanridesosua.com",
            "requests_enabled": 1,
            "request_action_label_en": "Request a ride or rental",
            "request_action_label_es": "Solicitar un vehículo o traslado",
            "whatsapp_alerts_consent": 1,
            "whatsapp_alerts_phone": "+18095553104",
            "service_modes_supported": json.dumps(["in_shop", "mobile_visit"]),
            "storefront_pin_lat": 19.7548,
            "storefront_pin_lng": -70.5122,
            "pickup_pin_lat": 19.7548,
            "pickup_pin_lng": -70.5122,
            "pickup_pin_note": "Rental Lot Gate, Calle Alejo Martínez opposite Supermercado",
            "services": [
                ("srv_ren_1", "150cc Automatic Scooter Rental (24 Hours)", "Alquiler de Pasola 150cc (24 Horas)", "Helmet and lock included.", 1500.0, 1),
                ("srv_ren_2", "Private Airport Transfer POP -> Sosúa", "Traslado Privado Aeropuerto POP a Sosúa", "A/C van with luggage space.", 1800.0, 1),
            ],
            "service_areas": ["loc_sosua", "loc_cabarete", "loc_montellano"]
        },
        # 5. Home & Property Services (Activated) - Sosúa
        {
            "id": "biz_sosua_crystal_clean",
            "owner_email": "clean@sosuacrystalclean.com",
            "owner_name": "Yolanda Castillo",
            "trading_name": "Sosúa Crystal Clean Services",
            "legal_name": "Servicios de Limpieza Crystal SRL",
            "slug": "sosua-crystal-clean",
            "category_id": "cat_home",
            "primary_location_id": "loc_sosua",
            "description_en": "Professional residential villa deep cleaning, condo changeover service, and laundry wash & fold pickup in Sosúa.",
            "description_es": "Limpieza profunda de villas residenciales, preparación de apartamentos y lavandería con entrega a domicilio.",
            "has_physical_location": 1,
            "address": "Calle David Stern #5, Sosúa",
            "serves_entire_area": 1,
            "whatsapp": "+18095553105",
            "phone": "+18095553105",
            "public_email": "dispatch@sosuacrystalclean.com",
            "requests_enabled": 1,
            "request_action_label_en": "Request a service or quote",
            "request_action_label_es": "Solicitar un servicio o cotización",
            "whatsapp_alerts_consent": 1,
            "whatsapp_alerts_phone": "+18095553105",
            "service_modes_supported": json.dumps(["mobile_visit"]),
            "storefront_pin_lat": 19.7531,
            "storefront_pin_lng": -70.5115,
            "pickup_pin_lat": 19.7531,
            "pickup_pin_lng": -70.5115,
            "pickup_pin_note": "Operations Depot, Calle David Stern #5",
            "services": [
                ("srv_cln_1", "2-Bedroom Condo Turnover Deep Clean", "Limpieza Profunda Apartamento 2 Habitaciones", "Full sanitize, linens changed, windows and floors.", 2500.0, 1),
                ("srv_cln_2", "Villa Pool & Patio Power Wash", "Lavado a Presión de Terraza y Piscina", "High pressure wash removing algae and salt build-up.", 3200.0, 1),
            ],
            "service_areas": ["loc_sosua", "loc_cabarete"]
        },
        # 6. Events & Catering (Activated) - Sosúa & Montellano
        {
            "id": "biz_palma_real_events",
            "owner_email": "events@palmarealdominicana.com",
            "owner_name": "Gabriel Mendez",
            "trading_name": "Palma Real Events & DJ Sound",
            "legal_name": "Eventos Palma Real SRL",
            "slug": "palma-real-events-dj",
            "category_id": "cat_events",
            "primary_location_id": "loc_sosua",
            "description_en": "Custom party sound systems, bilingual DJs, ambient beach lighting, and Creole BBQ catering for private villas and celebrations.",
            "description_es": "Sonido profesional para fiestas, DJs bilingües, iluminación ambiental y catering parrillada para villas privadas.",
            "has_physical_location": 0,
            "address": "Sosúa Events Warehouse, Carretera Sosúa",
            "serves_entire_area": 1,
            "whatsapp": "+18095553106",
            "phone": "+18095553106",
            "public_email": "booking@palmarealdominicana.com",
            "requests_enabled": 1,
            "request_action_label_en": "Request a quote or date",
            "request_action_label_es": "Solicitar cotización o fecha",
            "whatsapp_alerts_consent": 1,
            "whatsapp_alerts_phone": "+18095553106",
            "service_modes_supported": json.dumps(["mobile_visit"]),
            "storefront_pin_lat": 19.7495,
            "storefront_pin_lng": -70.5190,
            "pickup_pin_lat": 19.7495,
            "pickup_pin_lng": -70.5190,
            "pickup_pin_note": "Audio Warehouse Loading Bay, Carretera Principal",
            "services": [
                ("srv_eve_1", "Private Villa Party Sound & DJ Package (4 Hours)", "Paquete de Sonido y DJ para Villa (4 Horas)", "Speakers, subwoofers, party lighting and DJ controller.", 12000.0, 1),
                ("srv_eve_2", "Beach Wedding Acoustic Setup", "Sistema Acústico para Ceremonia en Playa", "Wireless mics, battery sound and background ambiance.", 7500.0, 1),
            ],
            "service_areas": ["loc_sosua", "loc_montellano", "loc_cabarete"]
        },
        # 7. Menu-Free Restaurant (Activated: Request an order with missing price & 15-min timer) - Sosúa
        {
            "id": "biz_taqueria_del_sol",
            "owner_email": "tacos@taqueriadelsolsosua.com",
            "owner_name": "Mateo Gutierrez",
            "trading_name": "Taqueria Del Sol Sosua",
            "legal_name": "Comidas del Sol EIRL",
            "slug": "taqueria-del-sol-sosua",
            "category_id": "cat_dining",
            "primary_location_id": "loc_sosua",
            "description_en": "Authentic street tacos, burritos, quesadillas, and homemade chips & guacamole with fast counter pickup in El Batey.",
            "description_es": "Auténticos tacos al pastor, burritos estilo callejero y quesadillas recién hechas en El Batey.",
            "has_physical_location": 1,
            "address": "Calle Ayuntamiento #22, Sosúa",
            "serves_entire_area": 1,
            "whatsapp": "+18095553107",
            "phone": "+18095553107",
            "public_email": "ordenes@taqueriadelsolsosua.com",
            "requests_enabled": 1,
            "request_action_label_en": "Request an order",
            "request_action_label_es": "Solicitar un pedido",
            "whatsapp_alerts_consent": 0, # Merchant without WhatsApp consent to test acceptance requirement!
            "whatsapp_alerts_phone": "+18095553107",
            "service_modes_supported": json.dumps(["pickup", "delivery"]),
            "storefront_pin_lat": 19.7570,
            "storefront_pin_lng": -70.5135,
            "pickup_pin_lat": 19.7570,
            "pickup_pin_lng": -70.5135,
            "pickup_pin_note": "Taco window on Calle Ayuntamiento #22",
            "services": [], # Menu-free restaurant! No catalog items.
            "service_areas": ["loc_sosua"]
        },
        # 8. Unactivated Listing (requests_enabled = 0: tests 'Register Interest') - Villa Montellano
        {
            "id": "biz_montellano_hardware",
            "owner_email": "luis@ferreteriamontellano.com",
            "owner_name": "Luis Alberto Santos",
            "trading_name": "Ferretería El Cañero Montellano",
            "legal_name": "Ferretería El Cañero SRL",
            "slug": "ferreteria-el-canero-montellano",
            "category_id": "cat_home",
            "primary_location_id": "loc_montellano",
            "description_en": "Building supplies, tools, electrical wiring, plumbing, and cement delivery in Villa Montellano.",
            "description_es": "Materiales de construcción, herramientas, electricidad, plomería y ferretería general en Villa Montellano.",
            "has_physical_location": 1,
            "address": "Avenida 27 de Febrero #15, Villa Montellano",
            "serves_entire_area": 1,
            "whatsapp": "+18095553108",
            "phone": "+18095553108",
            "public_email": "ventas@ferreteriamontellano.com",
            "requests_enabled": 0, # Unactivated listing! Shows Register Interest
            "request_action_label_en": "Request a quote",
            "request_action_label_es": "Solicitar una cotización",
            "whatsapp_alerts_consent": 0,
            "whatsapp_alerts_phone": None,
            "service_modes_supported": json.dumps(["in_shop"]),
            "storefront_pin_lat": 19.7435,
            "storefront_pin_lng": -70.5970,
            "pickup_pin_lat": 19.7435,
            "pickup_pin_lng": -70.5970,
            "pickup_pin_note": "Loading dock on Av. 27 de Febrero",
            "services": [
                ("srv_fer_1", "Bulk Bagged Cement (Portland 42.5kg)", "Funda de Cemento Gris 42.5kg", "Standard construction cement.", 485.0, 1),
            ],
            "service_areas": ["loc_montellano"]
        },
        # 10. Veterinary & Pet Care (AmigoVet Storefront on Mavunqo)
        {
            "id": "biz_klinickey_vet",
            "owner_email": "vet@amigovet.do",
            "owner_name": "AmigoVet Veterinary Network",
            "trading_name": "AmigoVet",
            "legal_name": "AmigoVet RD",
            "slug": "amigovet",
            "category_id": "cat_veterinary",
            "primary_location_id": "loc_sosua",
            "description_en": "Bilingual veterinary care, video tele-triage, mobile home vet visits, vaccinations, and clinic checkups across Sosúa, Cabarete, and Puerto Plata.",
            "description_es": "Atención veterinaria bilingüe, tele-triaje por video, visitas veterinarias a domicilio, vacunas y consultas clínicas en Sosúa, Cabarete y Puerto Plata.",
            "has_physical_location": 0,
            "address": "Sosúa, Cabarete & Puerto Plata (Mobile & Tele-Triage)",
            "serves_entire_area": 1,
            "whatsapp": "+18299414894",
            "phone": "+18299414894",
            "public_email": "vet@amigovet.do",
            "logo_url": "/frontend/uploads/amigovet_logo.jpg",
            "cover_image_url": "/frontend/uploads/amigovet_logo.jpg",
            "requests_enabled": 1,
            "request_action_label_en": "Book Vet Visit / Tele-Triage",
            "request_action_label_es": "Solicitar Consulta Veterinaria",
            "whatsapp_alerts_consent": 1,
            "whatsapp_alerts_phone": "+18299414894",
            "service_modes_supported": json.dumps(["in_shop", "mobile_visit"]),
            "storefront_pin_lat": 19.7540,
            "storefront_pin_lng": -70.5140,
            "pickup_pin_lat": 19.7540,
            "pickup_pin_lng": -70.5140,
            "pickup_pin_note": "Mobile Vet Dispatch & Clinic Network — Sosúa / Puerto Plata",
            "services": [
                ("srv_vet_1", "24/7 Live Video Vet Tele-Triage", "Tele-Triaje Veterinario por Video 24/7", "Immediate video evaluation for pet symptoms & urgent care.", 1200.0, 1),
                ("srv_vet_2", "Mobile Home / Villa Vet Visit", "Visita Veterinaria a Domicilio", "Licensed vet travels to your home or villa for exam & treatment.", 2800.0, 2),
                ("srv_vet_3", "Pet Wellness Exam & Vaccinations", "Consulta General y Vacunación", "Routine checkup, deworming, and core vaccines.", 1800.0, 3),
            ],
            "service_areas": ["loc_sosua", "loc_montellano", "loc_puerto_plata"]
        },

        # 11. Legal & Lawyers Directory (Consultation-Only Verified Profiles)
        {
            "id": "biz_legal_puerto_plata",
            "owner_email": "consultas@nortecosterolegal.do",
            "owner_name": "Lic. Rafael Mendoza & Asociados",
            "trading_name": "Norte Costero Legal & Title",
            "legal_name": "Norte Costero Legal & Title Advisors SRL",
            "slug": "norte-costero-legal",
            "category_id": "cat_legal",
            "primary_location_id": "loc_puerto_plata",
            "description_en": "Bilingual Dominican attorneys (CARD Bar Verified). Real estate title & deslinde due diligence, SRL company formation, commercial contracts, and notary services. Consultation-only directory listing; all legal retainers occur directly with the firm.",
            "description_es": "Abogados bilingües dominicanos (Colegio de Abogados verificado). Debida diligencia de títulos y deslindes, formación de SRL, contratos comerciales y notaría. Directorio solo de consultas; acuerdos legales directamente con la firma.",
            "has_physical_location": 1,
            "address": "Calle Beller #42, Centro Histórico, Puerto Plata",
            "serves_entire_area": 1,
            "whatsapp": "+18095550191",
            "phone": "+18095550191",
            "public_email": "consultas@nortecosterolegal.do",
            "logo_url": None,
            "cover_image_url": None,
            "requests_enabled": 1,
            "request_action_label_en": "Book Legal Consultation",
            "request_action_label_es": "Solicitar Consulta Legal",
            "whatsapp_alerts_consent": 1,
            "whatsapp_alerts_phone": "+18095550191",
            "service_modes_supported": json.dumps(["in_shop", "tele_consultation"]),
            "storefront_pin_lat": 19.7960,
            "storefront_pin_lng": -70.6915,
            "pickup_pin_lat": 19.7960,
            "pickup_pin_lng": -70.6915,
            "pickup_pin_note": "Puerto Plata Office & Video Consultation",
            "services": [
                ("srv_leg_pp_1", "Initial Legal Consultation (30 Min)", "Consulta Legal Inicial (30 Min)", "Bilingual case review in person or by video.", 3500.0, 1),
                ("srv_leg_pp_2", "Real Estate Title & Deslinde Check", "Revisión de Título y Deslinde", "Property title & lien verification before closing.", 12000.0, 2),
                ("srv_leg_pp_3", "SRL Company Formation Consultation", "Consulta Formación de SRL", "Entity structure, RNC registration & bylaws roadmap.", 6500.0, 3),
                ("srv_leg_pp_4", "Contract & Notary Review", "Revisión de Contratos y Notaría", "Lease, vendor, or partnership agreement review.", 4500.0, 4),
            ],
            "service_areas": ["loc_puerto_plata", "loc_sosua", "loc_cabarete"]
        },
        {
            "id": "biz_legal_sosua",
            "owner_email": "info@sosuaexpatlaw.do",
            "owner_name": "Lic. Carmen Valerio",
            "trading_name": "Sosúa Expat & Residency Law",
            "legal_name": "Sosúa Expat & Residency Law Group",
            "slug": "sosua-expat-law",
            "category_id": "cat_legal",
            "primary_location_id": "loc_sosua",
            "description_en": "Dedicated expat & immigration counsel in Sosúa (English/Spanish). Dominican residency permits, investor visas, wills & estate planning, and HOA/rental dispute guidance. Direct attorney-client engagement only.",
            "description_es": "Asesoría legal para expatriados e inmigración en Sosúa (Inglés/Español). Residencias dominicanas, visas de inversión, testamentos y conflictos de condominio. Contratación directa con la firma.",
            "has_physical_location": 1,
            "address": "Plaza El Batey, Suite 204, Sosúa",
            "serves_entire_area": 1,
            "whatsapp": "+18095550192",
            "phone": "+18095550192",
            "public_email": "info@sosuaexpatlaw.do",
            "logo_url": None,
            "cover_image_url": None,
            "requests_enabled": 1,
            "request_action_label_en": "Book Legal Consultation",
            "request_action_label_es": "Solicitar Consulta Legal",
            "whatsapp_alerts_consent": 1,
            "whatsapp_alerts_phone": "+18095550192",
            "service_modes_supported": json.dumps(["in_shop", "tele_consultation"]),
            "storefront_pin_lat": 19.7545,
            "storefront_pin_lng": -70.5175,
            "pickup_pin_lat": 19.7545,
            "pickup_pin_lng": -70.5175,
            "pickup_pin_note": "El Batey Office & Video Consultation — Sosúa",
            "services": [
                ("srv_leg_sos_1", "15-Min Intro & Case Fit Call", "Llamada Introductoria (15 Min)", "Quick scope check for residency or expat legal needs.", 0.0, 1),
                ("srv_leg_sos_2", "Dominican Residency Roadmap Session", "Sesión de Residencia Dominicana", "Document checklist & timeline for temporary/permanent residency.", 4000.0, 2),
                ("srv_leg_sos_3", "Expat Will & Estate Consultation", "Consulta de Testamento y Herencia", "Cross-border asset protection & Dominican succession planning.", 5500.0, 3),
            ],
            "service_areas": ["loc_sosua", "loc_cabarete", "loc_puerto_plata"]
        },
        {
            "id": "biz_legal_cabarete",
            "owner_email": "counsel@cabaretehospitalitylaw.do",
            "owner_name": "Lic. Andrés Peña",
            "trading_name": "Cabarete Hospitality & Business Law",
            "legal_name": "Cabarete Business & Hospitality Counsel",
            "slug": "cabarete-hospitality-law",
            "category_id": "cat_legal",
            "primary_location_id": "loc_cabarete",
            "description_en": "Tourism, villa, and hospitality legal counsel in Cabarete. Vendor liability agreements, DR Labor Code compliance, municipal permits, and terms-of-service structuring. Direct consultation booking only.",
            "description_es": "Asesoría legal para turismo, villas y hospitalidad en Cabarete. Contratos con proveedores, cumplimiento del Código de Trabajo, permisos municipales y términos de servicio.",
            "has_physical_location": 1,
            "address": "Carretera Principal Km 1, Plaza Oceanía, Cabarete",
            "serves_entire_area": 1,
            "whatsapp": "+18095550193",
            "phone": "+18095550193",
            "public_email": "counsel@cabaretehospitalitylaw.do",
            "logo_url": None,
            "cover_image_url": None,
            "requests_enabled": 1,
            "request_action_label_en": "Book Legal Consultation",
            "request_action_label_es": "Solicitar Consulta Legal",
            "whatsapp_alerts_consent": 1,
            "whatsapp_alerts_phone": "+18095550193",
            "service_modes_supported": json.dumps(["in_shop", "tele_consultation"]),
            "storefront_pin_lat": 19.7495,
            "storefront_pin_lng": -70.4090,
            "pickup_pin_lat": 19.7495,
            "pickup_pin_lng": -70.4090,
            "pickup_pin_note": "Cabarete Office & Video Consultation",
            "services": [
                ("srv_leg_cab_1", "Hospitality & Vendor Agreement Consult", "Consulta Contratos de Proveedores", "Structuring independent contractor & liability waivers.", 4500.0, 1),
                ("srv_leg_cab_2", "DR Labor & Staffing Compliance Review", "Revisión Laboral y Nómina RD", "TSS, contracts, and hospitality staffing compliance.", 4000.0, 2),
                ("srv_leg_cab_3", "Platform Terms & Liability Isolation", "Términos de Plataforma y Responsabilidad", "Ad-only directory disclaimers & DR Law 358-05 alignment.", 6000.0, 3),
            ],
            "service_areas": ["loc_cabarete", "loc_sosua", "loc_puerto_plata"]
        }
    ]

    for p in pilot_businesses:
        # 1. Owner User
        default_owner_id = f"user_{p['id']}"
        cur.execute("SELECT id FROM users WHERE id = ? OR email = ?", (default_owner_id, p["owner_email"]))
        user_row = cur.fetchone()
        owner_id = user_row[0] if user_row else default_owner_id
        if not user_row:
            cur.execute(
                """INSERT INTO users (id, email, password_hash, full_name, role)
                   VALUES (?, ?, ?, ?, 'owner')""",
                (owner_id, p["owner_email"], hash_password("PilotPass2026!"), p["owner_name"])
            )
        else:
            cur.execute(
                "UPDATE users SET email = ?, full_name = ? WHERE id = ?",
                (p["owner_email"], p["owner_name"], owner_id)
            )

        # 2. Business
        cur.execute("SELECT id FROM businesses WHERE id = ? OR slug = ?", (p["id"], p["slug"]))
        b_row = cur.fetchone()
        if not b_row:
            cur.execute(
                """INSERT INTO businesses (
                    id, owner_id, trading_name, legal_name, slug, category_id, primary_location_id,
                    description_en, description_es, status, has_physical_location, address,
                    serves_entire_area, website_url, whatsapp, phone, public_email,
                    hours_json, rnc_tax_id, rnc_status, approved_by, approved_at,
                    requests_enabled, request_action_label_en, request_action_label_es,
                    whatsapp_alerts_consent, whatsapp_alerts_phone, service_modes_supported,
                    storefront_pin_lat, storefront_pin_lng, pickup_pin_lat, pickup_pin_lng, pickup_pin_note,
                    pilot_delivery_enabled, logo_url, cover_image_url
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'approved', ?, ?, ?, NULL, ?, ?, ?, ?, NULL, 'verified', ?, CURRENT_TIMESTAMP, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    p["id"], owner_id, p["trading_name"], p["legal_name"], p["slug"], p["category_id"], p["primary_location_id"],
                    p["description_en"], p["description_es"], p["has_physical_location"], p["address"],
                    p["serves_entire_area"], p["whatsapp"], p["phone"], p["public_email"],
                    p.get("hours_json") or json.dumps({"monday_saturday": "8:30 AM - 6:00 PM"}), admin_id,
                    p["requests_enabled"], p["request_action_label_en"], p["request_action_label_es"],
                    p["whatsapp_alerts_consent"], p["whatsapp_alerts_phone"], p["service_modes_supported"],
                    p["storefront_pin_lat"], p["storefront_pin_lng"], p["pickup_pin_lat"], p["pickup_pin_lng"], p["pickup_pin_note"],
                    1 if p["id"] == "biz_taqueria_del_sol" else 0,
                    p.get("logo_url"), p.get("cover_image_url")
                )
            )
        else:
            cur.execute(
                """UPDATE businesses SET 
                    trading_name = ?, legal_name = ?, slug = ?,
                    description_en = ?, description_es = ?, public_email = ?,
                    requests_enabled = ?, request_action_label_en = ?, request_action_label_es = ?,
                    whatsapp_alerts_consent = ?, whatsapp_alerts_phone = ?, service_modes_supported = ?,
                    storefront_pin_lat = ?, storefront_pin_lng = ?, pickup_pin_lat = ?, pickup_pin_lng = ?, pickup_pin_note = ?,
                    logo_url = COALESCE(?, logo_url), cover_image_url = COALESCE(?, cover_image_url)
                   WHERE id = ?""",
                (
                    p["trading_name"], p["legal_name"], p["slug"],
                    p["description_en"], p["description_es"], p.get("public_email"),
                    p["requests_enabled"], p["request_action_label_en"], p["request_action_label_es"],
                    p["whatsapp_alerts_consent"], p["whatsapp_alerts_phone"], p["service_modes_supported"],
                    p["storefront_pin_lat"], p["storefront_pin_lng"], p["pickup_pin_lat"], p["pickup_pin_lng"], p["pickup_pin_note"],
                    p.get("logo_url"), p.get("cover_image_url"),
                    p["id"]
                )
            )

        # 3. Service areas
        for loc_id in p.get("service_areas", []):
            cur.execute("INSERT OR IGNORE INTO business_service_areas (business_id, location_id) VALUES (?, ?)", (p["id"], loc_id))

        # 4. Services
        for s_item in p.get("services", []):
            desc_es = s_item[6] if len(s_item) > 6 else s_item[3]
            cur.execute("SELECT id FROM services WHERE id = ?", (s_item[0],))
            if not cur.fetchone():
                cur.execute(
                    """INSERT INTO services (id, business_id, name_en, name_es, description_en, description_es, price, currency, display_price, sort_order)
                       VALUES (?, ?, ?, ?, ?, ?, ?, 'DOP', 1, ?)""",
                    (s_item[0], p["id"], s_item[1], s_item[2], s_item[3], desc_es, s_item[4], s_item[5])
                )
            else:
                cur.execute(
                    """UPDATE services
                       SET name_en = ?, name_es = ?, description_en = ?, description_es = ?
                       WHERE id = ?""",
                    (s_item[1], s_item[2], s_item[3], desc_es, s_item[0])
                )

    # Seed Initial Motorcycle Drivers & Delivery Capacity in Sosúa
    # -------------------------------------------------------------
    cur.execute("SELECT location_id FROM delivery_capacity_settings WHERE location_id = 'loc_sosua'")
    if not cur.fetchone():
        cur.execute(
            """INSERT INTO delivery_capacity_settings (location_id, is_delivery_paused, pause_reason, max_orders_per_driver)
               VALUES ('loc_sosua', 0, NULL, 2)"""
        )

    drivers_data = [
        ("drv_sosua_1", "Rafael Santana", "+18095554411", "motorcycle", "online", 2, "loc_sosua"),
        ("drv_sosua_2", "Miguel Angel Batista", "+18095554422", "motorcycle", "online", 2, "loc_sosua"),
    ]
    for did, dname, dphone, dtype, dstatus, dcap, dloc in drivers_data:
        cur.execute("SELECT id FROM drivers WHERE id = ?", (did,))
        if not cur.fetchone():
            cur.execute(
                """INSERT INTO drivers (id, full_name, phone, vehicle_type, status, max_concurrent_orders, location_id)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (did, dname, dphone, dtype, dstatus, dcap, dloc)
            )

    # Seed Monthly SaaS Plans (Free Basic + 90-Day Trial Pro Tiers)
    # -------------------------------------------------------------
    saas_plans_data = [
        (
            "plan_free",
            "free_basic",
            "Free Basic Listing",
            "Listado Básico Gratis",
            0.0,
            0.0,
            0.10,
            json.dumps({
                "trial_days": 0,
                "highlights_en": ["Directory listing", "WhatsApp intake", "10% per completed order/booking"],
                "highlights_es": ["Presencia en el directorio", "Recepción por WhatsApp", "10% por pedido o reserva completada"]
            }),
            1,
            1
        ),
        (
            "plan_ordering_pro",
            "ordering_booking_pro",
            "Ordering & Booking Pro (90-Day Free Trial)",
            "Pedidos y Reservas Pro (90 Días Gratis)",
            19.0,
            1150.0,
            0.05,
            json.dumps({
                "trial_days": 90,
                "highlights_en": ["90-day free trial", "Reduced 5% commission", "Unlimited menu/service updates & WhatsApp alerts"],
                "highlights_es": ["90 días de prueba gratis", "Comisión reducida al 5%", "Actualizaciones ilimitadas y alertas por WhatsApp"]
            }),
            1,
            2
        ),
        (
            "plan_featured",
            "featured_boost",
            "Featured Discovery Boost",
            "Impulso Destacado en Búsqueda",
            29.0,
            1750.0,
            0.05,
            json.dumps({
                "trial_days": 90,
                "highlights_en": ["90-day free trial", "Top placement in category & AI Concierge", "5% commission + analytics"],
                "highlights_es": ["90 días de prueba gratis", "Posición destacada en categoría y Concierge IA", "5% de comisión + analíticas"]
            }),
            1,
            3
        ),
        (
            "plan_clinic_multi",
            "multi_staff_clinic",
            "Multi-Staff Clinic & Salon Pack",
            "Pack Multi-Personal para Clínicas y Salones",
            39.0,
            2350.0,
            0.03,
            json.dumps({
                "trial_days": 90,
                "highlights_en": ["90-day free trial", "Up to 10 staff calendars", "3% commission + priority dispatch"],
                "highlights_es": ["90 días de prueba gratis", "Hasta 10 calendarios de personal", "3% de comisión + despacho prioritario"]
            }),
            1,
            4
        ),
    ]
    for pid, pcode, pne, pns, pusd, pdop, pcomm, pfeat, pact, psort in saas_plans_data:
        cur.execute(
            """INSERT OR IGNORE INTO saas_plans (
                id, code, name_en, name_es, monthly_price_usd, monthly_price_dop,
                commission_rate, features_json, is_active, sort_order
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (pid, pcode, pne, pns, pusd, pdop, pcomm, pfeat, pact, psort)
        )

    cur.execute(
        """INSERT OR IGNORE INTO businesses (
            id, owner_id, slug, trading_name, category_id, primary_location_id,
            description_en, description_es, status, requests_enabled
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'approved', 1)""",
        (
            "biz_montellano_oasis_massage",
            "user_admin",
            "montellano-oasis-massage",
            "Montellano Oasis Massage",
            "cat_wellness_massage",
            "loc_montellano",
            "Relaxing massage and spa therapy in Montellano.",
            "Masajes relajantes y terapia de spa en Montellano.",
        ),
    )

    outreach_starter = [
        ("lead_sosua_1", "The Waterfront Restaurant", "+1-809-571-3024", "Dining & Food", "Sosúa", "Playa Alicia", "user_staff_1"),
        ("lead_sosua_2", "Restaurant Maria (Sosúa Ocean Village)", "+1-809-571-2111", "Dining & Food", "Sosúa", "Reservations", "user_staff_1"),
        ("lead_sosua_3", "El Carnaval Restaurant", "+1-809-970-9433", "Dining & Food", "Sosúa", "El Colibrí / Pedro Clisante", "user_staff_1"),
        ("lead_sosua_4", "Casa Veintiuno", "+1-829-342-8089", "Dining & Food", "Sosúa", "Downtown Sosúa", "user_staff_1"),
        ("lead_sosua_5", "Bar Restaurante The Tree House", "+1-809-571-1383", "Dining & Food", "Sosúa", "Sosúa Beach", "user_staff_1"),
        ("lead_cab_1", "Bobo's Point Surf School & Camp", "+1-809-882-5197", "Tours & Activities", "Cabarete", "Playa Encuentro", "user_staff_2"),
        ("lead_cab_2", "Dominican Surf School", "+1-829-928-1371", "Tours & Activities", "Cabarete", "Encuentro", "user_staff_2"),
        ("lead_pp_1", "Cleto Tours", "+1-809-984-4992", "Tours & Activities", "Puerto Plata", "Amber Cove / Taino Bay", "user_staff_2"),
        ("lead_pp_2", "CR Top Excursions", "+1-809-836-7622", "Tours & Activities", "Puerto Plata", "ATV / Waterfalls", "user_staff_2"),
        ("lead_pp_3", "Mega Adventures DR", "+1-809-586-3611", "Tours & Activities", "Puerto Plata", "27 Waterfalls / Zipline", "user_staff_1"),
        ("lead_pp_4", "Zacarias Tours", "+1-809-249-7861", "Tours & Activities", "Puerto Plata", "Transfers & Excursions", "user_staff_2"),
        ("lead_pp_5", "RV Tours DR", "+1-809-912-4173", "Tours & Activities", "Puerto Plata", "Private Shore Excursions", "user_staff_1"),
        ("lead_sosua_6", "Sosúa Ocean Village Spa", "+1-809-877-4357", "Massage & Wellness", "Sosúa", "Milagros / Spa", "user_staff_1"),
        ("lead_sosua_7", "Spa Sosúa", "+1-809-571-2465", "Massage & Wellness", "Sosúa", "Pedro Clisante", "user_staff_2"),
        ("lead_sosua_8", "Oni Salón & Spa", "+1-809-571-1246", "Beauty & Salon", "Sosúa", "Front Desk", "user_staff_1"),
        ("lead_sosua_9", "Junilsa Masajes Center", "+1-809-571-3551", "Massage & Wellness", "Sosúa", "Reception", "user_staff_2"),
        ("lead_sosua_10", "X-Trem Car and Bike Rentals", "+1-809-860-9342", "Auto & Transport", "Sosúa", "Sosúa Beach", "user_staff_1"),
        ("lead_sosua_11", "CMY Rent a Car", "+1-809-571-2829", "Auto & Transport", "Sosúa", "Main Office", "user_staff_2"),
        ("lead_sosua_12", "Rick Scar Car Rental", "+1-809-571-2579", "Auto & Transport", "Sosúa", "WhatsApp +1-829-540-3159", "user_staff_1"),
        ("lead_sosua_13", "Universal Car Rental", "+1-809-571-0462", "Auto & Transport", "Sosúa", "Front Desk", "user_staff_2"),
        ("lead_cab_3", "El Cocotazo Cafe", "+1-829-678-3647", "Dining & Food", "Cabarete", "Kite Beach", "user_staff_1"),
        ("lead_cab_4", "Cabarete Coffee Company", "+1-809-999-1834", "Dining & Food", "Cabarete", "Main Road", "user_staff_2"),
        ("lead_cab_5", "La Kazba", "+1-829-540-6610", "Dining & Food", "Cabarete", "WhatsApp", "user_staff_1"),
        ("lead_cab_6", "Gorditos Fresh-Mex", "+1-829-844-3434", "Dining & Food", "Cabarete", "Delivery", "user_staff_2"),
        ("lead_cab_7", "Tuva'", "+1-809-869-8769", "Dining & Food", "Cabarete", "Modern Dining", "user_staff_1"),
        ("lead_cab_8", "Ceiba Café e Pizzeria", "+1-829-868-8808", "Dining & Food", "Cabarete", "Perla Marina", "user_staff_2"),
        ("lead_cab_9", "Pizza & Spaghetti House", "+1-829-783-9592", "Dining & Food", "Cabarete", "Beachfront", "user_staff_1"),
        ("lead_cab_10", "Drifter", "+1-829-702-2312", "Dining & Food", "Cabarete", "Beachfront Grill", "user_staff_2"),
        ("lead_cab_11", "Mojitos", "+1-829-723-5534", "Dining & Food", "Cabarete", "WhatsApp/Delivery", "user_staff_1"),
        ("lead_cab_12", "Café Marión y más", "+1-809-240-9492", "Dining & Food", "Cabarete", "Cafe", "user_staff_2"),
        ("lead_cab_13", "Vagamundo Coffee & Waffles", "+1-829-562-8869", "Dining & Food", "Cabarete", "WhatsApp", "user_staff_1"),
        ("lead_pp_6", "Casa Colonial Beach & Spa", "+1-809-320-3232", "Hospitality & Tourism", "Puerto Plata", "Luxury Boutique", "user_staff_2"),
        ("lead_pp_7", "Lifestyle Tropical Beach Resort", "+1-809-970-7777", "Hospitality & Tourism", "Puerto Plata", "Resort", "user_staff_1"),
        ("lead_pp_8", "Emotions by Hodelpa Playa Dorada", "+1-809-320-6226", "Hospitality & Tourism", "Puerto Plata", "Playa Dorada", "user_staff_2"),
        ("lead_pp_9", "Gran Ventana Beach Resort", "+1-809-320-2111", "Hospitality & Tourism", "Puerto Plata", "Playa Dorada", "user_staff_1"),
        ("lead_pp_10", "Senator Puerto Plata Spa Resort", "+1-809-320-4000", "Hospitality & Tourism", "Puerto Plata", "Resort", "user_staff_2"),
        ("lead_pp_11", "Embers Steak House", "+1-809-320-1037", "Dining & Food", "Cofresí", "Steakhouse", "user_staff_1"),
        ("lead_pp_12", "Kaffe Restaurant Bistro", "+1-809-261-3440", "Dining & Food", "Puerto Plata", "Historic District", "user_staff_2"),
        ("lead_pp_13", "Casa Mia", "+1-809-261-2382", "Dining & Food", "Puerto Plata", "City", "user_staff_1"),
        ("lead_law_1", "Guzmán Ariza Attorneys at Law", "+1-809-571-2880", "Legal & Lawyers", "Sosúa", "El Batey", "user_staff_1"),
        ("lead_law_2", "Gratereaux Delva & Associates", "+1-809-571-9785", "Legal & Lawyers", "Cabarete", "Plaza El Patio", "user_staff_2"),
        ("lead_law_3", "DR Legal Shield (Martinez & Crestman)", "+1-809-635-2368", "Legal & Lawyers", "Sosúa", "Main Office", "user_staff_1"),
        ("lead_law_4", "Guido Luis Perdomo Montalvo Law", "+1-809-571-1950", "Legal & Lawyers", "Sosúa", "Pedro Clisante", "user_staff_2"),
        ("lead_law_5", "Lisa Legal Solutions", "+1-809-571-4110", "Legal & Lawyers", "Sosúa", "Plaza Pyramida", "user_staff_1"),
        ("lead_pc_1", "Secrets Royal Beach Punta Cana", "+1-809-221-4646", "Hospitality & Tourism", "Punta Cana", "Resort", "user_staff_1"),
        ("lead_pc_2", "Onno's Bávaro", "+1-809-552-0376", "Dining & Food", "Punta Cana", "Bávaro", "user_staff_2"),
        ("lead_pc_3", "Trebol Restaurant", "+1-809-466-4301", "Dining & Food", "Punta Cana", "Restaurant", "user_staff_1"),
        ("lead_pc_4", "Villa Blanca Beach Club", "+1-809-831-3312", "Dining & Food", "Punta Cana", "Beach Club", "user_staff_2"),
        ("lead_pc_5", "Punta Cana Dinner Sky", "+1-809-759-5439", "Dining & Food", "Punta Cana", "Dining", "user_staff_1"),
        ("lead_pc_6", "Punta Cana Experiences", "+1-809-982-7211", "Tours & Activities", "Punta Cana", "Excursions", "user_staff_2"),
        ("lead_pc_7", "Punta Cana Transfer Pro", "+1-809-935-0357", "Auto & Transport", "Punta Cana", "Transfers", "user_staff_1"),
        ("lead_sd_1", "El Mesón de la Cava", "+1-809-533-2818", "Dining & Food", "Santo Domingo", "Fine Dining", "user_staff_2"),
        ("lead_sd_2", "Mesón D'Bari", "+1-809-687-4091", "Dining & Food", "Santo Domingo", "Colonial Zone", "user_staff_1"),
        ("lead_sd_3", "Pat'e Palo European Brasserie", "+1-809-687-8089", "Dining & Food", "Santo Domingo", "Plaza España", "user_staff_2"),
        ("lead_sd_4", "La Briciola", "+1-809-688-5055", "Dining & Food", "Santo Domingo", "Colonial Zone", "user_staff_1"),
        ("lead_sd_5", "Santino", "+1-809-368-1155", "Dining & Food", "Santo Domingo", "Acrópolis", "user_staff_2"),
        ("lead_sd_6", "Catalonia Santo Domingo", "+1-809-685-0000", "Hospitality & Tourism", "Santo Domingo", "Malecón", "user_staff_1"),
        ("lead_sd_7", "Hotel Villa Colonial", "+1-809-221-1049", "Hospitality & Tourism", "Santo Domingo", "Colonial Zone", "user_staff_2"),
        ("lead_sd_8", "Barceló Santo Domingo", "+1-809-563-5000", "Hospitality & Tourism", "Santo Domingo", "Hotel & Casino", "user_staff_1"),
        ("lead_sd_9", "W&P Santo Domingo", "+1-809-535-0800", "Hospitality & Tourism", "Santo Domingo", "Bella Vista", "user_staff_2"),
        ("lead_sti_1", "AC Hotel by Marriott Santiago", "+1-809-971-2024", "Hospitality & Tourism", "Santiago", "Hotel", "user_staff_1"),
        ("lead_sti_2", "Hodelpa Gran Almirante", "+1-809-580-1992", "Hospitality & Tourism", "Santiago", "Hotel & Casino", "user_staff_2"),
        ("lead_sti_3", "Hampton by Hilton Santiago", "+1-809-582-0224", "Hospitality & Tourism", "Santiago", "Hotel", "user_staff_1"),
        ("lead_sti_4", "Hodelpa Garden Court", "+1-809-664-7000", "Hospitality & Tourism", "Santiago", "Airport", "user_staff_2"),
        ("lead_sti_5", "Hotel Santiago Curio Collection", "+1-809-894-7000", "Hospitality & Tourism", "Santiago", "Hilton", "user_staff_1"),
        ("lead_sti_6", "Hotel Platino & Casino", "+1-809-724-7576", "Hospitality & Tourism", "Santiago", "Hotel", "user_staff_2"),
        ("lead_sti_7", "Lovera Hotel", "+1-809-575-6186", "Hospitality & Tourism", "Santiago", "Hotel", "user_staff_1"),
        ("lead_sti_8", "Giacomo Restaurante Cafe", "+1-809-806-2000", "Dining & Food", "Santiago", "Italian/Café", "user_staff_2"),
        ("lead_sti_9", "Restaurante Mar Y Fuego", "+1-809-736-4488", "Dining & Food", "Santiago", "Jardines Metropolitanos", "user_staff_1"),
        ("lead_sti_10", "Kingdom Restaurante", "+1-809-724-0875", "Dining & Food", "Santiago", "Villa Olga", "user_staff_2"),
        ("lead_sti_11", "Restaurante El Real Sabor", "+1-809-226-1193", "Dining & Food", "Santiago", "Centro", "user_staff_1"),
    ]
    for lid, bname, phone, cat, town, cname, rep_id in outreach_starter:
        cur.execute(
            """INSERT OR IGNORE INTO outreach_leads (
                id, business_name, phone, category, town, contact_name, status, assigned_to
            ) VALUES (?, ?, ?, ?, ?, ?, 'new', ?)""",
            (lid, bname, phone, cat, town, cname, rep_id),
        )

    conn.commit()
    conn.close()
    print("Database successfully initialized and seeded with Sosúa pilot data!")

if __name__ == "__main__":
    db_file = os.environ.get("MAVUNQO_DB_PATH", "").strip() or os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "..", "mavunqo.db"
    )
    if os.path.dirname(db_file):
        os.makedirs(os.path.dirname(db_file), exist_ok=True)
    seed_database(db_file)
