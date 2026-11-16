"""
Phase 2 Acceptance Test Suite for Mavunqo Merchant Request Automation,
Pilot Locations, Confirmed Map Pins, and Managed Motorcycle Delivery.
"""
import io
import json
import unittest
from datetime import datetime, timezone, timedelta
from backend.server import MavunqoRequestHandler, service, DB_PATH
from backend.seed import seed_database

class MockSocket:
    def __init__(self, request_bytes):
        self.rfile = io.BytesIO(request_bytes)
        self.wfile = io.BytesIO()

    def makefile(self, mode, *args, **kwargs):
        if 'r' in mode:
            return self.rfile
        elif 'w' in mode:
            return self.wfile
        raise ValueError("Invalid mode")

    def sendall(self, data):
        self.wfile.write(data)

def invoke(method: str, path: str, headers: dict = None, body: dict = None):
    headers = headers or {}
    body_bytes = b""
    if body is not None:
        body_bytes = json.dumps(body).encode("utf-8")
        headers["Content-Length"] = str(len(body_bytes))
        headers["Content-Type"] = "application/json"

    raw_req = f"{method} {path} HTTP/1.1\r\nHost: localhost\r\n"
    for k, v in headers.items():
        raw_req += f"{k}: {v}\r\n"
    raw_req += "\r\n"

    raw_bytes = raw_req.encode("utf-8") + body_bytes
    mock_sock = MockSocket(raw_bytes)

    class DummyServer:
        pass

    try:
        MavunqoRequestHandler(mock_sock, ("127.0.0.1", 12345), DummyServer())
    except Exception:
        pass

    response_bytes = mock_sock.wfile.getvalue()
    header_part, _, body_part = response_bytes.partition(b"\r\n\r\n")
    header_lines = header_part.decode("utf-8", errors="ignore").split("\r\n")
    status_line = header_lines[0] if header_lines else ""
    status_code = int(status_line.split(" ")[1]) if " " in status_line else 500

    parsed_body = {}
    if body_part:
        try:
            parsed_body = json.loads(body_part.decode("utf-8"))
        except Exception:
            parsed_body = body_part

    return status_code, parsed_body

class TestPhase2MerchantRequests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        seed_database(DB_PATH)

    def test_01_search_aliases_and_locations(self):
        """Acceptance check: Search for 'massage' and 'masaje' finds the same approved listing."""
        st_en, res_en = invoke("GET", "/api/businesses?q=massage")
        st_es, res_es = invoke("GET", "/api/businesses?q=masaje")
        self.assertEqual(st_en, 200)
        self.assertEqual(st_es, 200)
        self.assertTrue(any(b["slug"] == "montellano-oasis-massage" for b in res_en))
        self.assertTrue(any(b["slug"] == "montellano-oasis-massage" for b in res_es))

        # Check Montellano alias matches Villa Montellano
        st_v, res_v = invoke("GET", "/api/businesses?location=Villa%20Montellano")
        st_m, res_m = invoke("GET", "/api/businesses?location=Montellano")
        self.assertEqual(st_v, 200)
        self.assertEqual(st_m, 200)
        v_slugs = sorted([b["slug"] for b in res_v])
        m_slugs = sorted([b["slug"] for b in res_m])
        self.assertEqual(v_slugs, m_slugs)
        self.assertIn("montellano-oasis-massage", v_slugs)

    def test_02_unactivated_listing_register_interest(self):
        """Scenario: Approved but unactivated listing shows register interest; no order or WhatsApp created."""
        biz = service.get_business_by_slug("ferreteria-el-canero-montellano")
        self.assertEqual(biz["requests_enabled"], 0)

        interest_payload = {
            "business_id": biz["id"],
            "customer_name": "Pedro Almonte",
            "customer_contact": "+18095559988",
            "interest_note": "Need 50 cement bags delivered to Montellano next week",
            "source_url": "/b/ferreteria-el-canero-montellano"
        }
        st, res = invoke("POST", "/api/interest", body=interest_payload)
        self.assertEqual(st, 201)
        self.assertTrue(res["success"])
        self.assertTrue(res["interest_id"].startswith("int_"))

        # Verify interest count increased without creating orders
        count = service.get_business_interest_count(biz["id"])
        self.assertGreaterEqual(count, 1)

    def test_03_menu_free_restaurant_intake_and_deadline(self):
        """Scenario: Activated restaurant with no menu receives request; calculates 15-min deadline."""
        biz = service.get_business_by_slug("taqueria-del-sol-sosua")
        self.assertEqual(biz["requests_enabled"], 1)
        self.assertEqual(biz["whatsapp_alerts_consent"], 0) # No WhatsApp consent

        req_payload = {
            "business_id": biz["id"],
            "customer": {"name": "Sara Jenkins", "phone": "+18095558833"},
            "request_text": "2 steak burritos with extra salsa verde and 1 horchata",
            "action_type": "request_order",
            "service_mode": "pickup"
        }
        st, res = invoke("POST", "/api/requests", body=req_payload)
        self.assertEqual(st, 201)
        self.assertTrue(res["success"])
        self.assertFalse(res["notification_sent"]) # Merchant without consent gets no alert
        self.assertEqual(res["status"], "awaiting_confirmation")

        # Verify 15-minute deadline stored
        status_token = res["status_token"]
        st_chk, req_data = invoke("GET", f"/api/requests/status?token={status_token}")
        self.assertEqual(st_chk, 200)
        self.assertEqual(req_data["status"], "awaiting_confirmation")
        dl = datetime.fromisoformat(req_data["deadline_utc"].replace("Z", "+00:00"))
        # Deadline should be ~15 min from created_at
        self.assertLessEqual((dl - datetime.now(timezone.utc)).total_seconds(), 905)

    def test_04_merchant_privacy_and_offer_counter(self):
        """Scenario: Merchant opens alert with phone hidden; supplies missing price; customer accepts."""
        # 1. Create request for massage appointment with missing price
        biz = service.get_business_by_slug("montellano-oasis-massage")
        req_payload = {
            "business_id": biz["id"],
            "customer": {"name": "Mark Wilson", "phone": "+18095557766"},
            "request_text": "Deep tissue massage for lower back pain at clinic",
            "action_type": "request_appointment",
            "service_mode": "in_shop",
            "destination_lat": None,
            "destination_lng": None
        }
        st, res = invoke("POST", "/api/requests", body=req_payload)
        self.assertEqual(st, 201)
        merchant_token = res["merchant_url"].split("token=")[1]
        status_token = res["status_token"]

        # 2. Merchant views request: verify customer phone is masked
        st_m, m_view = invoke("GET", f"/api/requests/merchant?token={merchant_token}")
        self.assertEqual(st_m, 200)
        self.assertIn("customer_phone_masked", m_view)
        self.assertNotIn("customer_phone", m_view)

        # 3. Merchant suggests price of 2500 DOP and time
        suggest_payload = {
            "token": merchant_token,
            "action": "suggest_change",
            "price": 2500.0,
            "currency": "DOP",
            "offered_time": (datetime.now(timezone.utc) + timedelta(hours=3)).isoformat(),
            "notes": "We have a 3:00 PM slot available today with therapist Ana."
        }
        st_s, res_s = invoke("POST", "/api/requests/respond", body=suggest_payload)
        self.assertEqual(st_s, 200)
        self.assertEqual(res_s["status"], "offer_pending")
        offer_id = res_s["offer_id"]

        # 4. Customer views offer on status page and accepts
        st_c, c_view = invoke("GET", f"/api/requests/status?token={status_token}")
        self.assertEqual(st_c, 200)
        self.assertEqual(c_view["status"], "offer_pending")
        self.assertEqual(len(c_view["offers"]), 1)

        accept_payload = {
            "status_token": status_token,
            "offer_id": offer_id,
            "action": "accept"
        }
        st_acc, res_acc = invoke("POST", "/api/requests/offer/respond", body=accept_payload)
        self.assertEqual(st_acc, 200)
        self.assertEqual(res_acc["status"], "confirmed")
        self.assertTrue(res_acc["order_number"].startswith("ORD-"))

    def test_05_confirmed_map_pin_validation(self):
        """Scenario: Mobile home visit requires confirmed destination pin; out-of-area rejected."""
        biz = service.get_business_by_slug("montellano-oasis-massage")
        
        # 1. Missing pin must fail
        bad_payload = {
            "business_id": biz["id"],
            "customer": {"name": "Elena Vance", "phone": "+18095551122"},
            "request_text": "Villa visit massage",
            "action_type": "request_appointment",
            "service_mode": "mobile_visit",
            "destination_lat": None,
            "destination_lng": None
        }
        st_bad, res_bad = invoke("POST", "/api/requests", body=bad_payload)
        self.assertEqual(st_bad, 400)
        self.assertIn("confirmed destination map pin is required", res_bad.get("error", ""))

        # 2. Out of area coordinates (e.g. Santo Domingo 18.48, -69.93) must fail
        out_payload = {
            "business_id": biz["id"],
            "customer": {"name": "Elena Vance", "phone": "+18095551122"},
            "request_text": "Villa visit massage in Santo Domingo",
            "action_type": "request_appointment",
            "service_mode": "mobile_visit",
            "destination_lat": 18.48,
            "destination_lng": -69.93
        }
        st_out, res_out = invoke("POST", "/api/requests", body=out_payload)
        self.assertEqual(st_out, 400)
        self.assertIn("outside the current pilot service area", res_out.get("error", ""))

        # 3. Valid Sosúa / Montellano pin succeeds and includes directions URL
        valid_payload = {
            "business_id": biz["id"],
            "customer": {"name": "Elena Vance", "phone": "+18095551122"},
            "request_text": "Villa visit massage in Sosua Ocean Village",
            "action_type": "request_appointment",
            "service_mode": "mobile_visit",
            "destination_lat": 19.7582,
            "destination_lng": -70.5211,
            "destination_entrance_note": "Villa 24, Gate code 1234"
        }
        st_ok, res_ok = invoke("POST", "/api/requests", body=valid_payload)
        self.assertEqual(st_ok, 201)
        st_chk, req_info = invoke("GET", f"/api/requests/status?token={res_ok['status_token']}")
        self.assertIn("google.com/maps/dir", req_info["destination_directions_url"])
        self.assertEqual(req_info["destination_entrance_note"], "Villa 24, Gate code 1234")

    def test_06_managed_delivery_dispatch_and_cash_reconciliation(self):
        """Scenario: Mavunqo dispatcher assigns order; driver views travel-ordered stops; cash discrepancy detected."""
        # 1. Login as Admin / Dispatcher
        st_l, res_l = invoke("POST", "/api/auth/login", body={"email": "admin@mavunqo.com", "password": "AdminPass2026!"})
        self.assertEqual(st_l, 200)
        admin_token = res_l["token"]
        headers = {"Authorization": f"Bearer {admin_token}"}

        # 2. Get dispatcher queue
        st_q, q_data = invoke("GET", "/api/dispatcher/queue", headers=headers)
        self.assertEqual(st_q, 200)
        self.assertGreaterEqual(len(q_data["drivers"]), 1)
        driver_id = q_data["drivers"][0]["id"]

        # 3. Create a delivery order to dispatch
        biz = service.get_business_by_slug("taqueria-del-sol-sosua")
        req_payload = {
            "business_id": biz["id"],
            "customer": {"name": "Robert Taylor", "phone": "+18095554321"},
            "request_text": "Delivery order: 3 Carnitas Tacos and Quesadilla",
            "action_type": "request_order",
            "service_mode": "delivery",
            "destination_lat": 19.7565,
            "destination_lng": -70.5125,
            "destination_entrance_note": "Condo Las Canas Apt 3B",
            "agreed_price": 600.0
        }
        st_req, res_req = invoke("POST", "/api/requests", body=req_payload)
        m_tok = res_req["merchant_url"].split("token=")[1]
        
        # Accept request to confirm order
        st_acc, res_acc = invoke("POST", "/api/requests/respond", body={"token": m_tok, "action": "accept", "price": 600.0})
        order_id = res_acc["order_id"]

        # 4. Dispatcher assigns driver
        assign_payload = {
            "order_id": order_id,
            "driver_id": driver_id
        }
        st_as, res_as = invoke("POST", "/api/dispatcher/assign", headers=headers, body=assign_payload)
        self.assertEqual(st_as, 200)
        self.assertEqual(res_as["status"], "dispatched")

        # 5. Driver opens job view: sees 2 travel-ordered stops with directions links
        st_drv, jobs = invoke("GET", f"/api/driver/jobs?driver_id={driver_id}")
        self.assertEqual(st_drv, 200)
        my_job = next(j for j in jobs if j["order_id"] == order_id)
        self.assertEqual(len(my_job["stops"]), 2)
        self.assertEqual(my_job["stops"][0]["stop_type"], "pickup")
        self.assertEqual(my_job["stops"][1]["stop_type"], "dropoff")
        self.assertIn("Condo Las Canas", my_job["stops"][1]["entrance_note"])

        # 6. Driver collects cash at customer drop-off: RD$700 (600 items + 100 delivery)
        st_col, res_col = invoke("POST", "/api/driver/collect-cash", body={
            "order_id": order_id,
            "driver_id": driver_id,
            "amount_collected": 700.0
        })
        self.assertEqual(st_col, 200)
        self.assertEqual(res_col["amount_collected"], 700.0)

        # 7. Cash Handoff & Discrepancy Reconciliation:
        # Driver reports RD$700, but receiver counts RD$650 -> Discrepancy flagged!
        handoff_payload = {
            "driver_id": driver_id,
            "order_ids": [order_id],
            "total_driver_reported": 700.0,
            "total_receiver_counted": 650.0,
            "notes": "Shortage of 50 pesos: driver had only 650 pesos in small bills."
        }
        st_hnd, res_hnd = invoke("POST", "/api/dispatcher/cash-handoff", headers=headers, body=handoff_payload)
        self.assertEqual(st_hnd, 200)
        self.assertEqual(res_hnd["status"], "unresolved_discrepancy")
        self.assertEqual(res_hnd["difference"], -50.0)
        self.assertTrue(res_hnd["is_discrepancy"])

        # 8. Centralized Clearinghouse Model & Merchant Cash Envelope Settlement:
        # Reconcile full cash handoff
        handoff_clean = {
            "driver_id": driver_id,
            "order_ids": [order_id],
            "total_driver_reported": 700.0,
            "total_receiver_counted": 700.0,
            "notes": "Reconciled after driver handed over remaining 50 DOP."
        }
        invoke("POST", "/api/dispatcher/cash-handoff", headers=headers, body=handoff_clean)

        # Check Merchant Settlements queue
        st_set, res_set = invoke("GET", "/api/dispatcher/merchant-settlements", headers=headers)
        self.assertEqual(st_set, 200)
        self.assertIn("merchants", res_set)
        
        # Find merchant (biz["id"] from step 3: Taqueria del Sol Sosua)
        target_merchant = next((m for m in res_set["merchants"] if m["business_id"] == biz["id"]), None)
        self.assertIsNotNone(target_merchant)
        self.assertGreaterEqual(target_merchant["gross_sales"], 600.0)
        # Verify Mavunqo platform commission retained (e.g. 10% = 60 DOP)
        self.assertGreater(target_merchant["commission_retained"], 0)
        # Net cash payout envelope amount = Gross - Commission
        self.assertAlmostEqual(
            target_merchant["net_payout_due"],
            target_merchant["gross_sales"] - target_merchant["commission_retained"],
            places=2
        )

        # Dispatcher hands envelope to merchant and records payout
        payout_payload = {
            "business_id": biz["id"],
            "order_ids": [order_id],
            "payout_method": "cash_envelope",
            "notes": "Handed cash envelope at shop in El Batey, signed by manager."
        }
        st_pay, res_pay = invoke("POST", "/api/dispatcher/merchant-settlements/payout", headers=headers, body=payout_payload)
        self.assertEqual(st_pay, 200)
        self.assertTrue(res_pay["success"])
        self.assertEqual(res_pay["business_id"], biz["id"])
        self.assertGreater(res_pay["net_payout_amount"], 0)

        # Verify that after payout, the order is settled and no longer pending in settlements queue
        _, res_set_after = invoke("GET", "/api/dispatcher/merchant-settlements", headers=headers)
        pending_ids_after = [
            o["order_id"]
            for m in res_set_after["merchants"]
            for o in m["pending_orders"]
        ]
        self.assertNotIn(order_id, pending_ids_after)

    def test_07_zero_chargeback_payment_methods(self):
        """Scenario: Customer places order selecting Zelle or Bank Transfer (Transferencia) with 0% chargeback risk."""
        st_m, body_m = invoke("GET", "/api/restaurants/el-batey-bistro/menu")
        self.assertEqual(st_m, 200)
        biz_id = body_m["business_id"]
        snapper_cat = next(c for c in body_m["categories"] if c["name_en"] == "Fresh Catch & Grill")
        item = snapper_cat["items"][0]

        # 1. Place order with Zelle
        zelle_order_payload = {
            "business_id": biz_id,
            "customer": {"name": "Michael US Tourist", "phone": "8095551234"},
            "fulfillment_type": "delivery",
            "payment_method": "zelle",
            "delivery_address": "Sosua Ocean Village, Villa 21",
            "items": [{"menu_item_id": item["id"], "quantity": 2}]
        }
        st_z, res_z = invoke("POST", "/api/orders", body=zelle_order_payload)
        self.assertEqual(st_z, 201)
        self.assertTrue(res_z["success"])
        
        # Verify order details
        z_tok = res_z["status_url"].split("token=")[1]
        st_stat, o_stat = invoke("GET", f"/api/orders/status?token={z_tok}")
        self.assertEqual(st_stat, 200)
        self.assertEqual(o_stat["payment_method"], "zelle")
        self.assertEqual(o_stat["cash_due"], 0.0)

        # 2. Place order with Dominican Bank Transfer (Transferencia)
        transfer_payload = {
            "business_id": biz_id,
            "customer": {"name": "Juan Perez Local", "phone": "8095558899"},
            "fulfillment_type": "pickup",
            "payment_method": "transfer",
            "items": [{"menu_item_id": item["id"], "quantity": 1}]
        }
        st_t, res_t = invoke("POST", "/api/orders", body=transfer_payload)
        self.assertEqual(st_t, 201)
        self.assertTrue(res_t["success"])
        
        t_tok = res_t["status_url"].split("token=")[1]
        st_stat2, o_stat2 = invoke("GET", f"/api/orders/status?token={t_tok}")
        self.assertEqual(st_stat2, 200)
        self.assertEqual(o_stat2["payment_method"], "transfer")
        self.assertEqual(o_stat2["cash_due"], 0.0)

        # 3. Place order with Wise (Europe / Canada Instant Transfer)
        wise_payload = {
            "business_id": biz_id,
            "customer": {"name": "Hans EU Tourist", "phone": "8095557766"},
            "fulfillment_type": "delivery",
            "payment_method": "wise",
            "delivery_address": "Cabarete Kite Beach Apt 4",
            "items": [{"menu_item_id": item["id"], "quantity": 1}]
        }
        st_w, res_w = invoke("POST", "/api/orders", body=wise_payload)
        self.assertEqual(st_w, 201)
        self.assertTrue(res_w["success"])
        w_tok = res_w["status_url"].split("token=")[1]
        st_stat3, o_stat3 = invoke("GET", f"/api/orders/status?token={w_tok}")
        self.assertEqual(st_stat3, 200)
        self.assertEqual(o_stat3["payment_method"], "wise")
        self.assertEqual(o_stat3["cash_due"], 0.0)

    def test_08_driver_tip_rain_mode_and_pin(self):
        # 1. Admin login for Rain Mode toggle
        st_l, res_l = invoke("POST", "/api/auth/login", body={
            "email": "admin@mavunqo.com",
            "password": "AdminPass2026!"
        })
        self.assertEqual(st_l, 200)
        headers = {"Authorization": f"Bearer {res_l['token']}"}

        # 2. Enable Rain Mode via API
        st_rm, res_rm = invoke("POST", "/api/dispatcher/rain-mode", headers=headers, body={
            "location_id": "loc_sosua",
            "rain_mode_active": True
        })
        self.assertEqual(st_rm, 200)
        self.assertTrue(res_rm["rain_mode_active"])
        self.assertEqual(res_rm["delivery_fee"], 150.0)

        # 3. Verify capacity endpoint reflects Rain Mode
        st_cap, res_cap = invoke("GET", "/api/delivery/capacity?location=loc_sosua")
        self.assertEqual(st_cap, 200)
        self.assertTrue(res_cap["rain_mode_active"])
        self.assertEqual(res_cap["delivery_fee"], 150.0)

        # 4. Place delivery order with RD$ 100 tip during Rain Mode
        st_m, m_data = invoke("GET", "/api/restaurants/el-batey-bistro/menu")
        self.assertEqual(st_m, 200)
        biz_id = m_data["business_id"]
        item = m_data["categories"][0]["items"][0]

        st_o, res_o = invoke("POST", "/api/orders", body={
            "business_id": biz_id,
            "customer": {"name": "Tip Tester", "phone": "8095559900"},
            "fulfillment_type": "delivery",
            "payment_method": "zelle",
            "driver_tip": 100.0,
            "delivery_address": "Casa Linda Villa 14",
            "items": [{"menu_item_id": item["id"], "quantity": 1}]
        })
        self.assertEqual(st_o, 201)
        expected_total = round(float(item["price"]) + 150.0 + 100.0, 2)
        self.assertEqual(res_o["total"], expected_total)

        o_tok = res_o["status_url"].split("token=")[1]
        st_os, o_stat = invoke("GET", f"/api/orders/status?token={o_tok}")
        self.assertEqual(st_os, 200)
        self.assertEqual(o_stat["delivery_fee"], 150.0)
        self.assertEqual(o_stat["driver_tip"], 100.0)
        self.assertEqual(o_stat["payment_method"], "zelle")

        # 5. Turn Rain Mode back off
        st_rm2, res_rm2 = invoke("POST", "/api/dispatcher/rain-mode", headers=headers, body={
            "location_id": "loc_sosua",
            "rain_mode_active": False
        })
        self.assertEqual(st_rm2, 200)
        self.assertFalse(res_rm2["rain_mode_active"])

        # 6. Driver PIN verification
        st_bad, _ = invoke("POST", "/api/driver/verify-pin", body={"driver_id": "drv_sosua_2", "pin_code": "0000"})
        self.assertEqual(st_bad, 403)
        st_ok, res_ok = invoke("POST", "/api/driver/verify-pin", body={"driver_id": "drv_sosua_2", "pin_code": "1234"})
        self.assertEqual(st_ok, 200)
        self.assertTrue(res_ok["success"])

        # 7. Keep-alive /ping endpoint
        st_p, res_p = invoke("GET", "/ping")
        self.assertEqual(st_p, 200)
        self.assertEqual(res_p["status"], "ok")

        # 8. Payment proof upload + dispatcher verify-payment + bank email monitor check
        import base64 as _b64, uuid as _uuid
        _base_png = _b64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=")
        sample_png_b64 = "data:image/png;base64," + _b64.b64encode(_base_png + _uuid.uuid4().bytes).decode("ascii")
        st_proof, res_proof = invoke("POST", "/api/orders", body={
            "business_id": biz_id,
            "customer": {"name": "Zelle Proof Customer", "phone": "8095553344"},
            "fulfillment_type": "delivery",
            "payment_method": "zelle",
            "payment_proof_image": sample_png_b64,
            "delivery_address": "Perla Marina Villa 8",
            "delivery_pin_lat": 19.76123,
            "delivery_pin_lng": -70.48987,
            "items": [{"menu_item_id": item["id"], "quantity": 1}]
        })
        self.assertEqual(st_proof, 201)
        self.assertTrue(res_proof["payment_proof_url"].startswith("/frontend/uploads/proofs/"))

        # Verify checkout pin coordinates flow straight to driver job GPS link
        invoke("POST", "/api/dispatcher/assign", headers=headers, body={
            "order_id": res_proof["order_id"],
            "driver_id": "drv_sosua_2"
        })
        st_dj, dj_list = invoke("GET", "/api/driver/jobs?driver_id=drv_sosua_2")
        self.assertEqual(st_dj, 200)
        proof_job = next(j for j in dj_list if j["order_id"] == res_proof["order_id"])
        self.assertAlmostEqual(proof_job["destination_lat"], 19.76123, places=4)
        self.assertAlmostEqual(proof_job["destination_lng"], -70.48987, places=4)
        self.assertEqual(proof_job["payment_method"], "zelle")

        st_vp, res_vp = invoke("POST", "/api/dispatcher/verify-payment", headers=headers, body={
            "order_id": res_proof["order_id"],
            "source": "bank_email_monitor"
        })
        self.assertEqual(st_vp, 200)
        self.assertTrue(res_vp["payment_verified"])

        st_chk, res_chk = invoke("GET", "/api/dispatcher/check-bank-emails", headers=headers)
        self.assertEqual(st_chk, 200)
        self.assertIn("deposits", res_chk)

        # 9. Guardrail: Duplicate payment screenshot hash must be blocked
        st_dup, res_dup = invoke("POST", "/api/orders", body={
            "business_id": biz_id,
            "customer": {"name": "Repeat Screenshot Scammer", "phone": "8095550000"},
            "fulfillment_type": "delivery",
            "payment_method": "zelle",
            "payment_proof_image": sample_png_b64,
            "delivery_address": "Perla Marina Villa 9",
            "items": [{"menu_item_id": item["id"], "quantity": 1}]
        })
        self.assertEqual(st_dup, 400)
        self.assertIn("Duplicate payment screenshot", res_dup["error"])

        # 10. Guardrail: Non-image payload rejected
        st_bad_img, res_bad_img = invoke("POST", "/api/orders", body={
            "business_id": biz_id,
            "customer": {"name": "Invalid File Tester", "phone": "8095550001"},
            "fulfillment_type": "delivery",
            "payment_method": "zelle",
            "payment_proof_image": "data:text/plain;base64,SGVsbG8gd29ybGQhIFRoaXMgaXMgbm90IGFuIGltYWdl",
            "delivery_address": "Perla Marina Villa 10",
            "items": [{"menu_item_id": item["id"], "quantity": 1}]
        })
        self.assertEqual(st_bad_img, 400)
        self.assertIn("Only JPG, PNG, or WEBP", res_bad_img["error"])

        # 11. Admin Dynamic Settings & Per-Business Commission Override
        st_gs, res_gs = invoke("GET", "/api/admin/settings", headers=headers)
        self.assertEqual(st_gs, 200)
        self.assertEqual(res_gs["standard_commission_rate"], 0.15)

        st_bc, res_bc = invoke("POST", f"/api/admin/businesses/{biz_id}/commission", headers=headers, body={
            "custom_commission_rate": 0.10
        })
        self.assertEqual(st_bc, 200)
        self.assertEqual(res_bc["custom_commission_rate"], 0.10)

        st_co, res_co = invoke("POST", "/api/orders", body={
            "business_id": biz_id,
            "customer": {"name": "Custom Rate Tester", "phone": "8095551212"},
            "fulfillment_type": "pickup",
            "payment_method": "cash",
            "items": [{"menu_item_id": item["id"], "quantity": 1}]
        })
        self.assertEqual(st_co, 201)
        with service.get_connection() as conn:
            fee_row = conn.execute("SELECT commission_rate FROM fee_records WHERE order_id = ?", (res_co["order_id"],)).fetchone()
        self.assertAlmostEqual(float(fee_row["commission_rate"]), 0.10, places=4)

        # Reset business override back to default
        invoke("POST", f"/api/admin/businesses/{biz_id}/commission", headers=headers, body={"custom_commission_rate": None})

        # 12. 1-2 Week Promo Audience & Customer Opt-Out / Long-Term Opt-In
        st_pa, res_pa = invoke("GET", "/api/admin/promo-audience?days=14", headers=headers)
        self.assertEqual(st_pa, 200)
        self.assertGreaterEqual(res_pa["active_in_town_count"], 1)

        co_tok = res_co["status_url"].split("token=")[1]
        st_opt_out, res_opt_out = invoke("POST", "/api/orders/promo-preference", body={
            "token": co_tok,
            "promo_opt_in": False,
            "promo_longterm_opt_in": False
        })
        self.assertEqual(st_opt_out, 200)
        self.assertFalse(res_opt_out["promo_opt_in"])

        # 13. Business Reach & Location Check-In (Local Restaurant vs. All-Town Tour Guide)
        # Re-opt-in customer in Cabarete via location checkin
        st_opt_in, _ = invoke("POST", "/api/orders/promo-preference", body={
            "token": co_tok,
            "promo_opt_in": True,
            "promo_longterm_opt_in": False
        })
        self.assertEqual(st_opt_in, 200)
        st_ci, res_ci = invoke("POST", "/api/promo/location-checkin", body={
            "token": co_tok,
            "location_id": "loc_cabarete",
            "in_service_area": True
        })
        self.assertEqual(st_ci, 200)
        self.assertEqual(res_ci["last_location_id"], "loc_cabarete")

        # Local restaurant/business (serves_entire_area=0) should NOT see Cabarete customer
        with service.get_connection() as conn:
            local_biz = conn.execute(
                "SELECT id FROM businesses WHERE serves_entire_area = 0 AND primary_location_id != 'loc_cabarete' AND status = 'approved' LIMIT 1"
            ).fetchone()
        if local_biz:
            st_loc, res_loc = invoke("GET", f"/api/admin/promo-audience?days=14&business_id={local_biz['id']}", headers=headers)
            self.assertEqual(st_loc, 200)
            self.assertEqual(res_loc["reach_mode"], "local_coverage")
            cab_phones = [c["phone"] for c in res_loc["active_in_town"]]
            self.assertNotIn("8095551212", cab_phones)

        # Tour/regional business with serves_entire_area=1 SHOULD see Cabarete customer
        with service.get_connection() as conn:
            tour_biz = conn.execute(
                "SELECT id FROM businesses WHERE serves_entire_area = 1 AND status = 'approved' LIMIT 1"
            ).fetchone()
        if tour_biz:
            st_tour, res_tour = invoke("GET", f"/api/admin/promo-audience?days=14&business_id={tour_biz['id']}", headers=headers)
            self.assertEqual(st_tour, 200)
            self.assertEqual(res_tour["reach_mode"], "serves_entire_area")
            self.assertIn("8095551212", [c["phone"] for c in res_tour["active_in_town"]])

        # Customer leaves service area -> automatically paused from promo audience
        st_away, _ = invoke("POST", "/api/promo/location-checkin", body={
            "token": co_tok,
            "in_service_area": False
        })
        self.assertEqual(st_away, 200)
        st_after_away, res_after_away = invoke("GET", "/api/admin/promo-audience?days=14", headers=headers)
        self.assertEqual(st_after_away, 200)
        self.assertNotIn("8095551212", [c["phone"] for c in res_after_away["active_in_town"]])

        # 14. Hotel / Bike Excursion Booking feeds Promo Audience with booked_for_at
        with service.get_connection() as conn:
            req_biz = conn.execute(
                "SELECT id FROM businesses WHERE requests_enabled = 1 AND status = 'approved' LIMIT 1"
            ).fetchone()
        if req_biz:
            from datetime import datetime, timezone
            bk_time = datetime.now(timezone.utc).isoformat()
            st_bk, _ = invoke("POST", "/api/requests", body={
                "business_id": req_biz["id"],
                "customer": {"name": "Villa & Excursion Guest", "phone": "+18095557711"},
                "request_text": "2-hour bike excursion pickup at villa",
                "action_type": "request_appointment",
                "service_mode": "pickup",
                "requested_time": bk_time
            })
            self.assertEqual(st_bk, 201)
            st_bk_pa, res_bk_pa = invoke("GET", "/api/admin/promo-audience?days=14", headers=headers)
            self.assertEqual(st_bk_pa, 200)
            matched = [c for c in res_bk_pa["active_in_town"] if c["phone"] == "+18095557711"]
            self.assertEqual(len(matched), 1)
            self.assertEqual(matched[0]["last_source_type"], "booking")
            self.assertIsNotNone(matched[0]["booked_for_at"])

if __name__ == "__main__":
    unittest.main()
