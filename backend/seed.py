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
    # Clothing Store: Yaha Style RD
    # -------------------------------------------------------------
    cloth_owner = "user_clothe_yahaira"
    cur.execute("SELECT id FROM users WHERE email = 'yahastylerd@gmail.com' OR email = 'yahaira@tropicalwavesboutique.com'")
    if not cur.fetchone():
        cur.execute(
            """INSERT INTO users (id, email, password_hash, full_name, role)
               VALUES (?, ?, ?, ?, ?)""",
            (cloth_owner, "yahastylerd@gmail.com", hash_password("YahaStyle2026!"), "Yahaira Garcia", "owner")
        )

    b_clothe = "biz_yaha_style_rd"
    cur.execute("SELECT id FROM businesses WHERE id = ? OR slug = 'yaha-style-rd'", (b_clothe,))
    if not cur.fetchone():
        cur.execute(
            """INSERT INTO businesses (
                id, owner_id, trading_name, legal_name, slug, category_id, primary_location_id,
                description_en, description_es, status, has_physical_location, address,
                serves_entire_area, website_url, whatsapp, phone, public_email,
                hours_json, rnc_tax_id, rnc_status, approved_by, approved_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)""",
            (
                b_clothe, cloth_owner, "Yaha Style RD", "Yaha Style RD - Yahaira Garcia",
                "yaha-style-rd", "cat_fashion", "loc_sosua",
                "Coastal beachwear, rashguards, tropical summer linen dresses, swimsuits, sun hats, and surf accessories on Calle Pedro Clisante in Sosua.",
                "Boutique de ropa playera, vestidos frescos de lino caribeño, trajes de baño, sombreros y licras de surf en Calle Pedro Clisante.",
                "approved", 1, "Calle Pedro Clisante #28, El Batey, Sosúa",
                1, None, "+18296414722", "+18296414722", "orders@tropicalwavesboutique.com",
                json.dumps({"monday_saturday": "9:30 AM - 8:00 PM", "sunday": "10:00 AM - 4:00 PM"}),
                "131-44781-9", "verified", admin_id
            )
        )
        cur.execute("INSERT OR IGNORE INTO business_service_areas (business_id, location_id) VALUES (?, ?)", (b_clothe, "loc_sosua"))
        cur.execute("INSERT OR IGNORE INTO business_service_areas (business_id, location_id) VALUES (?, ?)", (b_clothe, "loc_cabarete"))

        cat_swim = "ccat_swimwear"
        cat_linen = "ccat_linen_apparel"
        cur.execute("INSERT INTO menu_categories (id, business_id, name_en, name_es, sort_order) VALUES (?, ?, ?, ?, ?)",
                    (cat_swim, b_clothe, "Swimwear & Boardshorts", "Trajes de Baño y Bañadores", 1))
        cur.execute("INSERT INTO menu_categories (id, business_id, name_en, name_es, sort_order) VALUES (?, ?, ?, ?, ?)",
                    (cat_linen, b_clothe, "Linen Dresses & Beach Shirts", "Vestidos de Lino y Camisas Playeras", 2))

        # Catalog items
        cur.execute("""INSERT INTO menu_items (id, business_id, category_id, name_en, name_es, description_en, description_es, price, currency, is_available, sort_order)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'DOP', 1, 1)""",
                    ("item_linen_shirt", b_clothe, cat_linen, "Caribbean White Linen Beach Shirt", "Camisa Playera de Lino Blanco",
                     "Breathable 100% natural linen short-sleeve button-down shirt. Perfect for hot coastal days.",
                     "Camisa de botones 100% lino blanco natural, fresca y elegante para el clima caribeño.", 1850.0))

        cur.execute("""INSERT INTO menu_items (id, business_id, category_id, name_en, name_es, description_en, description_es, price, currency, is_available, sort_order)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'DOP', 1, 2)""",
                    ("item_floral_dress", b_clothe, cat_linen, "Tropical Maxi Sun Dress", "Vestido Maxi Tropical de Playa",
                     "Flowy Caribbean floral-print summer dress with adjustable straps.",
                     "Vestido largo veraniego estampado tropical con tirantes ajustables.", 1950.0))

        cur.execute("""INSERT INTO menu_items (id, business_id, category_id, name_en, name_es, description_en, description_es, price, currency, is_available, sort_order)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'DOP', 1, 1)""",
                    ("item_boardshorts", b_clothe, cat_swim, "Quick-Dry Performance Boardshorts", "Bañador Boardshort de Secado Rápido",
                     "Durable stretch surf boardshorts with secure zip pocket.",
                     "Bañador elástico resistente para surf y playa con bolsillo de cremallera.", 1450.0))

        cur.execute("""INSERT INTO menu_items (id, business_id, category_id, name_en, name_es, description_en, description_es, price, currency, is_available, sort_order)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'DOP', 1, 2)""",
                    ("item_straw_hat", b_clothe, cat_swim, "Handwoven Dominican Palm Sun Hat", "Sombrero Playero Tejido en Palma",
                     "UV protective wide-brim handwoven beach hat.",
                     "Sombrero artesanal de ala ancha con protección solar UV.", 750.0))

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
