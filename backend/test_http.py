"""
In-process Mock HTTP Request/Response Testing for MavunqoRequestHandler.
Does not bind to network sockets, running cleanly in sandboxed environments.
"""
import io
import json
import unittest
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

def invoke_handler(method: str, path: str, headers: dict = None, body: dict = None):
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

    # Instantiate handler with dummy client address and mock server
    class DummyServer:
        pass

    try:
        handler = MavunqoRequestHandler(mock_sock, ("127.0.0.1", 12345), DummyServer())
    except Exception:
        pass

    response_bytes = mock_sock.wfile.getvalue()
    header_part, _, body_part = response_bytes.partition(b"\r\n\r\n")
    header_lines = header_part.decode("utf-8", errors="ignore").split("\r\n")
    status_line = header_lines[0] if header_lines else ""
    status_code = int(status_line.split(" ")[1]) if " " in status_line else 500

    return status_code, body_part

class TestHttpEndpoints(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        seed_database(DB_PATH)

    def test_get_categories_endpoint(self):
        status, body = invoke_handler("GET", "/api/categories")
        self.assertEqual(status, 200)
        data = json.loads(body.decode("utf-8"))
        self.assertGreaterEqual(len(data), 6)

    def test_get_locations_endpoint(self):
        status, body = invoke_handler("GET", "/api/locations")
        self.assertEqual(status, 200)
        data = json.loads(body.decode("utf-8"))
        sosua = next(l for l in data if l["name"] == "Sosúa")
        self.assertEqual(sosua["status"], "active")

    def test_get_businesses_search_endpoint(self):
        status, body = invoke_handler("GET", "/api/businesses?location=loc_sosua")
        self.assertEqual(status, 200)
        data = json.loads(body.decode("utf-8"))
        self.assertGreaterEqual(len(data), 2)

    def test_get_single_business_by_slug(self):
        status, body = invoke_handler("GET", "/api/businesses/sosua-ocean-view-villas")
        self.assertEqual(status, 200)
        data = json.loads(body.decode("utf-8"))
        self.assertEqual(data["trading_name"], "Sosúa Ocean View Villa Rentals")
        self.assertEqual(data["website_url"], "https://example-sosua-villas.com")

    def test_frontend_pages_served(self):
        pages = ["/", "/register", "/login", "/admin", "/dashboard", "/b/caribe-fix-auto"]
        for p in pages:
            status, body = invoke_handler("GET", p)
            self.assertEqual(status, 200, f"Page {p} returned {status}")
            self.assertIn(b"Mavunqo", body)

    def test_restaurant_ordering_http_flow(self):
        # 1. GET restaurant menu
        status, body = invoke_handler("GET", "/api/restaurants/el-batey-bistro/menu")
        self.assertEqual(status, 200)
        menu = json.loads(body.decode("utf-8"))
        self.assertEqual(menu["business_name"], "El Batey Bistro & Grill")
        self.assertTrue(len(menu["categories"]) >= 2)

        snapper_cat = next(c for c in menu["categories"] if c["name_en"] == "Fresh Catch & Grill")
        snapper_item = snapper_cat["items"][0]
        self.assertEqual(snapper_item["name_en"], "Whole Red Snapper with Tostones")

        # 2. POST /api/orders (Guest order)
        order_payload = {
            "business_id": menu["business_id"],
            "customer": {"name": "Carlos Gomez", "phone": "8095551234"},
            "items": [{
                "menu_item_id": snapper_item["id"],
                "quantity": 1,
                "modifiers": [{"id": "mod_chillo_garlic"}]
            }],
            "fulfillment_type": "pickup",
            "order_origin": "mavunqo"
        }
        status, body = invoke_handler("POST", "/api/orders", body=order_payload)
        self.assertEqual(status, 201)
        res = json.loads(body.decode("utf-8"))
        self.assertTrue(res["success"])
        # Snapper 750 + Garlic glaze 50 = 800
        self.assertEqual(res["total"], 800.0)
        token = res["status_token"]

        # 3. GET /api/orders/status?token=...
        status, body = invoke_handler("GET", f"/api/orders/status?token={token}")
        self.assertEqual(status, 200)
        order_status = json.loads(body.decode("utf-8"))
        self.assertEqual(order_status["customer_name"], "Carlos Gomez")
        self.assertEqual(order_status["status"], "pending")

if __name__ == "__main__":
    unittest.main()
