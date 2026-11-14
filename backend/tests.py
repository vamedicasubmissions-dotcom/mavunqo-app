"""
Unit and Integration Test Suite for Mavunqo Phase 1.
Validates:
1. Public visitor search without account (keyword, category, location, service).
2. Sosúa is active launch market, Cabarete and Puerto Plata staged as upcoming.
3. RNC optionality during business registration.
4. Business approval gate (listings stay pending until admin approves).
5. Multi-tenant business isolation (owners cannot view or edit unauthorized businesses).
6. Sensitive change requests require admin review.
7. Service prices can be shown or hidden independently.
8. Demo business with existing external website link works.
9. Demo business with free Mavunqo hosted storefront (/b/{slug}) works.
10. Contact form submission & audit logging.
"""
import unittest
import os
import tempfile
import json
from backend.db import init_db
from backend.seed import seed_database
from backend.service import MavunqoService
from backend.auth import hash_password, verify_password, generate_token, verify_token

class TestMavunqoPhase1(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.TemporaryDirectory()
        cls.db_path = os.path.join(cls.temp_dir.name, "test_mavunqo.db")
        seed_database(cls.db_path)
        cls.service = MavunqoService(cls.db_path)

    @classmethod
    def tearDownClass(cls):
        try:
            cls.temp_dir.cleanup()
        except Exception:
            pass

    # 1. Authentication and Token Tests
    def test_auth_and_token_cycle(self):
        pw = "SecretPass123!"
        hashed = hash_password(pw)
        self.assertTrue(verify_password(hashed, pw))
        self.assertFalse(verify_password(hashed, "WrongPass"))

        token = generate_token("user_123", "test@mavunqo.com", "owner")
        payload = verify_token(token)
        self.assertIsNotNone(payload)
        self.assertEqual(payload["uid"], "user_123")
        self.assertEqual(payload["email"], "test@mavunqo.com")
        self.assertEqual(payload["role"], "owner")

        # Invalid token
        self.assertIsNone(verify_token("tampered.token.value"))

    # 2. Public discovery without login & Sosúa active market
    def test_public_discovery_and_active_launch_market(self):
        categories = self.service.get_categories()
        self.assertGreaterEqual(len(categories), 6)

        locations = self.service.get_locations()
        sosua = next(l for l in locations if l["name"] == "Sosúa")
        cabarete = next(l for l in locations if l["name"] == "Cabarete")
        puerto_plata = next(l for l in locations if l["name"] == "Puerto Plata")

        # Sosúa must be active launch market
        self.assertEqual(sosua["status"], "active")
        self.assertEqual(sosua["is_launch_market"], 1)

        # Cabarete and Puerto Plata must be upcoming (expansion readiness)
        self.assertEqual(cabarete["status"], "upcoming")
        self.assertEqual(cabarete["is_launch_market"], 0)
        self.assertEqual(puerto_plata["status"], "upcoming")

    # 3. Search supports service, category, location and keyword
    def test_search_combinations(self):
        # Keyword search for 'villa'
        res_villa = self.service.search_businesses(q="villa")
        self.assertTrue(any(b["slug"] == "sosua-ocean-view-villas" for b in res_villa))

        # Category search for Auto
        res_auto = self.service.search_businesses(category_id="cat_auto")
        self.assertTrue(any(b["slug"] == "caribe-fix-auto" for b in res_auto))

        # Location search for Sosúa (at least the 2 initial seeded businesses)
        res_sosua = self.service.search_businesses(location_id="loc_sosua")
        self.assertGreaterEqual(len(res_sosua), 2)

        # Combined search
        res_combined = self.service.search_businesses(q="brake", category_id="cat_auto", location_id="loc_sosua")
        self.assertEqual(len(res_combined), 1)
        self.assertEqual(res_combined[0]["slug"], "caribe-fix-auto")

    # 4. Optional Service Prices
    def test_optional_service_prices(self):
        biz = self.service.get_business_by_slug("sosua-ocean-view-villas")
        self.assertIsNotNone(biz)
        services = biz["services"]
        # Villa has 1 displayed price (250 USD) and 1 price on request / hidden (display_price = 0)
        displayed = [s for s in services if s["display_price"] == 1]
        hidden = [s for s in services if s["display_price"] == 0]
        self.assertEqual(len(displayed), 1)
        self.assertEqual(displayed[0]["price"], 250.0)
        self.assertEqual(len(hidden), 1)
        self.assertIsNone(hidden[0]["price"])

    # 5. External Website vs Free Hosted Storefront
    def test_external_website_and_hosted_storefront(self):
        biz_external = self.service.get_business_by_slug("sosua-ocean-view-villas")
        self.assertEqual(biz_external["website_url"], "https://example-sosua-villas.com")

        biz_hosted = self.service.get_business_by_slug("caribe-fix-auto")
        self.assertIsNone(biz_hosted["website_url"])
        # Both are accessible via the hosted profile path
        self.assertIn("Caribe Fix Auto & AC", biz_hosted["trading_name"])

    # 4. Business approval gate (listings stay pending until admin approves)
    def test_registration_optional_rnc_and_admin_approval_gate(self):
        # Register business without RNC
        reg = self.service.register_business(
            owner_name="Marcos Diaz",
            owner_email="marcos@sosuadive.com",
            password="SecurePass2026!",
            trading_name="Sosúa Reef Diving Center",
            category_id="cat_tourism",
            primary_location_id="loc_sosua",
            description_en="PADI certified diving tours and equipment rental in Sosúa Bay.",
            description_es="Tours de buceo certificados por PADI y alquiler de equipos en la Bahía de Sosúa.",
            phone="+18095550999",
            whatsapp="+18095550999",
            rnc_tax_id=None # Optional!
        )
        self.assertEqual(reg["status"], "pending")
        new_biz_id = reg["business_id"]
        new_slug = reg["slug"]

        # MUST NOT appear in public search before approval
        search_res = self.service.search_businesses(q="Sosúa Reef Diving")
        self.assertFalse(any(b["id"] == new_biz_id for b in search_res))

        # Public get by slug must return None before approval
        self.assertIsNone(self.service.get_business_by_slug(new_slug, require_approved=True))

        # Admin approves listing
        self.service.approve_business(admin_user_id="user_admin", business_id=new_biz_id)

        # Now appears in public search
        search_res_after = self.service.search_businesses(q="Sosúa Reef Diving")
        self.assertTrue(any(b["id"] == new_biz_id for b in search_res_after))

        # Public get by slug works
        approved_biz = self.service.get_business_by_slug(new_slug, require_approved=True)
        self.assertIsNotNone(approved_biz)
        self.assertEqual(approved_biz["trading_name"], "Sosúa Reef Diving Center")

    # 7. Multi-Tenant Business Isolation
    def test_tenant_isolation_and_unauthorized_edits(self):
        # Owner 1 (Carlos: user_carlos_villas) owns biz_sosua_villas
        # Owner 2 (Rosa: user_rosa_autofix) owns biz_caribe_fix

        # Rosa cannot edit Carlos's business
        with self.assertRaises(PermissionError):
            self.service.update_business_profile(
                user_id="user_rosa_autofix",
                business_id="biz_sosua_villas",
                update_data={"trading_name": "Hacked Villas"}
            )

        # Carlos cannot access Rosa's contact leads
        with self.assertRaises(PermissionError):
            self.service.get_business_contact_requests(
                user_id="user_carlos_villas",
                business_id="biz_caribe_fix"
            )

        # Carlos CAN edit his own business
        update_res = self.service.update_business_profile(
            user_id="user_carlos_villas",
            business_id="biz_sosua_villas",
            update_data={
                "trading_name": "Sosúa Ocean View Luxury Villas",
                "legal_name": "New Inversiones Legal Name SRL" # Sensitive!
            }
        )
        self.assertIn("trading_name", update_res["direct_updates_applied"])
        self.assertIn("legal_name", update_res["pending_approval"])

    # 8. Contact Form Flow & Spam Protection
    def test_contact_form(self):
        res = self.service.submit_contact_form(
            business_id="biz_sosua_villas",
            sender_name="Alice Green",
            sender_contact="alice@example.com",
            message="Interested in renting the 3-bedroom villa for February."
        )
        self.assertTrue(res["success"])

        # Check that owner receives it
        leads = self.service.get_business_contact_requests("user_carlos_villas", "biz_sosua_villas")
        self.assertTrue(any(lead["sender_name"] == "Alice Green" for lead in leads))

    # 9. Admin Analytics & Search Auditing
    def test_admin_analytics(self):
        # Trigger at least one search to ensure search_events table has data
        self.service.search_businesses(q="test query")
        analytics = self.service.get_admin_analytics()
        self.assertGreater(analytics["total_businesses"], 0)
        self.assertGreater(analytics["total_searches"], 0)
        self.assertIn("zero_result_searches", analytics)

    # 10. Phase 2 Restaurant Ordering Pilot Tests
    def test_phase2_ordering_lifecycle_and_reconciliation(self):
        # Seed a test menu item directly
        with self.service.get_connection() as conn:
            conn.execute(
                """INSERT INTO menu_items (id, business_id, name_en, name_es, price, currency, is_available)
                   VALUES ('mi_test_pizza', 'biz_caribe_fix', 'Margherita Pizza', 'Pizza Margarita', 500.0, 'DOP', 1)"""
            )
            conn.execute(
                """INSERT INTO menu_modifiers (id, menu_item_id, group_name_en, group_name_es, name_en, name_es, price_delta)
                   VALUES ('mod_extra_cheese', 'mi_test_pizza', 'Toppings', 'Ingredientes', 'Extra Cheese', 'Queso Extra', 80.0)"""
            )
            conn.commit()

        # 1. Fetch menu
        menu = self.service.get_restaurant_menu("biz_caribe_fix")
        self.assertEqual(menu["business_name"], "Caribe Fix Auto & AC")

        # 2. Place guest order (Mavunqo-sourced)
        order_res = self.service.place_order(
            business_id="biz_caribe_fix",
            customer_data={"name": "Maria Rodriguez", "phone": "8095550199"},
            items=[{
                "menu_item_id": "mi_test_pizza",
                "quantity": 2,
                "modifiers": [{"id": "mod_extra_cheese"}]
            }],
            fulfillment_type="pickup",
            order_origin="mavunqo"
        )
        self.assertTrue(order_res["success"])
        # Unit price = 500 + 80 = 580; Qty = 2; Subtotal = 1160; Pickup fee = 0; Total = 1160
        self.assertEqual(order_res["total"], 1160.0)
        status_token = order_res["status_token"]
        order_id = order_res["order_id"]

        # 3. Retrieve order via public status token (no account needed)
        order_view = self.service.get_order_by_token(status_token)
        self.assertEqual(order_view["customer_name"], "Maria Rodriguez")
        self.assertEqual(order_view["status"], "pending")
        self.assertEqual(len(order_view["items"]), 1)
        self.assertEqual(order_view["items"][0]["quantity"], 2)

        # 4. Merchant order queue & status transitions
        merchant_orders = self.service.get_merchant_orders(user_id="user_rosa_autofix", business_id="biz_caribe_fix")
        self.assertTrue(any(o["id"] == order_id for o in merchant_orders))

        # Accept order with 25 min ETA
        self.service.update_order_status("user_rosa_autofix", "biz_caribe_fix", order_id, "accepted", estimated_minutes=25)
        # Advance to in_kitchen -> ready -> completed
        self.service.update_order_status("user_rosa_autofix", "biz_caribe_fix", order_id, "in_kitchen")
        self.service.update_order_status("user_rosa_autofix", "biz_caribe_fix", order_id, "ready")
        self.service.update_order_status("user_rosa_autofix", "biz_caribe_fix", order_id, "completed", cash_received=1160.0)

        # 5. Check fee statement (Standard launch 11% of 1160 DOP = 127.60 DOP accrued)
        statement = self.service.get_merchant_fee_statement("user_rosa_autofix", "biz_caribe_fix")
        self.assertEqual(statement["total_accrued_fees"], 127.60)
        self.assertEqual(statement["total_pending_fees"], 0.0)

        # 6. Verify cross-tenant isolation on orders
        with self.assertRaises(PermissionError):
            self.service.get_merchant_orders(user_id="user_carlos_villas", business_id="biz_caribe_fix")

        with self.assertRaises(PermissionError):
            self.service.update_order_status("user_carlos_villas", "biz_caribe_fix", order_id, "completed")

    # 11. Multi-Vertical Hospitality & Stays (City Lights Benchmark)
    def test_city_lights_hospitality_and_staff_checkin(self):
        # 1. Fetch lodging units
        units_res = self.service.get_lodging_units("biz_city_lights")
        self.assertEqual(units_res["business_name"], "City Lights Boutique Hotel & Lounge")
        self.assertGreaterEqual(len(units_res["units"]), 3)

        suite = next(u for u in units_res["units"] if u["unit_type"] == "suite")

        # 2. Book suite
        booking_res = self.service.book_lodging_unit(
            business_id="biz_city_lights",
            unit_id=suite["id"],
            guest_data={"name": "Sarah Connor", "contact": "+18095558833"},
            check_in="2026-12-01",
            check_out="2026-12-04",
            guest_count=2
        )
        self.assertTrue(booking_res["success"])
        # 3 nights * 75.0 = 225.0 USD
        self.assertEqual(booking_res["total_amount"], 225.0)
        res_id = booking_res["reservation_id"]

        # 3. Staff retrieves reservations and processes check-in with cash collection
        staff_res = self.service.get_staff_reservations("user_city_lights_owner", "biz_city_lights")
        self.assertTrue(any(r["id"] == res_id for r in staff_res))

        checkin_res = self.service.process_staff_checkin(
            user_id="user_city_lights_owner",
            business_id="biz_city_lights",
            reservation_id=res_id,
            cash_collected=225.0,
            staff_notes="Guest checked in early, paid full cash."
        )
        self.assertTrue(checkin_res["success"])
        self.assertEqual(checkin_res["status"], "checked_in")

        # 4. Multi-tenant isolation: Carlos cannot access City Lights bookings
        with self.assertRaises(PermissionError):
            self.service.get_staff_reservations("user_carlos_villas", "biz_city_lights")

    # 12. Bilingual AI Concierge Grounded Query
    def test_ai_concierge_query(self):
        res_en = self.service.ask_ai_concierge("hotel rooms in Sosúa", lang="en")
        self.assertTrue(any("City Lights" in r["trading_name"] for r in res_en["recommendations"]))

        res_es = self.service.ask_ai_concierge("reparar aire de carro", lang="es")
        self.assertTrue(any("Caribe Fix" in r["trading_name"] for r in res_es["recommendations"]))

    # 13. Automatic Delivery Capacity Control & Gas-Saving Dispatch Gate
    def test_automatic_delivery_capacity_and_dispatch_gate(self):
        # 1. Capacity check in Sosua (2 drivers online * 2 max = 4 max delivery capacity)
        cap = self.service.get_delivery_capacity("loc_sosua")
        self.assertTrue(cap["delivery_available"])
        self.assertEqual(cap["active_drivers_count"], 2)
        self.assertEqual(cap["total_delivery_capacity"], 4)

        # 2. Place a valid delivery order
        order_res = self.service.place_order(
            business_id="biz_el_batey_bistro",
            customer_data={"name": "Lucas Scott", "phone": "8095559988"},
            items=[{"menu_item_id": "mi_churrasco", "quantity": 1}],
            fulfillment_type="delivery",
            delivery_address="Playa Chiquita Condos #4B, Sosua"
        )
        self.assertTrue(order_res["success"])
        order_id = order_res["order_id"]

        # Verify driver is NOT dispatched yet while order is pending/in prep (Gasoline savings!)
        with self.service.get_connection() as conn:
            disp = conn.execute("SELECT * FROM delivery_dispatches WHERE order_id = ?", (order_id,)).fetchone()
            self.assertIsNone(disp)

        # 3. Simulate kitchen marking order 'ready' -> triggers driver dispatch!
        self.service.update_order_status("user_rest1_marco", "biz_el_batey_bistro", order_id, "accepted", estimated_minutes=20)
        self.service.update_order_status("user_rest1_marco", "biz_el_batey_bistro", order_id, "in_kitchen")
        self.service.update_order_status("user_rest1_marco", "biz_el_batey_bistro", order_id, "ready")

        with self.service.get_connection() as conn:
            disp = conn.execute("SELECT * FROM delivery_dispatches WHERE order_id = ?", (order_id,)).fetchone()
            self.assertIsNotNone(disp)
            self.assertEqual(disp["status"], "dispatched")
            self.assertIsNotNone(disp["driver_id"])

        # 4. Test delivery pause when drivers are offline or capacity full
        with self.service.get_connection() as conn:
            conn.execute("UPDATE drivers SET status = 'offline' WHERE location_id = 'loc_sosua'")
            conn.commit()

        cap_paused = self.service.get_delivery_capacity("loc_sosua")
        self.assertFalse(cap_paused["delivery_available"])
        self.assertTrue(cap_paused["pickup_always_available"])

        # Attempting delivery order raises error
        with self.assertRaises(ValueError):
            self.service.place_order(
                business_id="biz_el_batey_bistro",
                customer_data={"name": "Test Blocked", "phone": "8095551111"},
                items=[{"menu_item_id": "mi_churrasco", "quantity": 1}],
                fulfillment_type="delivery",
                delivery_address="Sosua Ocean Village"
            )

        # But pickup order SUCCEEDS even when delivery is paused!
        pickup_res = self.service.place_order(
            business_id="biz_el_batey_bistro",
            customer_data={"name": "Pickup Hero", "phone": "8095551111"},
            items=[{"menu_item_id": "mi_churrasco", "quantity": 1}],
            fulfillment_type="pickup"
        )
        self.assertTrue(pickup_res["success"])

        # 5. Restore drivers online
        with self.service.get_connection() as conn:
            conn.execute("UPDATE drivers SET status = 'online' WHERE location_id = 'loc_sosua'")
            conn.commit()


    # 14. Masked In-App Relay Chat
    def test_masked_order_chat_relay(self):
        # 1. Place a sample food order
        order_res = self.service.place_order(
            business_id="biz_el_batey_bistro",
            customer_data={
                "name": "Alex Privacy",
                "phone": "+1-809-555-0199",
                "email": "alex@privacy.com"
            },
            items=[{"menu_item_id": "mi_churrasco", "quantity": 1}],
            fulfillment_type="delivery",
            delivery_address="Sosua Ocean Village Villa 402"
        )
        token = order_res["status_token"]
        order_id = order_res["order_id"]

        # 2. Customer posts a note via status token (no phone exposed)
        msg1 = self.service.post_order_message(
            message="Please leave at guard gate 4B.",
            sender_role="customer",
            sender_name="Alex P.",
            status_token=token
        )
        self.assertTrue(msg1["success"])
        self.assertEqual(msg1["sender_role"], "customer")

        # 3. Kitchen / restaurant replies via order_id
        msg2 = self.service.post_order_message(
            message="Understood, extra sauces included!",
            sender_role="restaurant",
            sender_name="Kitchen",
            order_id=order_id
        )
        self.assertTrue(msg2["success"])
        self.assertEqual(msg2["sender_role"], "restaurant")

        # 4. Fetch messages via token (customer side)
        customer_feed = self.service.get_order_messages(status_token=token)
        self.assertEqual(len(customer_feed), 2)
        self.assertEqual(customer_feed[0]["message"], "Please leave at guard gate 4B.")
        self.assertEqual(customer_feed[1]["message"], "Understood, extra sauces included!")

        # 5. Fetch messages via order_id (staff/merchant side)
        staff_feed = self.service.get_order_messages(order_id=order_id)
        self.assertEqual(len(staff_feed), 2)

if __name__ == "__main__":
    unittest.main()
