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
        ("cat_grocery", "groceries-colmados", "Supermarkets & Colmados", "Supermercados y Colmados", "shopping-cart", 7),
        ("cat_fashion", "clothing-fashion", "Clothing & Beachwear", "Ropa y Moda Playera", "shirt", 8),
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
                hours_json, rnc_tax_id, rnc_status, approved_by, approved_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)""",
            (
                b_clothe, cloth_owner, "Yaha Style RD", "Yaha Style RD - Yahaira Garcia",
                "yaha-style-rd", "cat_fashion", "loc_sosua",
                "Trendy women and men fashion, coastal beachwear, stylish linen dresses, casual outfits, swimsuits, and accessories in Sosúa.",
                "Moda actual femenina y masculina, ropa playera, elegantes vestidos de lino, conjuntos casuales, trajes de baño y accesorios en Sosúa.",
                "approved", 1, "Calle Pedro Clisante #28, El Batey, Sosúa",
                1, None, "+18296414722", "+18296414722", "yahastylerd@gmail.com",
                "/frontend/uploads/yahastyle/item_black_goldbutton_mini_dress.png",
                "/frontend/uploads/yahastyle/item_rose_gold_velvet_choker_dress.jpg",
                json.dumps({"monday_saturday": "9:30 AM - 8:00 PM", "sunday": "10:00 AM - 4:00 PM"}),
                "131-44781-9", "verified", admin_id
            )
        )
        cur.execute("INSERT OR IGNORE INTO business_service_areas (business_id, location_id) VALUES (?, ?)", (b_clothe, "loc_sosua"))
        cur.execute("INSERT OR IGNORE INTO business_service_areas (business_id, location_id) VALUES (?, ?)", (b_clothe, "loc_cabarete"))

    # Seed all boutique categories
    boutique_cats = [('ccat_swimwear', 'Swimwear & Boardshorts', 'Trajes de Baño y Bañadores', 1), ('ccat_linen_apparel', 'Linen Dresses & Beach Shirts', 'Vestidos de Lino y Camisas Playeras', 2), ('ccat_yaha_dresses', 'Chic Dresses & Evening Outfits', 'Vestidos Elegantes y de Noche', 1), ('ccat_yaha_casual', 'Casual Wear & Pants', 'Ropa Casual, Joggers y Tops', 2), ('ccat_yaha_denim', 'Denim, Jeans & Skirts', 'Jeans, Pantalones y Faldas Denim', 3), ('ccat_yaha_swim', 'Swimwear & One-Pieces', 'Trajes de Baño y Monokinis', 4), ('ccat_yaha_tops', 'Glitter Sets, Tanks & Tops', 'Conjuntos Brillantes y Tops Urbanos', 5)]
    for cid, cname_en, cname_es, csort in boutique_cats:
        cur.execute("INSERT OR REPLACE INTO menu_categories (id, business_id, name_en, name_es, sort_order) VALUES (?, ?, ?, ?, ?)",
                    (cid, b_clothe, cname_en, cname_es, csort))

    # Seed all 43 boutique items with photos and descriptions
    boutique_items = [('yaha_01', 'ccat_yaha_dresses', 'Red Twist-Front Ribbed Long Sleeve Dress', 'Vestido Rojo Manga Larga con Nudo Delantero', 'Fitted ribbed bodycon dress with knot detail and plunge V-neckline.', 'Vestido acanalado entallado de manga larga con elegante nudo al frente.', 1850.0, 'DOP', '/frontend/uploads/yahastyle/item_red_longsleeve_wrap.png', 1, 1), ('yaha_02', 'ccat_yaha_dresses', 'Red Strapless Asymmetric Cocktail Dress', 'Vestido Rojo Asimétrico sin Tirantes', 'Sleek strapless cowl neck party dress with modern geometric hemline.', 'Vestido de fiesta sin tirantes con escote fluido y bajo asimétrico.', 1650.0, 'DOP', '/frontend/uploads/yahastyle/item_red_strapless_asymmetric.png', 1, 2), ('yaha_03', 'ccat_yaha_dresses', 'Black & White Off-Shoulder Grid Check Dress', 'Vestido Cuadriculado Blanco y Negro Off-Shoulder', 'Chic off-the-shoulder fitted check dress with discreet front leg slit.', 'Vestido a cuadros blanco y negro con hombros descubiertos y abertura frontal.', 1750.0, 'DOP', '/frontend/uploads/yahastyle/item_black_white_grid_dress.jpg', 1, 3), ('yaha_04', 'ccat_yaha_dresses', 'Red Cutout Knot Mini Sun Dress', 'Vestido Corto Rojo con Abertura Frontal', 'Flirty summer bodycon dress with front twist knot and waist cutout.', 'Vestido veraniego fresco con nudo y abertura estilizada en la cintura.', 1550.0, 'DOP', '/frontend/uploads/yahastyle/item_red_cutout_mini_dress.png', 1, 4), ('yaha_05', 'ccat_yaha_dresses', 'Black Ruched Off-Shoulder Midi Dress', 'Vestido Negro Drapeado Hombro Caído', 'Elegant draped and ruched evening dress with one-shoulder silhouette.', 'Vestido de noche drapeado elegante con silueta asimétrica de hombro caído.', 1950.0, 'DOP', '/frontend/uploads/yahastyle/item_black_offshoulder_ruched.png', 1, 5), ('yaha_06', 'ccat_yaha_dresses', 'Emerald Green Ribbed Racerback Mini Dress', 'Vestido Verde Esmeralda Acanalado Espalda Deportiva', 'Sleeveless high-neck ribbed knit casual mini dress with racerback straps.', 'Vestido mini acanalado verde esmeralda con tirantes deportivos en la espalda.', 1450.0, 'DOP', '/frontend/uploads/yahastyle/item_emerald_green_ribbed_dress.png', 1, 6), ('yaha_07', 'ccat_yaha_dresses', 'Sporty Trio Ribbed Tank Dresses (Yellow/Red/Black)', 'Vestido Deportivo Tricolor a Rayas (Set / Unitario)', 'Athletic ribbed cotton tank dress with contrast piping borders.', 'Vestido deportivo de tirantes con detalles en contraste.', 1350.0, 'DOP', '/frontend/uploads/yahastyle/item_sporty_tank_dresses_trio.jpg', 1, 7), ('yaha_08', 'ccat_yaha_dresses', 'Peach Halter Cutout Bodycon Dress', 'Vestido Melocotón Halter con Espalda Cruzada', 'Vibrant ribbed stretch dress with unique halter neck and strap details.', 'Vestido entallado color melocotón con cuello halter y tirantes ajustables.', 1550.0, 'DOP', '/frontend/uploads/yahastyle/item_peach_halter_cutout_dress.jpg', 1, 8), ('yaha_09', 'ccat_yaha_dresses', 'Summer Ribbed Cutout Dresses (Pink & Red)', 'Vestidos Veraniegos de Tirantes con Nudo (Rosa y Rojo)', 'Sleeveless spaghetti-strap bodycon midi dress in vibrant tropical shades.', 'Vestidos frescos de verano con tirantes finos en tonos rosa y rojo.', 1500.0, 'DOP', '/frontend/uploads/yahastyle/item_pink_and_red_summer_duo.jpg', 1, 9), ('yaha_10', 'ccat_yaha_dresses', 'Black Sweetheart Mini Dress with Gold Button Accent', 'Vestido Negro Escote Corazón con Botón Dorado', 'Tailored long-sleeve evening mini dress with notched sweetheart neckline.', 'Elegante vestido negro entallado de manga larga con escote corazón y botón dorado.', 2100.0, 'DOP', '/frontend/uploads/yahastyle/item_black_goldbutton_mini_dress.png', 1, 10), ('yaha_11', 'ccat_yaha_casual', 'Black Long-Sleeve Active Romper / Jumpsuit', 'Enterizo Deportivo Negro de Manga Larga con Cremallera', 'Full-body stretch athletic activewear romper with front half-zip and mock collar.', 'Enterizo elástico de compresión para entrenamiento y estilo urbano.', 1950.0, 'DOP', '/frontend/uploads/yahastyle/item_black_longsleeve_active_romper.jpg', 1, 11), ('yaha_12', 'ccat_yaha_dresses', 'Emerald Green Satin Sparkle Cocktail Dress', 'Vestido Satinado Verde Esmeralda con Tirantes Brillantes', 'Glamorous liquid satin slip dress featuring rhinestone sparkle straps.', 'Vestido de satén fluido verde esmeralda con tirantes brillantes de pedrería.', 2250.0, 'DOP', '/frontend/uploads/yahastyle/item_emerald_satin_sparkle_dress.jpg', 1, 12), ('yaha_13', 'ccat_yaha_dresses', 'Liquid Black Satin Cocktail Duo Dresses', 'Vestido Corto de Satén Negro para Coctel', 'Seductive black satin body-skimming cocktail dress with sweetheart bust cups.', 'Vestido de satén negro suave con copas estilo corsé para veladas y eventos.', 2150.0, 'DOP', '/frontend/uploads/yahastyle/item_black_satin_duo_cocktail_dresses.jpg', 1, 13), ('yaha_14', 'ccat_yaha_dresses', 'Blush Velvet Marble Choker Neck Midi Dress', 'Vestido Terciopelo Rosa Marmolado con Cuello Choker', 'Crushed velvet wrap midi dress with matching choker neck and high side slit.', 'Vestido de terciopelo marmolado con gargantilla a juego y abertura en la pierna.', 2350.0, 'DOP', '/frontend/uploads/yahastyle/item_rose_gold_velvet_choker_dress.jpg', 1, 14), ('yaha_15', 'ccat_yaha_casual', "Grey 'Faith' Cross Oversized Relaxed T-Shirt", "Camiseta Gris 'Faith' Estampada de Cruz", 'Soft cotton relaxed drop-shoulder graphic tee with calligraphic cross print.', "Camiseta de algodón suave estilo holgado con diseño de cruz 'Faith'.", 950.0, 'DOP', '/frontend/uploads/yahastyle/item_grey_faith_cross_tshirt.jpg', 1, 15), ('yaha_16', 'ccat_yaha_casual', 'Mustard Khaki Slim-Fit Cargo Joggers', 'Pantalón Cargo Jogger Mostaza con Bolsillos', 'Trendy high-waisted cargo pants with side flap utility pockets and elastic cuffs.', 'Pantalón cargo estilo jogger con bolsillos laterales y puños elásticos.', 1650.0, 'DOP', '/frontend/uploads/yahastyle/item_mustard_khaki_cargo_joggers.jpg', 1, 16), ('yaha_17', 'ccat_yaha_swim', 'Tropical Red & Black Leaves Halter Swimsuit', 'Traje de Baño Enterizo Hojas Rojas Tropicales', 'High-cut halter one-piece swimsuit with bold Caribbean botanical leaf print.', 'Traje de baño enterizo con cuello halter y estampado botánico tropical en rojo y negro.', 1650.0, 'DOP', '/frontend/uploads/yahastyle/item_tropical_red_leaves_swimsuit.jpg', 1, 1), ('yaha_18', 'ccat_yaha_swim', 'Classic Leopard Print High-Neck Monokini', 'Bañador Enterizo Estampado de Leopardo', 'Sleek halter animal-print one-piece with slimming high leg cut.', 'Traje de baño de animal print clásico con corte estilizado para la playa.', 1650.0, 'DOP', '/frontend/uploads/yahastyle/item_leopard_print_highneck_swimsuit.jpg', 1, 2), ('yaha_19', 'ccat_yaha_denim', 'Vintage Washed Khaki Skinny Jeans', 'Jeans Skinny Lavado Vintage Khaki', 'Comfort-stretch slim fit colored denim jeans with classic 5-pocket styling.', 'Pantalón jeans skinny en tono khaki envejecido con tela elástica cómoda.', 1850.0, 'DOP', '/frontend/uploads/yahastyle/item_vintage_khaki_skinny_jeans.jpg', 1, 3), ('yaha_20', 'ccat_yaha_denim', 'Classic Blue Wash High-Rise Skinny Jeans', 'Jeans Skinny Azul Clásico Tiro Alto', 'Flattering dark-washed body sculpting stretch jeans with double back pockets.', 'Jeans entallados azul clásico de tiro alto con efecto moldeador.', 1950.0, 'DOP', '/frontend/uploads/yahastyle/item_classic_blue_wash_skinny_jeans.jpg', 1, 4), ('yaha_21', 'ccat_yaha_denim', 'White Distressed Ripped Straight Leg Jeans', 'Jeans Blancos Rasgados Estilo Urbano', 'Clean white denim jeans featuring trendy front slit distressing and raw edge hems.', 'Jeans blancos de corte recto moderno con roturas frontales a la moda.', 2100.0, 'DOP', '/frontend/uploads/yahastyle/item_white_distressed_ripped_jeans.png', 1, 5), ('yaha_22', 'ccat_yaha_denim', 'Acid Wash Grey Cropped Raw Hem Jeans', 'Jeans Grises Lavado Ácido con Bajo Deshilachado', 'Edgy grey wash high-waisted denim pants with trendy ankle crop and frayed edge.', 'Jeans grises lavado ácido de tiro alto con terminación rústica deshilachada.', 1950.0, 'DOP', '/frontend/uploads/yahastyle/item_acid_wash_grey_denim_jeans.jpg', 1, 6), ('yaha_23', 'ccat_yaha_denim', 'Distressed Washed Denim Mini Skirt', 'Minifalda Denim con Roturas y Desgaste', 'Classic casual denim mini skirt with front rips, whiskers, and raw fringe hem.', 'Minifalda vaquera de corte clásico con roturas frontales y flecos.', 1450.0, 'DOP', '/frontend/uploads/yahastyle/item_distressed_denim_mini_skirt.jpg', 1, 7), ('yaha_24', 'ccat_yaha_tops', 'Metallic Silver Glitter Crop Top & Belted Pant Set', 'Conjunto 2 Piezas Plateado Brillante con Cinturón', 'Showstopping metallic shimmer plunge bralette top paired with belted wide-leg trousers.', 'Conjunto brillante de fiesta de 2 piezas: top escotado y pantalón con hebilla dorada.', 2850.0, 'DOP', '/frontend/uploads/yahastyle/item_metallic_glitter_crop_pant_set.jpg', 1, 8), ('yaha_25', 'ccat_yaha_tops', 'Glitter Shimmer Halter Crop & Ruched Skirt Set', 'Conjunto Glitter Top Halter y Falda Drapeada', 'Two-piece night-out club set with halter crop top and side-ruched bodycon mini skirt.', 'Conjunto de fiesta de 2 piezas con top halter brillante y minifalda fruncida.', 2450.0, 'DOP', '/frontend/uploads/yahastyle/item_glitter_halter_crop_ruched_skirt_set.jpg', 1, 9), ('yaha_26', 'ccat_yaha_tops', "Studded Black Streetwear Tank ('Liquid 67')", "Camiseta sin Mangas Negra con Tachuelas '67'", 'Sleeveless edgy black drop tee with metallic shoulder studs and psychedelic drip number print.', 'Camiseta de tirantes negra estilo urbano con tachuelas plateadas y gráfico líquido 67.', 1250.0, 'DOP', '/frontend/uploads/yahastyle/item_black_liquid_67_studded_tank.jpg', 1, 10), ('yaha_27', 'ccat_yaha_tops', "Studded Royal Blue Racing Tank ('15')", "Camiseta Deportiva Azul Rey con Tachuelas '15'", 'Vibrant royal blue athletic tank top with studded neckline and racing graphics.', 'Camiseta azul rey estilo motorsport con tachuelas metálicas y número 15.', 1250.0, 'DOP', '/frontend/uploads/yahastyle/item_royal_blue_racing_15_studded_tank.jpg', 1, 11), ('yaha_28', 'ccat_yaha_tops', 'Metallic Gold Crocodile Scale Crop Tank', 'Top Corto Dorado Efecto Escamas de Cocodrilo', 'Eye-catching high-neck metallic textured crop top in luxury gold finish.', 'Top brillante dorado con textura en relieve tipo escamas para ocasiones especiales.', 1350.0, 'DOP', '/frontend/uploads/yahastyle/item_metallic_gold_scales_crop_top.jpg', 1, 12), ('yaha_29', 'ccat_yaha_tops', 'OXOX Floral Lips Graphic Crop T-Shirt', "Camiseta Crop 'OXOX' con Labios Florales", 'Cream soft cotton crewneck boxy crop tee with vibrant botanical floral kiss print.', 'Camiseta crop color crema con diseño estampado de labios florales estilo urbano.', 950.0, 'DOP', '/frontend/uploads/yahastyle/item_oxox_floral_lips_crop_tee.jpg', 1, 13), ('yaha_30', 'ccat_yaha_tops', 'Neon Yellow Asymmetric Shoulder Cutout Tank', 'Top Neón Amarillo con Escote Asimétrico', 'Electric neon yellow ribbed stretch tank top featuring modern double-strap shoulder cutout.', 'Top acanalado amarillo neón con tirante doble asimétrico para look llamativo.', 1150.0, 'DOP', '/frontend/uploads/yahastyle/item_neon_yellow_cutout_tank.jpg', 1, 14), ('yaha_31', 'ccat_yaha_tops', 'White Crewneck Tee with Silver Sequin Bow', 'Camiseta Blanca con Lazo Brillante de Lentejuelas', 'Classic premium white cotton short-sleeve tee adorned with a hand-stitched silver sequin bow.', 'Camiseta blanca clásica decorada con un hermoso lazo brillante de lentejuelas.', 1250.0, 'DOP', '/frontend/uploads/yahastyle/item_white_sequin_bow_tshirt.jpg', 1, 15), ('yaha_32', 'ccat_yaha_tops', 'Bronze Satin Asymmetric Wrap Tie Halter Top', 'Top de Satén Bronce con Lazos y Cuello Halter', 'Lustrous copper bronze satin wrap crop top with extended wrap-around tie ribbons.', 'Top brillante de satén color bronce con cuello halter y lazos largos ajustables.', 1450.0, 'DOP', '/frontend/uploads/yahastyle/item_bronze_satin_asymmetric_tie_top.jpg', 1, 16), ('yaha_33', 'ccat_yaha_swim', 'Neon Lime Underwire Push-Up Bikini Set', 'Bikini 2 Piezas Verde Neón con Soporte', 'Vibrant 2-piece neon lime swimsuit featuring supportive underwire cups and tie-side cheeky bottoms.', 'Bikini de dos piezas verde neón con copas armadas y lazos laterales ajustables.', 1850.0, 'DOP', '/frontend/uploads/yahastyle/item_neon_lime_underwire_bikini_set.jpg', 1, 3), ('yaha_34', 'ccat_yaha_swim', 'Classic Black Underwire Halter Monokini', 'Bañador Enterizo Negro con Copas y Escote Profundo', 'Sophisticated black one-piece swimsuit with sculpted bust cups and halter neck strap.', 'Elegante traje de baño enterizo negro con escote corazón y soporte de busto.', 1750.0, 'DOP', '/frontend/uploads/yahastyle/item_black_halter_underwire_monokini.jpg', 1, 4), ('yaha_35', 'ccat_yaha_tops', "Burgundy 'Positive Life Attitude' Graphic Tee", "Camiseta Borgoña 'Positive Life Attitude'", 'Casual maroon soft-knit t-shirt with brushstroke inspirational typographic print.', 'Camiseta casual color vino con mensaje motivacional y corte clásico cómodo.', 950.0, 'DOP', '/frontend/uploads/yahastyle/item_burgundy_positive_life_tshirt.jpg', 1, 17), ('yaha_36', 'ccat_yaha_tops', 'Royal Blue Front-Zip Ribbed Crop Tank', 'Top Corto Azul Rey con Cremallera y Argolla', 'Cobalt blue ribbed crop tank with full functional silver ring zipper down the front.', 'Top acanalado azul eléctrico con cremallera frontal decorativa y argolla plateada.', 1200.0, 'DOP', '/frontend/uploads/yahastyle/item_royal_blue_zipper_ribbed_tank.jpg', 1, 18), ('yaha_37', 'ccat_yaha_swim', 'Celestial Sun & Moon Mystic Print One-Piece', 'Traje de Baño Místico Estampado Sol y Luna', 'Artistic black and cream celestial astrology print swimsuit with athletic scoop neck.', 'Traje de baño enterizo con diseño celestial astrológico de sol, luna y constelaciones.', 1750.0, 'DOP', '/frontend/uploads/yahastyle/item_celestial_sun_moon_one_piece.jpg', 1, 5), ('yaha_38', 'ccat_yaha_tops', 'Vanilla Cream Lettuce-Edge Ribbed Cami Top', 'Top de Tirantes Crema con Bordes Ondulados', 'Dainty ribbed knit sleeveless camisole with romantic ruffled lettuce-edge trims.', 'Top corto fresco color crema con textura acanalada y bordes ondulados.', 950.0, 'DOP', '/frontend/uploads/yahastyle/item_cream_lettuce_trim_ribbed_camisole.jpg', 1, 19), ('yaha_39', 'ccat_yaha_casual', "Acid Wash 'Faith Over Fear' Raw Cut Shorts", "Bermuda de Algodón Lavado Ácido 'Faith Over Fear'", 'Heavyweight mineral washed dark grey sweat shorts with drawstring and spiritual graphic.', 'Short bermuda estilo urbano gris lavado ácido con cordón ajustable y diseño impreso.', 1450.0, 'DOP', '/frontend/uploads/yahastyle/item_acid_wash_faith_over_fear_shorts.jpg', 1, 4), ('yaha_40', 'ccat_yaha_tops', 'Black Patent Crocodile Structured Corset Bustier', 'Corset Bustier Negro Efecto Piel de Cocodrilo', 'Glossy embossed croc-textured structured corset top with underwire cups and adjustable straps.', 'Top corset estructurado negro brillante textura cocodrilo para veladas y eventos.', 1950.0, 'DOP', '/frontend/uploads/yahastyle/item_black_crocodile_corset_bustier.jpg', 1, 20), ('yaha_41', 'ccat_yaha_tops', 'Mint Satin Backless Cowl Neck Handkerchief Top', 'Top Satinado Verde Menta con Espalda Descubierta', 'Silky pastel mint green draped cowl front top with open back criss-cross ties.', 'Top de satén verde menta con escote fluido y sensuales lazos cruzados en la espalda.', 1450.0, 'DOP', '/frontend/uploads/yahastyle/item_mint_green_satin_cowl_backless_top.jpg', 1, 21), ('yaha_42', 'ccat_yaha_tops', 'Heather Grey Studded V-Neck Ribbed Tie-Back Tank', "Top Gris Claro con Tachuelas en 'V' y Lazo", 'Soft grey ribbed knit crop top with silver stud embellishments and waist tie bow.', 'Top acanalado gris con detalle de tachuelas plateadas en escote V y lazo decorativo.', 1350.0, 'DOP', '/frontend/uploads/yahastyle/item_heather_grey_studded_bow_ribbed_tank.jpg', 1, 22), ('yaha_43', 'ccat_yaha_tops', 'Ivory Ribbed Long-Sleeve Boatneck Crop Top', 'Top Manga Larga Blanco Marfil Cuello Barco', 'Minimalist long sleeve body-contour ribbed crop top with wide boat neckline.', 'Top blanco marfil de manga larga con escote barco elegante y tela elástica suave.', 1350.0, 'DOP', '/frontend/uploads/yahastyle/item_ivory_boatneck_ribbed_longsleeve_crop.jpg', 1, 23)]
    for iid, icat, iname_en, iname_es, idesc_en, idesc_es, iprice, icurr, iimg, iavail, isort in boutique_items:
        cur.execute("""INSERT OR REPLACE INTO menu_items (id, business_id, category_id, name_en, name_es, description_en, description_es, price, currency, image_url, is_available, sort_order)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (iid, b_clothe, icat, iname_en, iname_es, idesc_en, idesc_es, iprice, icurr, iimg, iavail, isort))

    # Seed all 178 size modifiers
    boutique_mods = [('mod_yaha_01_0', 'yaha_01', 'Select Size', 'Seleccionar Talla', 'Size S (Small)', 'Talla S (Pequena)', 0.0, 'DOP', 1, 0), ('mod_yaha_01_1', 'yaha_01', 'Select Size', 'Seleccionar Talla', 'Size M (Medium)', 'Talla M (Mediana)', 0.0, 'DOP', 1, 1), ('mod_yaha_01_2', 'yaha_01', 'Select Size', 'Seleccionar Talla', 'Size L (Large)', 'Talla L (Grande)', 0.0, 'DOP', 1, 2), ('mod_yaha_01_3', 'yaha_01', 'Select Size', 'Seleccionar Talla', 'Size XL (Extra Large)', 'Talla XL (Extra Grande)', 0.0, 'DOP', 1, 3), ('mod_yaha_02_0', 'yaha_02', 'Select Size', 'Seleccionar Talla', 'Size S (Small)', 'Talla S (Pequena)', 0.0, 'DOP', 1, 0), ('mod_yaha_02_1', 'yaha_02', 'Select Size', 'Seleccionar Talla', 'Size M (Medium)', 'Talla M (Mediana)', 0.0, 'DOP', 1, 1), ('mod_yaha_02_2', 'yaha_02', 'Select Size', 'Seleccionar Talla', 'Size L (Large)', 'Talla L (Grande)', 0.0, 'DOP', 1, 2), ('mod_yaha_02_3', 'yaha_02', 'Select Size', 'Seleccionar Talla', 'Size XL (Extra Large)', 'Talla XL (Extra Grande)', 0.0, 'DOP', 1, 3), ('mod_yaha_03_0', 'yaha_03', 'Select Size', 'Seleccionar Talla', 'Size S (Small)', 'Talla S (Pequena)', 0.0, 'DOP', 1, 0), ('mod_yaha_03_1', 'yaha_03', 'Select Size', 'Seleccionar Talla', 'Size M (Medium)', 'Talla M (Mediana)', 0.0, 'DOP', 1, 1), ('mod_yaha_03_2', 'yaha_03', 'Select Size', 'Seleccionar Talla', 'Size L (Large)', 'Talla L (Grande)', 0.0, 'DOP', 1, 2), ('mod_yaha_03_3', 'yaha_03', 'Select Size', 'Seleccionar Talla', 'Size XL (Extra Large)', 'Talla XL (Extra Grande)', 0.0, 'DOP', 1, 3), ('mod_yaha_04_0', 'yaha_04', 'Select Size', 'Seleccionar Talla', 'Size S (Small)', 'Talla S (Pequena)', 0.0, 'DOP', 1, 0), ('mod_yaha_04_1', 'yaha_04', 'Select Size', 'Seleccionar Talla', 'Size M (Medium)', 'Talla M (Mediana)', 0.0, 'DOP', 1, 1), ('mod_yaha_04_2', 'yaha_04', 'Select Size', 'Seleccionar Talla', 'Size L (Large)', 'Talla L (Grande)', 0.0, 'DOP', 1, 2), ('mod_yaha_04_3', 'yaha_04', 'Select Size', 'Seleccionar Talla', 'Size XL (Extra Large)', 'Talla XL (Extra Grande)', 0.0, 'DOP', 1, 3), ('mod_yaha_05_0', 'yaha_05', 'Select Size', 'Seleccionar Talla', 'Size S (Small)', 'Talla S (Pequena)', 0.0, 'DOP', 1, 0), ('mod_yaha_05_1', 'yaha_05', 'Select Size', 'Seleccionar Talla', 'Size M (Medium)', 'Talla M (Mediana)', 0.0, 'DOP', 1, 1), ('mod_yaha_05_2', 'yaha_05', 'Select Size', 'Seleccionar Talla', 'Size L (Large)', 'Talla L (Grande)', 0.0, 'DOP', 1, 2), ('mod_yaha_05_3', 'yaha_05', 'Select Size', 'Seleccionar Talla', 'Size XL (Extra Large)', 'Talla XL (Extra Grande)', 0.0, 'DOP', 1, 3), ('mod_yaha_06_0', 'yaha_06', 'Select Size', 'Seleccionar Talla', 'Size S (Small)', 'Talla S (Pequena)', 0.0, 'DOP', 1, 0), ('mod_yaha_06_1', 'yaha_06', 'Select Size', 'Seleccionar Talla', 'Size M (Medium)', 'Talla M (Mediana)', 0.0, 'DOP', 1, 1), ('mod_yaha_06_2', 'yaha_06', 'Select Size', 'Seleccionar Talla', 'Size L (Large)', 'Talla L (Grande)', 0.0, 'DOP', 1, 2), ('mod_yaha_06_3', 'yaha_06', 'Select Size', 'Seleccionar Talla', 'Size XL (Extra Large)', 'Talla XL (Extra Grande)', 0.0, 'DOP', 1, 3), ('mod_yaha_07_0', 'yaha_07', 'Select Size', 'Seleccionar Talla', 'Size S (Small)', 'Talla S (Pequena)', 0.0, 'DOP', 1, 0), ('mod_yaha_07_1', 'yaha_07', 'Select Size', 'Seleccionar Talla', 'Size M (Medium)', 'Talla M (Mediana)', 0.0, 'DOP', 1, 1), ('mod_yaha_07_2', 'yaha_07', 'Select Size', 'Seleccionar Talla', 'Size L (Large)', 'Talla L (Grande)', 0.0, 'DOP', 1, 2), ('mod_yaha_07_3', 'yaha_07', 'Select Size', 'Seleccionar Talla', 'Size XL (Extra Large)', 'Talla XL (Extra Grande)', 0.0, 'DOP', 1, 3), ('mod_yaha_08_0', 'yaha_08', 'Select Size', 'Seleccionar Talla', 'Size S (Small)', 'Talla S (Pequena)', 0.0, 'DOP', 1, 0), ('mod_yaha_08_1', 'yaha_08', 'Select Size', 'Seleccionar Talla', 'Size M (Medium)', 'Talla M (Mediana)', 0.0, 'DOP', 1, 1), ('mod_yaha_08_2', 'yaha_08', 'Select Size', 'Seleccionar Talla', 'Size L (Large)', 'Talla L (Grande)', 0.0, 'DOP', 1, 2), ('mod_yaha_08_3', 'yaha_08', 'Select Size', 'Seleccionar Talla', 'Size XL (Extra Large)', 'Talla XL (Extra Grande)', 0.0, 'DOP', 1, 3), ('mod_yaha_09_0', 'yaha_09', 'Select Size', 'Seleccionar Talla', 'Size S (Small)', 'Talla S (Pequena)', 0.0, 'DOP', 1, 0), ('mod_yaha_09_1', 'yaha_09', 'Select Size', 'Seleccionar Talla', 'Size M (Medium)', 'Talla M (Mediana)', 0.0, 'DOP', 1, 1), ('mod_yaha_09_2', 'yaha_09', 'Select Size', 'Seleccionar Talla', 'Size L (Large)', 'Talla L (Grande)', 0.0, 'DOP', 1, 2), ('mod_yaha_09_3', 'yaha_09', 'Select Size', 'Seleccionar Talla', 'Size XL (Extra Large)', 'Talla XL (Extra Grande)', 0.0, 'DOP', 1, 3), ('mod_yaha_10_0', 'yaha_10', 'Select Size', 'Seleccionar Talla', 'Size S (Small)', 'Talla S (Pequena)', 0.0, 'DOP', 1, 0), ('mod_yaha_10_1', 'yaha_10', 'Select Size', 'Seleccionar Talla', 'Size M (Medium)', 'Talla M (Mediana)', 0.0, 'DOP', 1, 1), ('mod_yaha_10_2', 'yaha_10', 'Select Size', 'Seleccionar Talla', 'Size L (Large)', 'Talla L (Grande)', 0.0, 'DOP', 1, 2), ('mod_yaha_10_3', 'yaha_10', 'Select Size', 'Seleccionar Talla', 'Size XL (Extra Large)', 'Talla XL (Extra Grande)', 0.0, 'DOP', 1, 3), ('mod_yaha_11_0', 'yaha_11', 'Select Size', 'Seleccionar Talla', 'Size S (Small)', 'Talla S (Pequena)', 0.0, 'DOP', 1, 0), ('mod_yaha_11_1', 'yaha_11', 'Select Size', 'Seleccionar Talla', 'Size M (Medium)', 'Talla M (Mediana)', 0.0, 'DOP', 1, 1), ('mod_yaha_11_2', 'yaha_11', 'Select Size', 'Seleccionar Talla', 'Size L (Large)', 'Talla L (Grande)', 0.0, 'DOP', 1, 2), ('mod_yaha_11_3', 'yaha_11', 'Select Size', 'Seleccionar Talla', 'Size XL (Extra Large)', 'Talla XL (Extra Grande)', 0.0, 'DOP', 1, 3), ('mod_yaha_12_0', 'yaha_12', 'Select Size', 'Seleccionar Talla', 'Size S (Small)', 'Talla S (Pequena)', 0.0, 'DOP', 1, 0), ('mod_yaha_12_1', 'yaha_12', 'Select Size', 'Seleccionar Talla', 'Size M (Medium)', 'Talla M (Mediana)', 0.0, 'DOP', 1, 1), ('mod_yaha_12_2', 'yaha_12', 'Select Size', 'Seleccionar Talla', 'Size L (Large)', 'Talla L (Grande)', 0.0, 'DOP', 1, 2), ('mod_yaha_12_3', 'yaha_12', 'Select Size', 'Seleccionar Talla', 'Size XL (Extra Large)', 'Talla XL (Extra Grande)', 0.0, 'DOP', 1, 3), ('mod_yaha_13_0', 'yaha_13', 'Select Size', 'Seleccionar Talla', 'Size S (Small)', 'Talla S (Pequena)', 0.0, 'DOP', 1, 0), ('mod_yaha_13_1', 'yaha_13', 'Select Size', 'Seleccionar Talla', 'Size M (Medium)', 'Talla M (Mediana)', 0.0, 'DOP', 1, 1), ('mod_yaha_13_2', 'yaha_13', 'Select Size', 'Seleccionar Talla', 'Size L (Large)', 'Talla L (Grande)', 0.0, 'DOP', 1, 2), ('mod_yaha_13_3', 'yaha_13', 'Select Size', 'Seleccionar Talla', 'Size XL (Extra Large)', 'Talla XL (Extra Grande)', 0.0, 'DOP', 1, 3), ('mod_yaha_14_0', 'yaha_14', 'Select Size', 'Seleccionar Talla', 'Size S (Small)', 'Talla S (Pequena)', 0.0, 'DOP', 1, 0), ('mod_yaha_14_1', 'yaha_14', 'Select Size', 'Seleccionar Talla', 'Size M (Medium)', 'Talla M (Mediana)', 0.0, 'DOP', 1, 1), ('mod_yaha_14_2', 'yaha_14', 'Select Size', 'Seleccionar Talla', 'Size L (Large)', 'Talla L (Grande)', 0.0, 'DOP', 1, 2), ('mod_yaha_14_3', 'yaha_14', 'Select Size', 'Seleccionar Talla', 'Size XL (Extra Large)', 'Talla XL (Extra Grande)', 0.0, 'DOP', 1, 3), ('mod_yaha_15_0', 'yaha_15', 'Select Size', 'Seleccionar Talla', 'Size S (Small)', 'Talla S (Pequena)', 0.0, 'DOP', 1, 0), ('mod_yaha_15_1', 'yaha_15', 'Select Size', 'Seleccionar Talla', 'Size M (Medium)', 'Talla M (Mediana)', 0.0, 'DOP', 1, 1), ('mod_yaha_15_2', 'yaha_15', 'Select Size', 'Seleccionar Talla', 'Size L (Large)', 'Talla L (Grande)', 0.0, 'DOP', 1, 2), ('mod_yaha_15_3', 'yaha_15', 'Select Size', 'Seleccionar Talla', 'Size XL (Extra Large)', 'Talla XL (Extra Grande)', 0.0, 'DOP', 1, 3), ('mod_yaha_16_0', 'yaha_16', 'Select Size', 'Seleccionar Talla', 'Size 1 / 26 (XS)', 'Talla 1 / 26 (XS)', 0.0, 'DOP', 1, 0), ('mod_yaha_16_1', 'yaha_16', 'Select Size', 'Seleccionar Talla', 'Size 3 / 28 (S)', 'Talla 3 / 28 (S)', 0.0, 'DOP', 1, 1), ('mod_yaha_16_2', 'yaha_16', 'Select Size', 'Seleccionar Talla', 'Size 5 / 30 (M)', 'Talla 5 / 30 (M)', 0.0, 'DOP', 1, 2), ('mod_yaha_16_3', 'yaha_16', 'Select Size', 'Seleccionar Talla', 'Size 7 / 32 (L)', 'Talla 7 / 32 (L)', 0.0, 'DOP', 1, 3), ('mod_yaha_16_4', 'yaha_16', 'Select Size', 'Seleccionar Talla', 'Size 9 / 34 (XL)', 'Talla 9 / 34 (XL)', 0.0, 'DOP', 1, 4), ('mod_yaha_17_0', 'yaha_17', 'Select Size', 'Seleccionar Talla', 'Size S (Small)', 'Talla S (Pequena)', 0.0, 'DOP', 1, 0), ('mod_yaha_17_1', 'yaha_17', 'Select Size', 'Seleccionar Talla', 'Size M (Medium)', 'Talla M (Mediana)', 0.0, 'DOP', 1, 1), ('mod_yaha_17_2', 'yaha_17', 'Select Size', 'Seleccionar Talla', 'Size L (Large)', 'Talla L (Grande)', 0.0, 'DOP', 1, 2), ('mod_yaha_17_3', 'yaha_17', 'Select Size', 'Seleccionar Talla', 'Size XL (Extra Large)', 'Talla XL (Extra Grande)', 0.0, 'DOP', 1, 3), ('mod_yaha_18_0', 'yaha_18', 'Select Size', 'Seleccionar Talla', 'Size S (Small)', 'Talla S (Pequena)', 0.0, 'DOP', 1, 0), ('mod_yaha_18_1', 'yaha_18', 'Select Size', 'Seleccionar Talla', 'Size M (Medium)', 'Talla M (Mediana)', 0.0, 'DOP', 1, 1), ('mod_yaha_18_2', 'yaha_18', 'Select Size', 'Seleccionar Talla', 'Size L (Large)', 'Talla L (Grande)', 0.0, 'DOP', 1, 2), ('mod_yaha_18_3', 'yaha_18', 'Select Size', 'Seleccionar Talla', 'Size XL (Extra Large)', 'Talla XL (Extra Grande)', 0.0, 'DOP', 1, 3), ('mod_yaha_19_0', 'yaha_19', 'Select Size', 'Seleccionar Talla', 'Size 1 / 26 (XS)', 'Talla 1 / 26 (XS)', 0.0, 'DOP', 1, 0), ('mod_yaha_19_1', 'yaha_19', 'Select Size', 'Seleccionar Talla', 'Size 3 / 28 (S)', 'Talla 3 / 28 (S)', 0.0, 'DOP', 1, 1), ('mod_yaha_19_2', 'yaha_19', 'Select Size', 'Seleccionar Talla', 'Size 5 / 30 (M)', 'Talla 5 / 30 (M)', 0.0, 'DOP', 1, 2), ('mod_yaha_19_3', 'yaha_19', 'Select Size', 'Seleccionar Talla', 'Size 7 / 32 (L)', 'Talla 7 / 32 (L)', 0.0, 'DOP', 1, 3), ('mod_yaha_19_4', 'yaha_19', 'Select Size', 'Seleccionar Talla', 'Size 9 / 34 (XL)', 'Talla 9 / 34 (XL)', 0.0, 'DOP', 1, 4), ('mod_yaha_20_0', 'yaha_20', 'Select Size', 'Seleccionar Talla', 'Size 1 / 26 (XS)', 'Talla 1 / 26 (XS)', 0.0, 'DOP', 1, 0), ('mod_yaha_20_1', 'yaha_20', 'Select Size', 'Seleccionar Talla', 'Size 3 / 28 (S)', 'Talla 3 / 28 (S)', 0.0, 'DOP', 1, 1), ('mod_yaha_20_2', 'yaha_20', 'Select Size', 'Seleccionar Talla', 'Size 5 / 30 (M)', 'Talla 5 / 30 (M)', 0.0, 'DOP', 1, 2), ('mod_yaha_20_3', 'yaha_20', 'Select Size', 'Seleccionar Talla', 'Size 7 / 32 (L)', 'Talla 7 / 32 (L)', 0.0, 'DOP', 1, 3), ('mod_yaha_20_4', 'yaha_20', 'Select Size', 'Seleccionar Talla', 'Size 9 / 34 (XL)', 'Talla 9 / 34 (XL)', 0.0, 'DOP', 1, 4), ('mod_yaha_21_0', 'yaha_21', 'Select Size', 'Seleccionar Talla', 'Size 1 / 26 (XS)', 'Talla 1 / 26 (XS)', 0.0, 'DOP', 1, 0), ('mod_yaha_21_1', 'yaha_21', 'Select Size', 'Seleccionar Talla', 'Size 3 / 28 (S)', 'Talla 3 / 28 (S)', 0.0, 'DOP', 1, 1), ('mod_yaha_21_2', 'yaha_21', 'Select Size', 'Seleccionar Talla', 'Size 5 / 30 (M)', 'Talla 5 / 30 (M)', 0.0, 'DOP', 1, 2), ('mod_yaha_21_3', 'yaha_21', 'Select Size', 'Seleccionar Talla', 'Size 7 / 32 (L)', 'Talla 7 / 32 (L)', 0.0, 'DOP', 1, 3), ('mod_yaha_21_4', 'yaha_21', 'Select Size', 'Seleccionar Talla', 'Size 9 / 34 (XL)', 'Talla 9 / 34 (XL)', 0.0, 'DOP', 1, 4), ('mod_yaha_22_0', 'yaha_22', 'Select Size', 'Seleccionar Talla', 'Size 1 / 26 (XS)', 'Talla 1 / 26 (XS)', 0.0, 'DOP', 1, 0), ('mod_yaha_22_1', 'yaha_22', 'Select Size', 'Seleccionar Talla', 'Size 3 / 28 (S)', 'Talla 3 / 28 (S)', 0.0, 'DOP', 1, 1), ('mod_yaha_22_2', 'yaha_22', 'Select Size', 'Seleccionar Talla', 'Size 5 / 30 (M)', 'Talla 5 / 30 (M)', 0.0, 'DOP', 1, 2), ('mod_yaha_22_3', 'yaha_22', 'Select Size', 'Seleccionar Talla', 'Size 7 / 32 (L)', 'Talla 7 / 32 (L)', 0.0, 'DOP', 1, 3), ('mod_yaha_22_4', 'yaha_22', 'Select Size', 'Seleccionar Talla', 'Size 9 / 34 (XL)', 'Talla 9 / 34 (XL)', 0.0, 'DOP', 1, 4), ('mod_yaha_23_0', 'yaha_23', 'Select Size', 'Seleccionar Talla', 'Size 1 / 26 (XS)', 'Talla 1 / 26 (XS)', 0.0, 'DOP', 1, 0), ('mod_yaha_23_1', 'yaha_23', 'Select Size', 'Seleccionar Talla', 'Size 3 / 28 (S)', 'Talla 3 / 28 (S)', 0.0, 'DOP', 1, 1), ('mod_yaha_23_2', 'yaha_23', 'Select Size', 'Seleccionar Talla', 'Size 5 / 30 (M)', 'Talla 5 / 30 (M)', 0.0, 'DOP', 1, 2), ('mod_yaha_23_3', 'yaha_23', 'Select Size', 'Seleccionar Talla', 'Size 7 / 32 (L)', 'Talla 7 / 32 (L)', 0.0, 'DOP', 1, 3), ('mod_yaha_23_4', 'yaha_23', 'Select Size', 'Seleccionar Talla', 'Size 9 / 34 (XL)', 'Talla 9 / 34 (XL)', 0.0, 'DOP', 1, 4), ('mod_yaha_24_0', 'yaha_24', 'Select Size', 'Seleccionar Talla', 'Size 1 / 26 (XS)', 'Talla 1 / 26 (XS)', 0.0, 'DOP', 1, 0), ('mod_yaha_24_1', 'yaha_24', 'Select Size', 'Seleccionar Talla', 'Size 3 / 28 (S)', 'Talla 3 / 28 (S)', 0.0, 'DOP', 1, 1), ('mod_yaha_24_2', 'yaha_24', 'Select Size', 'Seleccionar Talla', 'Size 5 / 30 (M)', 'Talla 5 / 30 (M)', 0.0, 'DOP', 1, 2), ('mod_yaha_24_3', 'yaha_24', 'Select Size', 'Seleccionar Talla', 'Size 7 / 32 (L)', 'Talla 7 / 32 (L)', 0.0, 'DOP', 1, 3), ('mod_yaha_24_4', 'yaha_24', 'Select Size', 'Seleccionar Talla', 'Size 9 / 34 (XL)', 'Talla 9 / 34 (XL)', 0.0, 'DOP', 1, 4), ('mod_yaha_25_0', 'yaha_25', 'Select Size', 'Seleccionar Talla', 'Size S (Small)', 'Talla S (Pequena)', 0.0, 'DOP', 1, 0), ('mod_yaha_25_1', 'yaha_25', 'Select Size', 'Seleccionar Talla', 'Size M (Medium)', 'Talla M (Mediana)', 0.0, 'DOP', 1, 1), ('mod_yaha_25_2', 'yaha_25', 'Select Size', 'Seleccionar Talla', 'Size L (Large)', 'Talla L (Grande)', 0.0, 'DOP', 1, 2), ('mod_yaha_26_0', 'yaha_26', 'Select Size', 'Seleccionar Talla', 'Size S (Small)', 'Talla S (Pequena)', 0.0, 'DOP', 1, 0), ('mod_yaha_26_1', 'yaha_26', 'Select Size', 'Seleccionar Talla', 'Size M (Medium)', 'Talla M (Mediana)', 0.0, 'DOP', 1, 1), ('mod_yaha_26_2', 'yaha_26', 'Select Size', 'Seleccionar Talla', 'Size L (Large)', 'Talla L (Grande)', 0.0, 'DOP', 1, 2), ('mod_yaha_26_3', 'yaha_26', 'Select Size', 'Seleccionar Talla', 'Size XL (Extra Large)', 'Talla XL (Extra Grande)', 0.0, 'DOP', 1, 3), ('mod_yaha_27_0', 'yaha_27', 'Select Size', 'Seleccionar Talla', 'Size S (Small)', 'Talla S (Pequena)', 0.0, 'DOP', 1, 0), ('mod_yaha_27_1', 'yaha_27', 'Select Size', 'Seleccionar Talla', 'Size M (Medium)', 'Talla M (Mediana)', 0.0, 'DOP', 1, 1), ('mod_yaha_27_2', 'yaha_27', 'Select Size', 'Seleccionar Talla', 'Size L (Large)', 'Talla L (Grande)', 0.0, 'DOP', 1, 2), ('mod_yaha_27_3', 'yaha_27', 'Select Size', 'Seleccionar Talla', 'Size XL (Extra Large)', 'Talla XL (Extra Grande)', 0.0, 'DOP', 1, 3), ('mod_yaha_28_0', 'yaha_28', 'Select Size', 'Seleccionar Talla', 'Size S (Small)', 'Talla S (Pequena)', 0.0, 'DOP', 1, 0), ('mod_yaha_28_1', 'yaha_28', 'Select Size', 'Seleccionar Talla', 'Size M (Medium)', 'Talla M (Mediana)', 0.0, 'DOP', 1, 1), ('mod_yaha_28_2', 'yaha_28', 'Select Size', 'Seleccionar Talla', 'Size L (Large)', 'Talla L (Grande)', 0.0, 'DOP', 1, 2), ('mod_yaha_28_3', 'yaha_28', 'Select Size', 'Seleccionar Talla', 'Size XL (Extra Large)', 'Talla XL (Extra Grande)', 0.0, 'DOP', 1, 3), ('mod_yaha_29_0', 'yaha_29', 'Select Size', 'Seleccionar Talla', 'Size S (Small)', 'Talla S (Pequena)', 0.0, 'DOP', 1, 0), ('mod_yaha_29_1', 'yaha_29', 'Select Size', 'Seleccionar Talla', 'Size M (Medium)', 'Talla M (Mediana)', 0.0, 'DOP', 1, 1), ('mod_yaha_29_2', 'yaha_29', 'Select Size', 'Seleccionar Talla', 'Size L (Large)', 'Talla L (Grande)', 0.0, 'DOP', 1, 2), ('mod_yaha_29_3', 'yaha_29', 'Select Size', 'Seleccionar Talla', 'Size XL (Extra Large)', 'Talla XL (Extra Grande)', 0.0, 'DOP', 1, 3), ('mod_yaha_30_0', 'yaha_30', 'Select Size', 'Seleccionar Talla', 'Size S (Small)', 'Talla S (Pequena)', 0.0, 'DOP', 1, 0), ('mod_yaha_30_1', 'yaha_30', 'Select Size', 'Seleccionar Talla', 'Size M (Medium)', 'Talla M (Mediana)', 0.0, 'DOP', 1, 1), ('mod_yaha_30_2', 'yaha_30', 'Select Size', 'Seleccionar Talla', 'Size L (Large)', 'Talla L (Grande)', 0.0, 'DOP', 1, 2), ('mod_yaha_30_3', 'yaha_30', 'Select Size', 'Seleccionar Talla', 'Size XL (Extra Large)', 'Talla XL (Extra Grande)', 0.0, 'DOP', 1, 3), ('mod_yaha_31_0', 'yaha_31', 'Select Size', 'Seleccionar Talla', 'Size S (Small)', 'Talla S (Pequena)', 0.0, 'DOP', 1, 0), ('mod_yaha_31_1', 'yaha_31', 'Select Size', 'Seleccionar Talla', 'Size M (Medium)', 'Talla M (Mediana)', 0.0, 'DOP', 1, 1), ('mod_yaha_31_2', 'yaha_31', 'Select Size', 'Seleccionar Talla', 'Size L (Large)', 'Talla L (Grande)', 0.0, 'DOP', 1, 2), ('mod_yaha_31_3', 'yaha_31', 'Select Size', 'Seleccionar Talla', 'Size XL (Extra Large)', 'Talla XL (Extra Grande)', 0.0, 'DOP', 1, 3), ('mod_yaha_32_0', 'yaha_32', 'Select Size', 'Seleccionar Talla', 'Size S (Small)', 'Talla S (Pequena)', 0.0, 'DOP', 1, 0), ('mod_yaha_32_1', 'yaha_32', 'Select Size', 'Seleccionar Talla', 'Size M (Medium)', 'Talla M (Mediana)', 0.0, 'DOP', 1, 1), ('mod_yaha_32_2', 'yaha_32', 'Select Size', 'Seleccionar Talla', 'Size L (Large)', 'Talla L (Grande)', 0.0, 'DOP', 1, 2), ('mod_yaha_32_3', 'yaha_32', 'Select Size', 'Seleccionar Talla', 'Size XL (Extra Large)', 'Talla XL (Extra Grande)', 0.0, 'DOP', 1, 3), ('mod_yaha_33_0', 'yaha_33', 'Select Size', 'Seleccionar Talla', 'Size S (Small)', 'Talla S (Pequena)', 0.0, 'DOP', 1, 0), ('mod_yaha_33_1', 'yaha_33', 'Select Size', 'Seleccionar Talla', 'Size M (Medium)', 'Talla M (Mediana)', 0.0, 'DOP', 1, 1), ('mod_yaha_33_2', 'yaha_33', 'Select Size', 'Seleccionar Talla', 'Size L (Large)', 'Talla L (Grande)', 0.0, 'DOP', 1, 2), ('mod_yaha_33_3', 'yaha_33', 'Select Size', 'Seleccionar Talla', 'Size XL (Extra Large)', 'Talla XL (Extra Grande)', 0.0, 'DOP', 1, 3), ('mod_yaha_34_0', 'yaha_34', 'Select Size', 'Seleccionar Talla', 'Size S (Small)', 'Talla S (Pequena)', 0.0, 'DOP', 1, 0), ('mod_yaha_34_1', 'yaha_34', 'Select Size', 'Seleccionar Talla', 'Size M (Medium)', 'Talla M (Mediana)', 0.0, 'DOP', 1, 1), ('mod_yaha_34_2', 'yaha_34', 'Select Size', 'Seleccionar Talla', 'Size L (Large)', 'Talla L (Grande)', 0.0, 'DOP', 1, 2), ('mod_yaha_34_3', 'yaha_34', 'Select Size', 'Seleccionar Talla', 'Size XL (Extra Large)', 'Talla XL (Extra Grande)', 0.0, 'DOP', 1, 3), ('mod_yaha_35_0', 'yaha_35', 'Select Size', 'Seleccionar Talla', 'Size S (Small)', 'Talla S (Pequena)', 0.0, 'DOP', 1, 0), ('mod_yaha_35_1', 'yaha_35', 'Select Size', 'Seleccionar Talla', 'Size M (Medium)', 'Talla M (Mediana)', 0.0, 'DOP', 1, 1), ('mod_yaha_35_2', 'yaha_35', 'Select Size', 'Seleccionar Talla', 'Size L (Large)', 'Talla L (Grande)', 0.0, 'DOP', 1, 2), ('mod_yaha_35_3', 'yaha_35', 'Select Size', 'Seleccionar Talla', 'Size XL (Extra Large)', 'Talla XL (Extra Grande)', 0.0, 'DOP', 1, 3), ('mod_yaha_36_0', 'yaha_36', 'Select Size', 'Seleccionar Talla', 'Size S (Small)', 'Talla S (Pequena)', 0.0, 'DOP', 1, 0), ('mod_yaha_36_1', 'yaha_36', 'Select Size', 'Seleccionar Talla', 'Size M (Medium)', 'Talla M (Mediana)', 0.0, 'DOP', 1, 1), ('mod_yaha_36_2', 'yaha_36', 'Select Size', 'Seleccionar Talla', 'Size L (Large)', 'Talla L (Grande)', 0.0, 'DOP', 1, 2), ('mod_yaha_36_3', 'yaha_36', 'Select Size', 'Seleccionar Talla', 'Size XL (Extra Large)', 'Talla XL (Extra Grande)', 0.0, 'DOP', 1, 3), ('mod_yaha_37_0', 'yaha_37', 'Select Size', 'Seleccionar Talla', 'Size S (Small)', 'Talla S (Pequena)', 0.0, 'DOP', 1, 0), ('mod_yaha_37_1', 'yaha_37', 'Select Size', 'Seleccionar Talla', 'Size M (Medium)', 'Talla M (Mediana)', 0.0, 'DOP', 1, 1), ('mod_yaha_37_2', 'yaha_37', 'Select Size', 'Seleccionar Talla', 'Size L (Large)', 'Talla L (Grande)', 0.0, 'DOP', 1, 2), ('mod_yaha_37_3', 'yaha_37', 'Select Size', 'Seleccionar Talla', 'Size XL (Extra Large)', 'Talla XL (Extra Grande)', 0.0, 'DOP', 1, 3), ('mod_yaha_38_0', 'yaha_38', 'Select Size', 'Seleccionar Talla', 'Size S (Small)', 'Talla S (Pequena)', 0.0, 'DOP', 1, 0), ('mod_yaha_38_1', 'yaha_38', 'Select Size', 'Seleccionar Talla', 'Size M (Medium)', 'Talla M (Mediana)', 0.0, 'DOP', 1, 1), ('mod_yaha_38_2', 'yaha_38', 'Select Size', 'Seleccionar Talla', 'Size L (Large)', 'Talla L (Grande)', 0.0, 'DOP', 1, 2), ('mod_yaha_38_3', 'yaha_38', 'Select Size', 'Seleccionar Talla', 'Size XL (Extra Large)', 'Talla XL (Extra Grande)', 0.0, 'DOP', 1, 3), ('mod_yaha_39_0', 'yaha_39', 'Select Size', 'Seleccionar Talla', 'Size S (Small)', 'Talla S (Pequena)', 0.0, 'DOP', 1, 0), ('mod_yaha_39_1', 'yaha_39', 'Select Size', 'Seleccionar Talla', 'Size M (Medium)', 'Talla M (Mediana)', 0.0, 'DOP', 1, 1), ('mod_yaha_39_2', 'yaha_39', 'Select Size', 'Seleccionar Talla', 'Size L (Large)', 'Talla L (Grande)', 0.0, 'DOP', 1, 2), ('mod_yaha_39_3', 'yaha_39', 'Select Size', 'Seleccionar Talla', 'Size XL (Extra Large)', 'Talla XL (Extra Grande)', 0.0, 'DOP', 1, 3), ('mod_yaha_40_0', 'yaha_40', 'Select Size', 'Seleccionar Talla', 'Size S (Small)', 'Talla S (Pequena)', 0.0, 'DOP', 1, 0), ('mod_yaha_40_1', 'yaha_40', 'Select Size', 'Seleccionar Talla', 'Size M (Medium)', 'Talla M (Mediana)', 0.0, 'DOP', 1, 1), ('mod_yaha_40_2', 'yaha_40', 'Select Size', 'Seleccionar Talla', 'Size L (Large)', 'Talla L (Grande)', 0.0, 'DOP', 1, 2), ('mod_yaha_40_3', 'yaha_40', 'Select Size', 'Seleccionar Talla', 'Size XL (Extra Large)', 'Talla XL (Extra Grande)', 0.0, 'DOP', 1, 3), ('mod_yaha_41_0', 'yaha_41', 'Select Size', 'Seleccionar Talla', 'Size S (Small)', 'Talla S (Pequena)', 0.0, 'DOP', 1, 0), ('mod_yaha_41_1', 'yaha_41', 'Select Size', 'Seleccionar Talla', 'Size M (Medium)', 'Talla M (Mediana)', 0.0, 'DOP', 1, 1), ('mod_yaha_41_2', 'yaha_41', 'Select Size', 'Seleccionar Talla', 'Size L (Large)', 'Talla L (Grande)', 0.0, 'DOP', 1, 2), ('mod_yaha_41_3', 'yaha_41', 'Select Size', 'Seleccionar Talla', 'Size XL (Extra Large)', 'Talla XL (Extra Grande)', 0.0, 'DOP', 1, 3), ('mod_yaha_42_0', 'yaha_42', 'Select Size', 'Seleccionar Talla', 'Size S (Small)', 'Talla S (Pequena)', 0.0, 'DOP', 1, 0), ('mod_yaha_42_1', 'yaha_42', 'Select Size', 'Seleccionar Talla', 'Size M (Medium)', 'Talla M (Mediana)', 0.0, 'DOP', 1, 1), ('mod_yaha_42_2', 'yaha_42', 'Select Size', 'Seleccionar Talla', 'Size L (Large)', 'Talla L (Grande)', 0.0, 'DOP', 1, 2), ('mod_yaha_42_3', 'yaha_42', 'Select Size', 'Seleccionar Talla', 'Size XL (Extra Large)', 'Talla XL (Extra Grande)', 0.0, 'DOP', 1, 3), ('mod_yaha_43_0', 'yaha_43', 'Select Size', 'Seleccionar Talla', 'Size S (Small)', 'Talla S (Pequena)', 0.0, 'DOP', 1, 0), ('mod_yaha_43_1', 'yaha_43', 'Select Size', 'Seleccionar Talla', 'Size M (Medium)', 'Talla M (Mediana)', 0.0, 'DOP', 1, 1), ('mod_yaha_43_2', 'yaha_43', 'Select Size', 'Seleccionar Talla', 'Size L (Large)', 'Talla L (Grande)', 0.0, 'DOP', 1, 2), ('mod_yaha_43_3', 'yaha_43', 'Select Size', 'Seleccionar Talla', 'Size XL (Extra Large)', 'Talla XL (Extra Grande)', 0.0, 'DOP', 1, 3)]
    for mid, miid, g_en, g_es, men, mes, pdelta, mcurr, mreq, msort in boutique_mods:
        cur.execute("""INSERT OR REPLACE INTO menu_modifiers (id, menu_item_id, group_name_en, group_name_es, name_en, name_es, price_delta, currency, is_required, sort_order)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (mid, miid, g_en, g_es, men, mes, pdelta, mcurr, mreq, msort))

    # -------------------------------------------------------------
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

    conn.commit()
    conn.close()
    print("Database successfully initialized and seeded with Sosúa pilot data!")

if __name__ == "__main__":
    db_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "mavunqo.db")
    seed_database(db_file)
