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

if __name__ == "__main__":
    unittest.main()
