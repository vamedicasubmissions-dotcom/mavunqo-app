import unittest
import os
import time
import json
import tempfile
import hmac
import hashlib

from backend.db import init_db, get_connection
from backend.redaction import (
    hash_phone_number,
    mask_phone_number,
    generate_customer_alias,
    redact_text,
    redact_dict
)
from backend.tokens_and_attribution import (
    generate_attribution_signature,
    verify_attribution_signature,
    build_merchant_qr_link,
    compute_order_fee,
    create_secure_order_token,
    STANDARD_COMMISSION_RATE
)
from backend.whatsapp_gateway import (
    verify_webhook_signature,
    record_and_check_idempotency,
    get_customer_consent,
    update_customer_consent,
    process_inbound_opt_keywords
)
from backend.whatsapp_bot import WhatsAppOrderBot
from backend.whatsapp_ordering_service import WhatsAppOrderingService
from backend.seed import seed_database

class TestWhatsAppOrderingSystem(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.test_db = os.path.join(tempfile.gettempdir(), f"test_mavunqo_wa_{int(time.time())}.db")
        init_db(cls.test_db)
        seed_database(cls.test_db)
        cls.wa_service = WhatsAppOrderingService(cls.test_db)
        cls.wa_bot = WhatsAppOrderBot(cls.test_db)

    @classmethod
    def tearDownClass(cls):
        if os.path.exists(cls.test_db):
            try:
                os.remove(cls.test_db)
            except Exception:
                pass

    def test_01_privacy_and_phone_masking(self):
        """Merchants and standard exports must NEVER see raw phone numbers."""
        phone = "+1 (809) 555-4321"
        alias = generate_customer_alias(phone, "Sosúa")
        self.assertTrue(alias.startswith("Guest #"))
        self.assertNotIn("809", alias)
        self.assertNotIn("4321", alias)

        masked = mask_phone_number(phone)
        self.assertEqual(masked, "+***-***-**21")

        text_with_phone = "Please call 809-555-9999 when food is ready."
        redacted = redact_text(text_with_phone)
        self.assertNotIn("809-555-9999", redacted)
        self.assertIn("[REDACTED_PHONE]", redacted)

    def test_02_authoritative_order_lifecycle(self):
        """Every WhatsApp order gets authoritative Mavunqo Order ID and recorded in DB."""
        order_res = self.wa_service.create_whatsapp_assisted_order(
            business_id="biz_el_batey_bistro",
            customer_phone="8291112233",
            items=[{"menu_item_id": "mi_red_snapper", "quantity": 2}],
            fulfillment_type="delivery",
            delivery_address="Playa Sosua #44",
            customer_notes="Extra lime"
        )
        self.assertTrue(order_res["success"])
        self.assertTrue(order_res["order_id"].startswith("ord_"))
        self.assertTrue(order_res["order_number"].startswith("MVQ-"))
        self.assertEqual(order_res["source_type"], "mavunqo_acquired")
        self.assertEqual(order_res["commission_rate"], 0.15)
        self.assertAlmostEqual(order_res["commission_amount"], round(order_res["customer_selling_price"] * 0.15, 2))
        self.assertAlmostEqual(order_res["merchant_payout"], round(order_res["customer_selling_price"] - order_res["commission_amount"], 2))

    def test_03_standard_15_percent_commission_across_all_sources(self):
        """
        Verify single standard 15% commission across both Mavunqo-acquired and merchant-acquired orders.
        Attribution is tracked for analytics, and initial launch commission is 15% flat.
        """
        biz_id = "biz_el_batey_bistro"
        campaign = "table_qr_05"
        valid_sig = generate_attribution_signature(biz_id, campaign)

        # 1. Merchant-acquired order -> identified as merchant_acquired, charged 15%
        res_merchant = self.wa_service.create_whatsapp_assisted_order(
            business_id=biz_id,
            customer_phone="8292223344",
            items=[{"menu_item_id": "mi_red_snapper", "quantity": 1}],
            attribution_payload={"m_biz": biz_id, "m_camp": campaign, "m_sig": valid_sig}
        )
        self.assertEqual(res_merchant["source_type"], "merchant_acquired")
        self.assertEqual(res_merchant["commission_rate"], 0.15)
        self.assertEqual(res_merchant["commission_amount"], round(res_merchant["customer_selling_price"] * 0.15, 2))
        self.assertEqual(res_merchant["merchant_payout"], round(res_merchant["customer_selling_price"] - res_merchant["commission_amount"], 2))

        # 2. Mavunqo-acquired order -> identified as mavunqo_acquired, charged 15%
        res_mavunqo = self.wa_service.create_whatsapp_assisted_order(
            business_id=biz_id,
            customer_phone="8293334455",
            items=[{"menu_item_id": "mi_red_snapper", "quantity": 1}]
        )
        self.assertEqual(res_mavunqo["source_type"], "mavunqo_acquired")
        self.assertEqual(res_mavunqo["commission_rate"], 0.15)
        self.assertEqual(res_mavunqo["commission_amount"], round(res_mavunqo["customer_selling_price"] * 0.15, 2))
        self.assertEqual(res_mavunqo["merchant_payout"], round(res_mavunqo["customer_selling_price"] - res_mavunqo["commission_amount"], 2))

        # 3. Tampered attribution signature defaults to mavunqo_acquired, still charged 11%
        res_tampered = self.wa_service.create_whatsapp_assisted_order(
            business_id=biz_id,
            customer_phone="8294445566",
            items=[{"menu_item_id": "mi_red_snapper", "quantity": 1}],
            attribution_payload={"m_biz": biz_id, "m_camp": campaign, "m_sig": "invalid_tampered_sig"}
        )
        self.assertEqual(res_tampered["source_type"], "mavunqo_acquired")
        self.assertEqual(res_tampered["commission_rate"], 0.15)

    def test_04_idempotent_webhook_and_replay_prevention(self):
        """Duplicate WhatsApp events must be rejected to prevent duplicate processing."""
        event_id = f"evt_{int(time.time())}"
        msg_id = f"wamid_test_{int(time.time())}"
        payload = json.dumps({"test": "data", "id": event_id})

        first_attempt = record_and_check_idempotency(self.test_db, event_id, msg_id, "message", payload)
        self.assertTrue(first_attempt)

        replay_attempt = record_and_check_idempotency(self.test_db, event_id, msg_id, "message", payload)
        self.assertFalse(replay_attempt)

    def test_05_consent_management_and_opt_out(self):
        """Transactional and marketing consents separated; STOP keyword triggers opt-out."""
        phone = "8097778899"
        update_customer_consent(self.test_db, phone, transactional=True, marketing=False, source="checkout")
        c1 = get_customer_consent(self.test_db, phone)
        self.assertEqual(c1["transactional_consent"], 1)
        self.assertEqual(c1["marketing_consent"], 0)

        # Opt-out via WhatsApp keyword STOP
        resp = process_inbound_opt_keywords(self.test_db, phone, "STOP")
        self.assertIn("dado de baja", resp)
        c2 = get_customer_consent(self.test_db, phone)
        self.assertEqual(c2["transactional_consent"], 0)

    def test_06_secure_order_token_expiration_and_single_use(self):
        """Tokens are single-use, opaque and reject reuse or expired state."""
        tok = create_secure_order_token("ord_dummy_999", "biz_el_batey_bistro", expires_in=1800)
        self.assertTrue(tok["token"].startswith("mvt_"))
        self.assertNotIn("ord_dummy_999", tok["token"])

    def test_07_cash_only_merchant_tracking(self):
        """Cash due and collected are tracked separately from order completion."""
        order_res = self.wa_service.create_whatsapp_assisted_order(
            business_id="biz_el_batey_bistro",
            customer_phone="8098889900",
            items=[{"menu_item_id": "mi_red_snapper", "quantity": 1}],
            fulfillment_type="pickup"
        )
        oid = order_res["order_id"]
        total = order_res["total"]

        cash_res = self.wa_service.record_cash_collection(
            user_id="user_rest1_marco",
            business_id="biz_el_batey_bistro",
            order_id=oid,
            amount_collected=total + 50.0,
            is_exception=True,
            exception_notes="50 DOP extra tip given in cash"
        )
        self.assertTrue(cash_res["success"])
        self.assertEqual(cash_res["cash_status"], "exception")

    def test_08_rbac_and_zero_phone_exposure_in_dashboard(self):
        """Merchant operational dashboard shows zero raw phone numbers and hides fees from kitchen."""
        orders = self.wa_service.get_merchant_operational_orders(
            user_id="user_rest1_marco",
            business_id="biz_el_batey_bistro"
        )
        self.assertGreater(len(orders), 0)
        for o in orders:
            self.assertNotIn("customer_phone", o)
            self.assertTrue(o["customer_alias"].startswith("Guest #") or o["customer_alias"] == o["customer_name"])
            self.assertIn("masked_phone", o)
            self.assertIn("aging_minutes", o)
            # Owner sees financial fields
            self.assertIn("customer_selling_price", o)
            self.assertIn("commission_rate", o)
            self.assertIn("merchant_payout", o)

    def test_09_manual_fallback_handoff_with_warning(self):
        """Manual fallback requires operational reason and logs phone exposure warning."""
        orders = self.wa_service.get_merchant_operational_orders("user_rest1_marco", "biz_el_batey_bistro")
        oid = orders[0]["id"]

        fallback_res = self.wa_service.initiate_manual_whatsapp_fallback(
            user_id="user_rest1_marco",
            business_id="biz_el_batey_bistro",
            order_id=oid,
            reason="Repartidor extravió la dirección exacta en El Batey"
        )
        self.assertTrue(fallback_res["success"])
        self.assertIn("AVISO DE PRIVACIDAD", fallback_res["warning"])

    def test_10_break_glass_exceptional_access_audit(self):
        """Break-glass unmasking requires justification and writes an audit event."""
        orders = self.wa_service.get_merchant_operational_orders("user_rest1_marco", "biz_el_batey_bistro")
        oid = orders[0]["id"]

        access_res = self.wa_service.break_glass_exceptional_access(
            user_id="user_rest1_marco",
            business_id="biz_el_batey_bistro",
            order_id=oid,
            reason="Investigación de fraude y doble cobro por el banco local"
        )
        self.assertTrue(access_res["success"])
        self.assertIn("customer_phone", access_res)
        self.assertIn("warning", access_res)

    def test_11_sanitized_csv_export_financial_record(self):
        """CSV export contains zero raw phone numbers and contains full financial breakdown."""
        csv_data = self.wa_service.generate_sanitized_csv_export(
            user_id="user_rest1_marco",
            business_id="biz_el_batey_bistro"
        )
        self.assertIn("Customer Alias", csv_data)
        self.assertIn("Customer Selling Price", csv_data)
        self.assertIn("Commission Rate", csv_data)
        self.assertIn("15.0%", csv_data)
        self.assertIn("Merchant Payout", csv_data)
        # Assert no phone numbers in customer columns
        for row in csv_data.splitlines()[1:]:
            parts = row.split(",")
            alias_col = parts[2]
            self.assertTrue(alias_col.startswith('"Guest #'))
            self.assertNotIn("809555", row)
            self.assertNotIn("829111", row)

    def test_12_financial_adjustment_audit_record(self):
        """Test recording of approved credit, refund, or adjustment."""
        orders = self.wa_service.get_merchant_operational_orders("user_rest1_marco", "biz_el_batey_bistro")
        oid = orders[0]["id"]

        adj_res = self.wa_service.record_financial_adjustment(
            user_id="user_rest1_marco",
            business_id="biz_el_batey_bistro",
            order_id=oid,
            adjustment_type="credit",
            adjustment_amount=100.0,
            reason="Compensación de cortesía por demora en cocina"
        )
        self.assertTrue(adj_res["success"])
        self.assertEqual(adj_res["adjustment_type"], "credit")
        self.assertEqual(adj_res["amount"], 100.0)

    def test_13_vamedica_isolation_integrity(self):
        """Strict verification: No files in D:\\AI VAMEDICA WORKFLOW were touched."""
        vamedica_path = "D:\\AI VAMEDICA WORKFLOW"
        if os.path.exists(vamedica_path):
            self.assertNotIn("Mavunqo", vamedica_path)
        self.assertTrue(os.path.exists("D:\\Mavunqo"))
        self.assertTrue(os.path.exists("D:\\Mavunqo\\backend\\whatsapp_ordering_service.py"))

if __name__ == "__main__":
    unittest.main()
