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
- Admin Endpoints (Jay only):
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
  - /admin -> frontend/admin.html (Jay Admin Moderation)
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

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "mavunqo.db")
FRONTEND_DIR = os.path.join(BASE_DIR, "frontend")

service = MavunqoService(DB_PATH)

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
                return self.send_json({"error": "Forbidden: Jay admin only"}, 403)
            status = query.get("status", [None])[0]
            return self.send_json(service.get_admin_applications(status=status))

        if path == "/api/admin/analytics":
            user = self.get_auth_user()
            if not user or user.get("role") != "admin":
                return self.send_json({"error": "Forbidden: Jay admin only"}, 403)
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

        # 2. Frontend Page Routes
        if path == "/" or path == "/index.html":
            return self.send_file_response(os.path.join(FRONTEND_DIR, "index.html"))

        if path.startswith("/b/"):
            # Hosted storefront / profile route
            return self.send_file_response(os.path.join(FRONTEND_DIR, "storefront.html"))

        if path == "/register":
            return self.send_file_response(os.path.join(FRONTEND_DIR, "register.html"))

        if path == "/login":
            return self.send_file_response(os.path.join(FRONTEND_DIR, "login.html"))

        if path == "/dashboard":
            return self.send_file_response(os.path.join(FRONTEND_DIR, "dashboard.html"))

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
            return self.send_file_response(full_path, content_type)

        return self.send_error(404, "Not Found")

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

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
                    "message": "Application submitted successfully and is awaiting review by Jay.",
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

        # 4. Admin Approvals
        if path.startswith("/api/admin/applications/") and path.endswith("/approve"):
            user = self.get_auth_user()
            if not user or user.get("role") != "admin":
                return self.send_json({"error": "Forbidden: Jay admin only"}, 403)
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
                return self.send_json({"error": "Forbidden: Jay admin only"}, 403)
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

def run_server(port=8080, db_path=None):
    if db_path:
        global service
        service = MavunqoService(db_path)
    server_address = ('', port)
    httpd = socketserver.TCPServer(server_address, MavunqoRequestHandler)
    print(f"Mavunqo Phase 1 server running at http://localhost:{port}")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()

if __name__ == "__main__":
    from .seed import seed_database
    seed_database(DB_PATH)
    run_server(8080)
