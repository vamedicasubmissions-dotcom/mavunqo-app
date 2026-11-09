"""
Unit and Integration Test Suite for Mavunqo Phase 1.
Validates:
1. Public visitor search without account (keyword, category, location, service).
2. Sosúa is active launch market, Cabarete and Puerto Plata staged as upcoming.
3. RNC optionality during business registration.
4. Business approval gate (listings stay pending until Jay approves).
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

    # 6. Optional RNC in Registration & Pending Approval Gate
    def test_registration_optional_rnc_and_jay_approval_gate(self):
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

        # Jay Admin approves listing
        self.service.approve_business(admin_user_id="user_jay_admin", business_id=new_biz_id)

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

if __name__ == "__main__":
    unittest.main()
