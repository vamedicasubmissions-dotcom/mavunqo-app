"""
Mavunqo Phase 1 - HTTP Server & REST API.
Endpoints:
- GET /api/categories
- GET /api/locations
- GET /api/businesses (search: q, category, location)
- GET /api/businesses/{slug} (public business profile & services)
- POST /api/businesses/register (submit application, optional RNC, pending status)
- POST /api/contact (submit contact request)
- POST /api/auth/login (admin & business owner login)
- GET /api/auth/me (current user profile)
- Admin Endpoints:
  - GET /api/admin/applications (list pending/all applications)
  - POST /api/admin/applications/{id}/approve
  - POST /api/admin/applications/{id}/reject
  - GET /api/admin/analytics
- Owner Endpoints (Authenticated owner):
  - GET /api/owner/businesses
  - PUT /api/owner/businesses/{id}
  - GET /api/owner/businesses/{id}/contacts
- Static Frontend File Serving:
  - / -> frontend/index.html (Directory & Search)
  - /b/{slug} -> frontend/storefront.html (Hosted Storefront / Profile)
  - /register -> frontend/register.html (Business Onboarding)
  - /login -> frontend/login.html (Owner/Admin Sign In)
  - /dashboard -> frontend/dashboard.html (Owner Dashboard)
  - /admin -> frontend/admin.html (Admin Moderation)
  - /assets/* -> static files
"""
import http.server
import socketserver
import json
import os
import urllib.parse
from .db import init_db
from .auth import hash_password, verify_password, generate_token, verify_token
from .service import MavunqoService
from .whatsapp_gateway import verify_webhook_signature, record_and_check_idempotency, process_inbound_opt_keywords
from .whatsapp_bot import WhatsAppOrderBot
from .whatsapp_ordering_service import WhatsAppOrderingService
from .tokens_and_attribution import build_merchant_qr_link, generate_attribution_signature

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "mavunqo.db")
FRONTEND_DIR = os.path.join(BASE_DIR, "frontend")

service = MavunqoService(DB_PATH)
wa_service = WhatsAppOrderingService(DB_PATH)
wa_bot = WhatsAppOrderBot(DB_PATH)

class MavunqoRequestHandler(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        # Enable CORS for local dev / API calls
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        super().end_headers()

    def do_OPTIONS(self):
        self.send_response(204)
        self.end_headers()

    def get_auth_user(self):
        auth_header = self.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:].strip()
            return verify_token(token)
        return None

    def read_json_body(self):
        content_length = int(self.headers.get("Content-Length", 0))
        if content_length == 0:
            return {}
        body = self.rfile.read(content_length)
        return json.loads(body.decode("utf-8"))

    def send_json(self, data, status=200):
        body = json.dumps(data, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def send_file_response(self, file_path, content_type="text/html; charset=utf-8"):
        if not os.path.isfile(file_path):
            self.send_error(404, "Page Not Found")
            return
        with open(file_path, "rb") as f:
            content = f.read()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        query = urllib.parse.parse_qs(parsed.query)

        # 1. API Routes
        if path == "/api/categories":
            return self.send_json(service.get_categories())

        if path == "/api/locations":
            return self.send_json(service.get_locations())

        if path == "/api/businesses":
            q = query.get("q", [""])[0]
            cat = query.get("category", [""])[0]
            loc = query.get("location", [""])[0]
            lang = query.get("lang", ["en"])[0]
            return self.send_json(service.search_businesses(q=q, category_id=cat, location_id=loc, lang=lang))

        if path.startswith("/api/businesses/"):
            slug = path.replace("/api/businesses/", "").strip("/")
            biz = service.get_business_by_slug(slug, require_approved=True)
            if not biz:
                return self.send_json({"error": "Business not found or pending approval"}, 404)
            return self.send_json(biz)

        if path == "/api/auth/me":
            user = self.get_auth_user()
            if not user:
                return self.send_json({"error": "Unauthorized"}, 401)
            return self.send_json(user)

        # Admin Routes
        if path == "/api/admin/applications":
            user = self.get_auth_user()
            if not user or user.get("role") != "admin":
                return self.send_json({"error": "Forbidden: Admin access only"}, 403)
            status = query.get("status", [None])[0]
            return self.send_json(service.get_admin_applications(status=status))

        if path == "/api/admin/analytics":
            user = self.get_auth_user()
            if not user or user.get("role") != "admin":
                return self.send_json({"error": "Forbidden: Admin access only"}, 403)
            return self.send_json(service.get_admin_analytics())

        # Owner Routes
        if path == "/api/owner/businesses":
            user = self.get_auth_user()
            if not user:
                return self.send_json({"error": "Unauthorized"}, 401)
            return self.send_json(service.get_owner_businesses(user["uid"]))

        if path.startswith("/api/owner/businesses/") and path.endswith("/contacts"):
            user = self.get_auth_user()
            if not user:
                return self.send_json({"error": "Unauthorized"}, 401)
            parts = path.split("/")
            biz_id = parts[4]
            try:
                return self.send_json(service.get_business_contact_requests(user["uid"], biz_id))
            except PermissionError as e:
                return self.send_json({"error": str(e)}, 403)

        # Phase 2 Restaurant Ordering Endpoints
        if path.startswith("/api/restaurants/") and path.endswith("/menu"):
            parts = path.split("/")
            slug_or_id = parts[3]
            try:
                return self.send_json(service.get_restaurant_menu(slug_or_id))
            except Exception as e:
                return self.send_json({"error": str(e)}, 404)

        if path.startswith("/api/orders/status"):
            query = urllib.parse.parse_qs(parsed.query)
            token = query.get("token", [""])[0]
            try:
                return self.send_json(service.get_order_by_token(token))
            except Exception as e:
                return self.send_json({"error": str(e)}, 404)

        if path.startswith("/api/owner/businesses/") and path.endswith("/catalog"):
            user = self.get_auth_user()
            if not user:
                return self.send_json({"error": "Unauthorized"}, 401)
            parts = path.split("/")
            biz_id = parts[4]
            try:
                return self.send_json(service.get_merchant_catalog_items(user["uid"], biz_id))
            except PermissionError as e:
                return self.send_json({"error": str(e)}, 403)
            except Exception as e:
                return self.send_json({"error": str(e)}, 400)

        if path.startswith("/api/owner/businesses/") and path.endswith("/orders"):
            user = self.get_auth_user()
            if not user:
                return self.send_json({"error": "Unauthorized"}, 401)
            parts = path.split("/")
            biz_id = parts[4]
            try:
                return self.send_json(service.get_merchant_orders(user["uid"], biz_id))
            except PermissionError as e:
                return self.send_json({"error": str(e)}, 403)
            except Exception as e:
                return self.send_json({"error": str(e)}, 400)

        if path.startswith("/api/owner/businesses/") and path.endswith("/fee-statement"):
            user = self.get_auth_user()
            if not user:
                return self.send_json({"error": "Unauthorized"}, 401)
            parts = path.split("/")
            biz_id = parts[4]
            try:
                return self.send_json(service.get_merchant_fee_statement(user["uid"], biz_id))
            except PermissionError as e:
                return self.send_json({"error": str(e)}, 403)
            except Exception as e:
                return self.send_json({"error": str(e)}, 400)

        # Multi-Vertical / Hospitality Endpoints
        if path.startswith("/api/hospitality/") and path.endswith("/units"):
            parts = path.split("/")
            slug_or_id = parts[3]
            try:
                return self.send_json(service.get_lodging_units(slug_or_id))
            except Exception as e:
                return self.send_json({"error": str(e)}, 404)

        if path.startswith("/api/owner/businesses/") and path.endswith("/reservations"):
            user = self.get_auth_user()
            if not user:
                return self.send_json({"error": "Unauthorized"}, 401)
            parts = path.split("/")
            biz_id = parts[4]
            try:
                return self.send_json(service.get_staff_reservations(user["uid"], biz_id))
            except PermissionError as e:
                return self.send_json({"error": str(e)}, 403)
            except Exception as e:
                return self.send_json({"error": str(e)}, 400)

        # Order In-App Masked Chat Messages (GET)
        if path == "/api/orders/messages":
            query_params = urllib.parse.parse_qs(parsed.query)
            token = query_params.get("token", [""])[0]
            order_id = query_params.get("order_id", [""])[0]
            try:
                return self.send_json(service.get_order_messages(order_id=order_id, status_token=token))
            except Exception as e:
                return self.send_json({"error": str(e)}, 400)

        # AI Concierge Endpoint (GET)
        if path == "/api/concierge":
            query_params = urllib.parse.parse_qs(parsed.query)
            q = query_params.get("q", [""])[0]
            lang = query_params.get("lang", ["en"])[0]
            return self.send_json(service.ask_ai_concierge(q, lang))

        # WhatsApp Webhook Challenge Verification (GET)
        if path == "/api/whatsapp/webhook":
            hub_mode = query.get("hub.mode", [""])[0]
            hub_challenge = query.get("hub.challenge", [""])[0]
            hub_token = query.get("hub.verify_token", [""])[0]
            if hub_mode == "subscribe" and hub_token == "mavunqo_wa_verify_2026":
                self.send_response(200)
                self.send_header("Content-Type", "text/plain")
                self.end_headers()
                self.wfile.write(hub_challenge.encode("utf-8"))
                return
            return self.send_json({"error": "Forbidden"}, 403)

        # Secure Single-Use Order Checkout Details (GET)
        if path == "/api/orders/secure-checkout":
            token = query.get("token", [""])[0]
            with service.get_connection() as conn:
                tok_row = conn.execute(
                    "SELECT * FROM secure_order_tokens WHERE token = ? AND status = 'active'",
                    (token,)
                ).fetchone()
                if not tok_row:
                    return self.send_json({"error": "Invalid or revoked checkout token"}, 404)
                import time
                if tok_row["expires_at"] < int(time.time()):
                    return self.send_json({"error": "Checkout link has expired"}, 410)
                
                biz = conn.execute("SELECT * FROM businesses WHERE id = ?", (tok_row["business_id"],)).fetchone()
                return self.send_json({
                    "token": token,
                    "business": {
                        "id": biz["id"],
                        "name": biz["trading_name"],
                        "cash_only": bool(biz["cash_only"]),
                        "delivery_enabled": bool(biz["delivery_enabled"])
                    },
                    "expires_at": tok_row["expires_at"]
                })

        # Merchant Operational Dashboard Orders (GET)
        if path.startswith("/api/merchant/dashboard/orders"):
            user = self.get_auth_user()
            if not user:
                return self.send_json({"error": "Unauthorized"}, 401)
            biz_id = query.get("business_id", [""])[0]
            status_filter = query.get("status", [""])[0]
            try:
                orders = wa_service.get_merchant_operational_orders(user["uid"], biz_id, status_filter)
                return self.send_json(orders)
            except PermissionError as e:
                return self.send_json({"error": str(e)}, 403)
            except Exception as e:
                return self.send_json({"error": str(e)}, 400)

        # Privacy-Sanitized CSV Export (GET)
        if path.startswith("/api/merchant/export/orders"):
            user = self.get_auth_user()
            if not user:
                return self.send_json({"error": "Unauthorized"}, 401)
            biz_id = query.get("business_id", [""])[0]
            try:
                csv_data = wa_service.generate_sanitized_csv_export(user["uid"], biz_id)
                body = csv_data.encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "text/csv; charset=utf-8")
                self.send_header("Content-Disposition", f'attachment; filename="orders_{biz_id}.csv"')
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return
            except PermissionError as e:
                return self.send_json({"error": str(e)}, 403)
            except Exception as e:
                return self.send_json({"error": str(e)}, 400)

        # 2. Frontend Page Routes
        if path == "/" or path == "/index.html":
            return self.send_file_response(os.path.join(FRONTEND_DIR, "index.html"))

        if path.startswith("/b/"):
            # Hosted storefront / profile route
            return self.send_file_response(os.path.join(FRONTEND_DIR, "storefront.html"))

        if path == "/order/status":
            return self.send_file_response(os.path.join(FRONTEND_DIR, "order_status.html"))

        if path == "/orders":
            return self.send_file_response(os.path.join(FRONTEND_DIR, "orders.html"))

        if path == "/staff":
            return self.send_file_response(os.path.join(FRONTEND_DIR, "staff.html"))

        if path == "/register":
            return self.send_file_response(os.path.join(FRONTEND_DIR, "register.html"))

        if path == "/login":
            return self.send_file_response(os.path.join(FRONTEND_DIR, "login.html"))

        if path == "/dashboard":
            return self.send_file_response(os.path.join(FRONTEND_DIR, "dashboard.html"))

        if path == "/merchant/ops" or path == "/merchant/orders":
            return self.send_file_response(os.path.join(FRONTEND_DIR, "merchant_ops.html"))

        if path == "/order/checkout":
            return self.send_file_response(os.path.join(FRONTEND_DIR, "checkout.html"))

        if path == "/admin":
            return self.send_file_response(os.path.join(FRONTEND_DIR, "admin.html"))

        # Assets or static files
        if path.startswith("/assets/") or path.startswith("/frontend/"):
            rel_path = path.lstrip("/")
            full_path = os.path.join(BASE_DIR, rel_path)
            content_type = "text/plain"
            if full_path.endswith(".css"):
                content_type = "text/css"
            elif full_path.endswith(".js"):
                content_type = "application/javascript"
            elif full_path.endswith(".html"):
                content_type = "text/html; charset=utf-8"
            elif full_path.endswith(".jpg") or full_path.endswith(".jpeg"):
                content_type = "image/jpeg"
            elif full_path.endswith(".png"):
                content_type = "image/png"
            elif full_path.endswith(".webp"):
                content_type = "image/webp"
            elif full_path.endswith(".gif"):
                content_type = "image/gif"
            return self.send_file_response(full_path, content_type)

        return self.send_error(404, "Not Found")

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        # Photo Upload endpoint for clothing/food catalog & storefronts
        if path == "/api/upload":
            user = self.get_auth_user()
            if not user:
                return self.send_json({"error": "Unauthorized"}, 401)
            data = self.read_json_body()
            data_url = data.get("image", "")
            filename = data.get("filename", "upload.jpg")
            if not data_url:
                return self.send_json({"error": "No image data provided"}, 400)

            import base64
            import uuid
            try:
                if "," in data_url:
                    header, base64_data = data_url.split(",", 1)
                else:
                    base64_data = data_url

                raw_bytes = base64.b64decode(base64_data)
                ext = ".jpg"
                if "png" in filename.lower() or "png" in data_url[:30]:
                    ext = ".png"
                elif "webp" in filename.lower() or "webp" in data_url[:30]:
                    ext = ".webp"

                unique_name = f"photo_{uuid.uuid4().hex[:12]}{ext}"
                save_dir = os.path.join(FRONTEND_DIR, "uploads")
                os.makedirs(save_dir, exist_ok=True)
                target_path = os.path.join(save_dir, unique_name)
                with open(target_path, "wb") as img_f:
                    img_f.write(raw_bytes)

                public_url = f"/frontend/uploads/{unique_name}"
                return self.send_json({"url": public_url, "filename": unique_name}, 201)
            except Exception as e:
                return self.send_json({"error": f"Failed to process image: {str(e)}"}, 400)

        # 1. Login
        if path == "/api/auth/login":
            data = self.read_json_body()
            email = data.get("email", "").strip().lower()
            password = data.get("password", "")
            with service.get_connection() as conn:
                user = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
                if not user or not verify_password(user["password_hash"], password):
                    return self.send_json({"error": "Invalid email or password"}, 401)
                token = generate_token(user["id"], user["email"], user["role"])
                return self.send_json({
                    "token": token,
                    "user": {
                        "id": user["id"],
                        "email": user["email"],
                        "full_name": user["full_name"],
                        "role": user["role"]
                    }
                })

        # 2. Business Registration (Onboarding)
        if path == "/api/businesses/register":
            data = self.read_json_body()
            try:
                res = service.register_business(
                    owner_name=data.get("owner_name", ""),
                    owner_email=data.get("owner_email", ""),
                    password=data.get("password", "Pass2026!"),
                    trading_name=data.get("trading_name", ""),
                    category_id=data.get("category_id", ""),
                    primary_location_id=data.get("primary_location_id", ""),
                    description_en=data.get("description_en", ""),
                    description_es=data.get("description_es", ""),
                    phone=data.get("phone", ""),
                    whatsapp=data.get("whatsapp", ""),
                    website_url=data.get("website_url", ""),
                    address=data.get("address", ""),
                    serves_entire_area=bool(data.get("serves_entire_area")),
                    rnc_tax_id=data.get("rnc_tax_id"), # Optional
                    service_area_ids=data.get("service_area_ids", []),
                    initial_services=data.get("services", []),
                    legal_name=data.get("legal_name")
                )
                return self.send_json({
                    "success": True,
                    "message": "Application submitted successfully and is awaiting review.",
                    "data": res
                }, 201)
            except Exception as e:
                return self.send_json({"error": str(e)}, 400)

        # 3. Contact Form Submission
        if path == "/api/contact":
            data = self.read_json_body()
            try:
                res = service.submit_contact_form(
                    business_id=data.get("business_id", ""),
                    sender_name=data.get("name", ""),
                    sender_contact=data.get("contact", ""),
                    message=data.get("message", "")
                )
                return self.send_json({"success": True, "message": "Message sent to business.", "data": res})
            except Exception as e:
                return self.send_json({"error": str(e)}, 400)

        # Phase 2: Place Guest Order
        if path == "/api/orders":
            data = self.read_json_body()
            try:
                res = service.place_order(
                    business_id=data.get("business_id", ""),
                    customer_data=data.get("customer", {}),
                    items=data.get("items", []),
                    fulfillment_type=data.get("fulfillment_type", "pickup"),
                    delivery_address=data.get("delivery_address", ""),
                    order_origin=data.get("order_origin", "mavunqo"),
                    customer_notes=data.get("notes", "")
                )
                return self.send_json(res, 201)
            except Exception as e:
                return self.send_json({"error": str(e)}, 400)

        # Phase 2: Merchant Update Order Status
        if path.startswith("/api/owner/businesses/") and path.endswith("/catalog"):
            user = self.get_auth_user()
            if not user:
                return self.send_json({"error": "Unauthorized"}, 401)
            parts = path.split("/")
            biz_id = parts[4]
            data = self.read_json_body()
            try:
                res = service.add_merchant_catalog_item(user["uid"], biz_id, data)
                return self.send_json(res, 201)
            except PermissionError as e:
                return self.send_json({"error": str(e)}, 403)
            except Exception as e:
                return self.send_json({"error": str(e)}, 400)

        if path.startswith("/api/owner/businesses/") and "/orders/" in path and path.endswith("/status"):
            user = self.get_auth_user()
            if not user:
                return self.send_json({"error": "Unauthorized"}, 401)
            parts = path.split("/")
            biz_id = parts[4]
            order_id = parts[6]
            data = self.read_json_body()
            try:
                res = service.update_order_status(
                    user_id=user["uid"],
                    business_id=biz_id,
                    order_id=order_id,
                    new_status=data.get("status", ""),
                    estimated_minutes=int(data.get("estimated_minutes", 0)),
                    reason=data.get("reason", ""),
                    cash_received=data.get("cash_received")
                )
                return self.send_json(res)
            except PermissionError as e:
                return self.send_json({"error": str(e)}, 403)
            except Exception as e:
                return self.send_json({"error": str(e)}, 400)

        # Multi-Vertical: Book Hospitality Lodging Unit (City Lights)
        if path == "/api/hospitality/book":
            data = self.read_json_body()
            try:
                res = service.book_lodging_unit(
                    business_id=data.get("business_id", ""),
                    unit_id=data.get("unit_id", ""),
                    guest_data=data.get("guest", {}),
                    check_in=data.get("check_in", ""),
                    check_out=data.get("check_out", ""),
                    guest_count=int(data.get("guest_count", 1))
                )
                return self.send_json(res, 201)
            except Exception as e:
                return self.send_json({"error": str(e)}, 400)

        # Multi-Vertical: Staff Check-in & Cash Collection
        if path.startswith("/api/owner/businesses/") and "/reservations/" in path and path.endswith("/checkin"):
            user = self.get_auth_user()
            if not user:
                return self.send_json({"error": "Unauthorized"}, 401)
            parts = path.split("/")
            biz_id = parts[4]
            res_id = parts[6]
            data = self.read_json_body()
            try:
                res = service.process_staff_checkin(
                    user_id=user["uid"],
                    business_id=biz_id,
                    reservation_id=res_id,
                    cash_collected=float(data.get("cash_collected", 0.0)),
                    staff_notes=data.get("notes", "")
                )
                return self.send_json(res)
            except PermissionError as e:
                return self.send_json({"error": str(e)}, 403)
            except Exception as e:
                return self.send_json({"error": str(e)}, 400)

        # Order In-App Masked Chat Post (POST)
        if path == "/api/orders/messages":
            data = self.read_json_body()
            token = data.get("token", "")
            order_id = data.get("order_id", "")
            msg = data.get("message", "")
            sender_role = data.get("sender_role", "customer")
            sender_name = data.get("sender_name", "")
            try:
                res = service.post_order_message(
                    message=msg,
                    sender_role=sender_role,
                    sender_name=sender_name,
                    order_id=order_id,
                    status_token=token
                )
                return self.send_json(res, 201)
            except Exception as e:
                return self.send_json({"error": str(e)}, 400)

        # WhatsApp Inbound Webhook (POST)
        if path == "/api/whatsapp/webhook":
            content_length = int(self.headers.get("Content-Length", 0))
            payload_bytes = self.rfile.read(content_length)
            raw_payload = payload_bytes.decode("utf-8")
            sig_header = self.headers.get("X-Hub-Signature-256", "")
            
            # Verify signature if header present
            if sig_header and not verify_webhook_signature(payload_bytes, sig_header):
                return self.send_json({"error": "Invalid signature"}, 401)
                
            try:
                event_data = json.loads(raw_payload)
            except Exception:
                return self.send_json({"error": "Malformed JSON"}, 400)
                
            import uuid
            event_id = event_data.get("id", "evt_" + uuid.uuid4().hex[:12])
            entry = event_data.get("entry", [{}])[0]
            changes = entry.get("changes", [{}])[0]
            val = changes.get("value", {})
            messages = val.get("messages", [])
            
            if not messages:
                return self.send_json({"status": "acknowledged"})
                
            msg = messages[0]
            msg_id = msg.get("id", "msg_" + uuid.uuid4().hex[:12])
            from_phone = msg.get("from", "")
            text_body = msg.get("text", {}).get("body", "")
            
            # Idempotency guard
            if not record_and_check_idempotency(DB_PATH, event_id, msg_id, "message", raw_payload):
                return self.send_json({"status": "duplicate_ignored"}, 200)
                
            # Check opt keywords (STOP / START)
            opt_resp = process_inbound_opt_keywords(DB_PATH, from_phone, text_body)
            if opt_resp:
                return self.send_json({"status": "opt_handled", "response": opt_resp})
                
            # Process via Grounded WhatsApp Bot
            bot_result = wa_bot.handle_message(from_phone, text_body)
            return self.send_json({"status": "processed", "bot": bot_result})

        # Confirm Secure Single-Use Order (POST)
        if path == "/api/orders/secure-checkout/confirm":
            data = self.read_json_body()
            token = data.get("token", "")
            with service.get_connection() as conn:
                tok = conn.execute(
                    "SELECT * FROM secure_order_tokens WHERE token = ? AND status = 'active'",
                    (token,)
                ).fetchone()
                if not tok:
                    return self.send_json({"error": "Single-use token already consumed, revoked or invalid."}, 400)
                import time
                if tok["expires_at"] < int(time.time()):
                    conn.execute("UPDATE secure_order_tokens SET status = 'expired' WHERE token = ?", (token,))
                    conn.commit()
                    return self.send_json({"error": "Token has expired."}, 410)
                
                # Consume token immediately
                conn.execute("UPDATE secure_order_tokens SET status = 'consumed' WHERE token = ?", (token,))
                conn.commit()
                
            try:
                res = wa_service.create_whatsapp_assisted_order(
                    business_id=data.get("business_id", ""),
                    customer_phone=data.get("customer_phone", "8095551234"),
                    items=data.get("items", []),
                    fulfillment_type=data.get("fulfillment_type", "delivery"),
                    delivery_address=data.get("delivery_address", ""),
                    customer_notes=data.get("notes", ""),
                    attribution_payload=data.get("attribution")
                )
                return self.send_json(res, 201)
            except Exception as e:
                return self.send_json({"error": str(e)}, 400)

        # Merchant Ops: Update Status (POST)
        if path.startswith("/api/merchant/orders/") and path.endswith("/status"):
            user = self.get_auth_user()
            if not user:
                return self.send_json({"error": "Unauthorized"}, 401)
            parts = path.split("/")
            order_id = parts[4]
            data = self.read_json_body()
            try:
                res = wa_service.update_order_status_by_staff(
                    user_id=user["uid"],
                    business_id=data.get("business_id", ""),
                    order_id=order_id,
                    new_status=data.get("status", ""),
                    notes=data.get("notes", "")
                )
                return self.send_json(res)
            except PermissionError as e:
                return self.send_json({"error": str(e)}, 403)
            except Exception as e:
                return self.send_json({"error": str(e)}, 400)

        # Merchant Ops: Record Cash Collection (POST)
        if path.startswith("/api/merchant/orders/") and path.endswith("/cash-record"):
            user = self.get_auth_user()
            if not user:
                return self.send_json({"error": "Unauthorized"}, 401)
            parts = path.split("/")
            order_id = parts[4]
            data = self.read_json_body()
            try:
                res = wa_service.record_cash_collection(
                    user_id=user["uid"],
                    business_id=data.get("business_id", ""),
                    order_id=order_id,
                    amount_collected=float(data.get("amount_collected", 0.0)),
                    is_exception=bool(data.get("is_exception", False)),
                    exception_notes=data.get("notes", "")
                )
                return self.send_json(res)
            except PermissionError as e:
                return self.send_json({"error": str(e)}, 403)
            except Exception as e:
                return self.send_json({"error": str(e)}, 400)

        # Merchant Ops: Propose Substitution (POST)
        if path.startswith("/api/merchant/orders/") and path.endswith("/substitutions"):
            user = self.get_auth_user()
            if not user:
                return self.send_json({"error": "Unauthorized"}, 401)
            parts = path.split("/")
            order_id = parts[4]
            data = self.read_json_body()
            try:
                res = wa_service.propose_item_substitution(
                    user_id=user["uid"],
                    business_id=data.get("business_id", ""),
                    order_id=order_id,
                    original_item_id=data.get("original_item_id", ""),
                    proposed_item_id=data.get("proposed_item_id", "")
                )
                return self.send_json(res)
            except PermissionError as e:
                return self.send_json({"error": str(e)}, 403)
            except Exception as e:
                return self.send_json({"error": str(e)}, 400)

        # Merchant Ops: Controlled Manual WhatsApp Fallback (POST)
        if path.startswith("/api/merchant/orders/") and path.endswith("/fallback-handoff"):
            user = self.get_auth_user()
            if not user:
                return self.send_json({"error": "Unauthorized"}, 401)
            parts = path.split("/")
            order_id = parts[4]
            data = self.read_json_body()
            try:
                res = wa_service.initiate_manual_whatsapp_fallback(
                    user_id=user["uid"],
                    business_id=data.get("business_id", ""),
                    order_id=order_id,
                    reason=data.get("reason", "")
                )
                return self.send_json(res)
            except PermissionError as e:
                return self.send_json({"error": str(e)}, 403)
            except Exception as e:
                return self.send_json({"error": str(e)}, 400)

        # Break-Glass Exceptional Customer Access (POST)
        if path.startswith("/api/admin/orders/") and path.endswith("/exceptional-access"):
            user = self.get_auth_user()
            if not user:
                return self.send_json({"error": "Unauthorized"}, 401)
            parts = path.split("/")
            order_id = parts[4]
            data = self.read_json_body()
            try:
                res = wa_service.break_glass_exceptional_access(
                    user_id=user["uid"],
                    business_id=data.get("business_id", ""),
                    order_id=order_id,
                    reason=data.get("reason", "")
                )
                return self.send_json(res)
            except PermissionError as e:
                return self.send_json({"error": str(e)}, 403)
            except Exception as e:
                return self.send_json({"error": str(e)}, 400)

        # 4. Admin Approvals
        if path.startswith("/api/admin/applications/") and path.endswith("/approve"):
            user = self.get_auth_user()
            if not user or user.get("role") != "admin":
                return self.send_json({"error": "Forbidden: Admin access only"}, 403)
            parts = path.split("/")
            biz_id = parts[4]
            try:
                service.approve_business(user["uid"], biz_id)
                return self.send_json({"success": True, "message": "Business approved and published!"})
            except Exception as e:
                return self.send_json({"error": str(e)}, 400)

        if path.startswith("/api/admin/applications/") and path.endswith("/reject"):
            user = self.get_auth_user()
            if not user or user.get("role") != "admin":
                return self.send_json({"error": "Forbidden: Admin access only"}, 403)
            parts = path.split("/")
            biz_id = parts[4]
            data = self.read_json_body()
            try:
                service.reject_business(user["uid"], biz_id, reason=data.get("reason", "Did not meet requirements"))
                return self.send_json({"success": True, "message": "Business application rejected."})
            except Exception as e:
                return self.send_json({"error": str(e)}, 400)

        return self.send_error(404, "Not Found")

    def do_PUT(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        if path.startswith("/api/owner/businesses/") and "/catalog/" in path:
            user = self.get_auth_user()
            if not user:
                return self.send_json({"error": "Unauthorized"}, 401)
            parts = path.split("/")
            biz_id = parts[4]
            item_id = parts[6]
            data = self.read_json_body()
            try:
                res = service.update_merchant_catalog_item(user["uid"], biz_id, item_id, data)
                return self.send_json(res)
            except PermissionError as e:
                return self.send_json({"error": str(e)}, 403)
            except Exception as e:
                return self.send_json({"error": str(e)}, 400)

        if path.startswith("/api/owner/businesses/"):
            user = self.get_auth_user()
            if not user:
                return self.send_json({"error": "Unauthorized"}, 401)
            biz_id = path.replace("/api/owner/businesses/", "").strip("/")
            data = self.read_json_body()
            try:
                res = service.update_business_profile(user["uid"], biz_id, data)
                return self.send_json(res)
            except PermissionError as e:
                return self.send_json({"error": str(e)}, 403)
            except Exception as e:
                return self.send_json({"error": str(e)}, 400)

        return self.send_error(404, "Not Found")

    def do_DELETE(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        if path.startswith("/api/owner/businesses/") and "/catalog/" in path:
            user = self.get_auth_user()
            if not user:
                return self.send_json({"error": "Unauthorized"}, 401)
            parts = path.split("/")
            biz_id = parts[4]
            item_id = parts[6]
            try:
                res = service.delete_merchant_catalog_item(user["uid"], biz_id, item_id)
                return self.send_json(res)
            except PermissionError as e:
                return self.send_json({"error": str(e)}, 403)
            except Exception as e:
                return self.send_json({"error": str(e)}, 400)

        return self.send_error(404, "Not Found")

def run_server(port=8080, db_path=None):
    if db_path:
        global service
        service = MavunqoService(db_path)
    server_address = ('0.0.0.0', port)
    socketserver.TCPServer.allow_reuse_address = True
    httpd = socketserver.TCPServer(server_address, MavunqoRequestHandler)
    print(f"Mavunqo server active on http://127.0.0.1:{port} and http://localhost:{port}", flush=True)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()

if __name__ == "__main__":
    from .seed import seed_database
    seed_database(DB_PATH)
    port = int(os.environ.get("PORT", 8080))
    run_server(port)
