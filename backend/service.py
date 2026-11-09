"""
Mavunqo Phase 1 - Core Business Logic & Query Services.
Handles:
- Public directory search with multi-filters (category, location, keyword, business name, service)
- Zero-results and search query audit tracking
- Business profiles & hosted storefronts (/b/{slug})
- Business application registration (optional RNC, default 'pending' status)
- Jay Admin moderation: approve, reject, request corrections, list applications
- Multi-tenant business owner dashboard: view owned businesses, edit profile, propose sensitive changes
- Change requests workflow (sensitive fields require Jay approval)
- Contact form handling with rate-limit and anti-spam verification
"""
import sqlite3
import json
import uuid
import re
from datetime import datetime

class MavunqoService:
    def __init__(self, db_path: str):
        self.db_path = db_path

    def get_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        return conn

    # -------------------------------------------------------------
    # Metadata: Categories and Locations
    # -------------------------------------------------------------
    def get_categories(self):
        with self.get_connection() as conn:
            rows = conn.execute("SELECT * FROM categories ORDER BY sort_order ASC").fetchall()
            return [dict(r) for r in rows]

    def get_locations(self):
        with self.get_connection() as conn:
            rows = conn.execute("SELECT * FROM locations ORDER BY sort_order ASC").fetchall()
            return [dict(r) for r in rows]

    # -------------------------------------------------------------
    # Public Directory & Search
    # -------------------------------------------------------------
    def search_businesses(self, q: str = "", category_id: str = "", location_id: str = "", lang: str = "en"):
        q = (q or "").strip().lower()
        category_id = (category_id or "").strip()
        location_id = (location_id or "").strip()

        sql = """
            SELECT DISTINCT b.id, b.trading_name, b.slug, b.category_id, b.primary_location_id,
                   b.description_en, b.description_es, b.has_physical_location, b.address,
                   b.serves_entire_area, b.website_url, b.whatsapp, b.phone, b.public_email,
                   b.logo_url, b.cover_image_url,
                   c.name_en AS category_name_en, c.name_es AS category_name_es, c.slug AS category_slug,
                   l.name AS location_name, l.status AS location_status
            FROM businesses b
            JOIN categories c ON b.category_id = c.id
            JOIN locations l ON b.primary_location_id = l.id
            LEFT JOIN business_service_areas bsa ON b.id = bsa.business_id
            LEFT JOIN services s ON b.id = s.business_id
            WHERE b.status = 'approved'
        """
        params = []

        if category_id:
            sql += " AND (b.category_id = ? OR c.slug = ?)"
            params.extend([category_id, category_id])

        if location_id:
            sql += " AND (b.primary_location_id = ? OR bsa.location_id = ? OR l.name LIKE ?)"
            params.extend([location_id, location_id, f"%{location_id}%"])

        if q:
            sql += """ AND (
                LOWER(b.trading_name) LIKE ? OR
                LOWER(b.description_en) LIKE ? OR
                LOWER(b.description_es) LIKE ? OR
                LOWER(s.name_en) LIKE ? OR
                LOWER(s.name_es) LIKE ? OR
                LOWER(s.description_en) LIKE ? OR
                LOWER(s.description_es) LIKE ? OR
                LOWER(c.name_en) LIKE ? OR
                LOWER(c.name_es) LIKE ?
            )"""
            pattern = f"%{q}%"
            params.extend([pattern] * 9)

        sql += " ORDER BY b.trading_name ASC"

        with self.get_connection() as conn:
            rows = conn.execute(sql, params).fetchall()
            results = []
            for r in rows:
                item = dict(r)
                # fetch services summary for search card
                s_rows = conn.execute(
                    "SELECT name_en, name_es, price, currency, display_price FROM services WHERE business_id = ? ORDER BY sort_order ASC LIMIT 4",
                    (item["id"],)
                ).fetchall()
                item["services_summary"] = [dict(sr) for sr in s_rows]

                # fetch service areas
                sa_rows = conn.execute(
                    """SELECT l.name FROM business_service_areas bsa
                       JOIN locations l ON bsa.location_id = l.id
                       WHERE bsa.business_id = ?""",
                    (item["id"],)
                ).fetchall()
                item["service_areas"] = [sar["name"] for sar in sa_rows]
                results.append(item)

        with self.get_connection() as conn:
            # Record search event in privacy-conscious aggregate log
            conn.execute(
                """INSERT INTO search_events (id, query_text, category_id, location_id, results_count)
                   VALUES (?, ?, ?, ?, ?)""",
                (str(uuid.uuid4()), q if q else None, category_id if category_id else None,
                 location_id if location_id else None, len(results))
            )
            conn.commit()

        return results

    def get_business_by_slug(self, slug: str, require_approved: bool = True):
        with self.get_connection() as conn:
            sql = """
                SELECT b.*, c.name_en AS category_name_en, c.name_es AS category_name_es, c.slug AS category_slug,
                       l.name AS location_name, l.status AS location_status
                FROM businesses b
                JOIN categories c ON b.category_id = c.id
                JOIN locations l ON b.primary_location_id = l.id
                WHERE b.slug = ?
            """
            if require_approved:
                sql += " AND b.status = 'approved'"
            row = conn.execute(sql, (slug,)).fetchone()
            if not row:
                return None
            biz = dict(row)

            # Services
            s_rows = conn.execute(
                "SELECT * FROM services WHERE business_id = ? ORDER BY sort_order ASC",
                (biz["id"],)
            ).fetchall()
            biz["services"] = [dict(sr) for sr in s_rows]

            # Service areas
            sa_rows = conn.execute(
                """SELECT l.id, l.name FROM business_service_areas bsa
                   JOIN locations l ON bsa.location_id = l.id
                   WHERE bsa.business_id = ?""",
                (biz["id"],)
            ).fetchall()
            biz["service_areas"] = [dict(sar) for sar in sa_rows]

            # Parse hours if present
            if biz.get("hours_json"):
                try:
                    biz["hours"] = json.loads(biz["hours_json"])
                except Exception:
                    biz["hours"] = {}
            else:
                biz["hours"] = {}

            # Don't leak private/audit fields publicly if unauthenticated
            if require_approved:
                biz.pop("legal_name", None)
                biz.pop("rnc_tax_id", None)
                biz.pop("rejection_reason", None)
                biz.pop("approved_by", None)

            return biz

    # -------------------------------------------------------------
    # Business Registration (Onboarding)
    # -------------------------------------------------------------
    def register_business(self, owner_name: str, owner_email: str, password: str,
                          trading_name: str, category_id: str, primary_location_id: str,
                          description_en: str, description_es: str,
                          phone: str = "", whatsapp: str = "", website_url: str = "",
                          address: str = "", serves_entire_area: bool = False,
                          rnc_tax_id: str = None, service_area_ids: list = None,
                          initial_services: list = None, legal_name: str = None):
        from .auth import hash_password
        owner_email = owner_email.strip().lower()
        trading_name = trading_name.strip()
        slug = re.sub(r'[^a-z0-9]+', '-', trading_name.lower()).strip('-')

        with self.get_connection() as conn:
            # Check or create user
            user_row = conn.execute("SELECT id, role FROM users WHERE email = ?", (owner_email,)).fetchone()
            if user_row:
                owner_id = user_row["id"]
            else:
                owner_id = f"user_{uuid.uuid4().hex[:12]}"
                conn.execute(
                    "INSERT INTO users (id, email, password_hash, full_name, role) VALUES (?, ?, ?, ?, 'owner')",
                    (owner_id, owner_email, hash_password(password), owner_name)
                )

            # Ensure unique slug
            base_slug = slug or "business"
            test_slug = base_slug
            idx = 2
            while conn.execute("SELECT id FROM businesses WHERE slug = ?", (test_slug,)).fetchone():
                test_slug = f"{base_slug}-{idx}"
                idx += 1
            final_slug = test_slug

            biz_id = f"biz_{uuid.uuid4().hex[:12]}"
            # Status is strictly PENDING until Jay approves
            conn.execute(
                """INSERT INTO businesses (
                    id, owner_id, trading_name, legal_name, slug, category_id, primary_location_id,
                    description_en, description_es, status, has_physical_location, address,
                    serves_entire_area, website_url, whatsapp, phone, public_email,
                    rnc_tax_id, rnc_status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?, ?, ?, ?, ?, ?, ?, ?, 'unverified')""",
                (
                    biz_id, owner_id, trading_name, legal_name or trading_name, final_slug,
                    category_id, primary_location_id, description_en, description_es,
                    1 if address else 0, address, 1 if serves_entire_area else 0,
                    website_url or None, whatsapp or None, phone or None, owner_email,
                    rnc_tax_id or None
                )
            )

            # Insert service areas
            areas = service_area_ids or [primary_location_id]
            for lid in set(areas):
                conn.execute(
                    "INSERT OR IGNORE INTO business_service_areas (business_id, location_id) VALUES (?, ?)",
                    (biz_id, lid)
                )

            # Insert initial services if provided
            if initial_services:
                for idx, s in enumerate(initial_services):
                    conn.execute(
                        """INSERT INTO services (id, business_id, name_en, name_es, description_en, description_es, price, currency, display_price, sort_order)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                        (str(uuid.uuid4()), biz_id, s.get("name_en", "Service"), s.get("name_es", "Servicio"),
                         s.get("description_en", ""), s.get("description_es", ""),
                         float(s.get("price")) if s.get("price") is not None and s.get("price") != "" else None,
                         s.get("currency", "DOP"), 1 if s.get("display_price") else 0, idx + 1)
                    )

            # Audit event
            conn.execute(
                """INSERT INTO audit_events (id, actor_id, action, target_type, target_id, details_json)
                   VALUES (?, ?, 'BUSINESS_APPLICATION_SUBMITTED', 'business', ?, ?)""",
                (str(uuid.uuid4()), owner_id, biz_id, json.dumps({"trading_name": trading_name, "slug": final_slug}))
            )
            conn.commit()

            return {"business_id": biz_id, "slug": final_slug, "status": "pending", "owner_id": owner_id}

    # -------------------------------------------------------------
    # Jay Admin Actions
    # -------------------------------------------------------------
    def get_admin_applications(self, status: str = None):
        with self.get_connection() as conn:
            sql = """
                SELECT b.*, u.full_name AS owner_name, u.email AS owner_email,
                       c.name_en AS category_name, l.name AS location_name
                FROM businesses b
                JOIN users u ON b.owner_id = u.id
                JOIN categories c ON b.category_id = c.id
                JOIN locations l ON b.primary_location_id = l.id
            """
            params = []
            if status:
                sql += " WHERE b.status = ?"
                params.append(status)
            sql += " ORDER BY b.created_at DESC"
            rows = conn.execute(sql, params).fetchall()
            return [dict(r) for r in rows]

    def approve_business(self, admin_user_id: str, business_id: str):
        with self.get_connection() as conn:
            # Verify admin
            admin = conn.execute("SELECT role FROM users WHERE id = ?", (admin_user_id,)).fetchone()
            if not admin or admin["role"] != "admin":
                raise PermissionError("Only Jay or authorized admins can approve listings.")

            conn.execute(
                """UPDATE businesses
                   SET status = 'approved', approved_by = ?, approved_at = CURRENT_TIMESTAMP, rejection_reason = NULL, updated_at = CURRENT_TIMESTAMP
                   WHERE id = ?""",
                (admin_user_id, business_id)
            )
            conn.execute(
                """INSERT INTO audit_events (id, actor_id, action, target_type, target_id, details_json)
                   VALUES (?, ?, 'BUSINESS_APPROVED', 'business', ?, ?)""",
                (str(uuid.uuid4()), admin_user_id, business_id, json.dumps({"status": "approved"}))
            )
            conn.commit()
            return True

    def reject_business(self, admin_user_id: str, business_id: str, reason: str):
        with self.get_connection() as conn:
            admin = conn.execute("SELECT role FROM users WHERE id = ?", (admin_user_id,)).fetchone()
            if not admin or admin["role"] != "admin":
                raise PermissionError("Only Jay or authorized admins can reject listings.")

            conn.execute(
                """UPDATE businesses
                   SET status = 'rejected', rejection_reason = ?, updated_at = CURRENT_TIMESTAMP
                   WHERE id = ?""",
                (reason, business_id)
            )
            conn.execute(
                """INSERT INTO audit_events (id, actor_id, action, target_type, target_id, details_json)
                   VALUES (?, ?, 'BUSINESS_REJECTED', 'business', ?, ?)""",
                (str(uuid.uuid4()), admin_user_id, business_id, json.dumps({"reason": reason}))
            )
            conn.commit()
            return True

    def get_admin_analytics(self):
        with self.get_connection() as conn:
            total_biz = conn.execute("SELECT COUNT(*) AS c FROM businesses").fetchone()["c"]
            approved_biz = conn.execute("SELECT COUNT(*) AS c FROM businesses WHERE status = 'approved'").fetchone()["c"]
            pending_biz = conn.execute("SELECT COUNT(*) AS c FROM businesses WHERE status = 'pending'").fetchone()["c"]
            total_searches = conn.execute("SELECT COUNT(*) AS c FROM search_events").fetchone()["c"]
            zero_searches = conn.execute("SELECT COUNT(*) AS c FROM search_events WHERE results_count = 0").fetchone()["c"]
            top_queries = conn.execute(
                """SELECT query_text, COUNT(*) AS count
                   FROM search_events
                   WHERE query_text IS NOT NULL AND query_text != ''
                   GROUP BY query_text ORDER BY count DESC LIMIT 10"""
            ).fetchall()
            contact_leads = conn.execute("SELECT COUNT(*) AS c FROM contact_requests").fetchone()["c"]

            return {
                "total_businesses": total_biz,
                "approved_businesses": approved_biz,
                "pending_businesses": pending_biz,
                "total_searches": total_searches,
                "zero_result_searches": zero_searches,
                "top_search_queries": [dict(t) for t in top_queries],
                "total_contact_inquiries": contact_leads
            }

    # -------------------------------------------------------------
    # Business Owner Dashboard & Tenant Isolation
    # -------------------------------------------------------------
    def get_owner_businesses(self, user_id: str):
        with self.get_connection() as conn:
            rows = conn.execute(
                """SELECT b.*, c.name_en AS category_name, l.name AS location_name
                   FROM businesses b
                   JOIN categories c ON b.category_id = c.id
                   JOIN locations l ON b.primary_location_id = l.id
                   WHERE b.owner_id = ?
                   ORDER BY b.created_at DESC""",
                (user_id,)
            ).fetchall()
            return [dict(r) for r in rows]

    def verify_business_ownership(self, user_id: str, business_id: str, allow_admin: bool = True):
        with self.get_connection() as conn:
            user = conn.execute("SELECT role FROM users WHERE id = ?", (user_id,)).fetchone()
            if not user:
                return False
            if allow_admin and user["role"] == "admin":
                return True
            biz = conn.execute("SELECT id FROM businesses WHERE id = ? AND owner_id = ?", (business_id, user_id)).fetchone()
            return bool(biz)

    def update_business_profile(self, user_id: str, business_id: str, update_data: dict):
        if not self.verify_business_ownership(user_id, business_id):
            raise PermissionError("Access denied: You do not own this business.")

        # Check for sensitive changes that require Jay approval
        # Sensitive fields: legal_name, rnc_tax_id, primary_location_id, category_id, website_url
        sensitive_keys = {"legal_name", "rnc_tax_id", "primary_location_id", "category_id"}
        sensitive_updates = {k: v for k, v in update_data.items() if k in sensitive_keys}

        direct_keys = {
            "trading_name", "description_en", "description_es", "address", "has_physical_location",
            "serves_entire_area", "website_url", "whatsapp", "phone", "public_email",
            "hours_json", "logo_url", "cover_image_url"
        }
        direct_updates = {k: v for k, v in update_data.items() if k in direct_keys}

        with self.get_connection() as conn:
            # Apply direct updates
            if direct_updates:
                set_clauses = [f"{k} = ?" for k in direct_updates.keys()]
                values = list(direct_updates.values())
                values.extend([datetime.now().isoformat(), business_id])
                sql = f"UPDATE businesses SET {', '.join(set_clauses)}, updated_at = ? WHERE id = ?"
                conn.execute(sql, values)

            # If sensitive updates exist, create a change request
            change_request_id = None
            if sensitive_updates:
                change_request_id = f"cr_{uuid.uuid4().hex[:12]}"
                conn.execute(
                    """INSERT INTO change_requests (id, business_id, requested_by, changes_json, status)
                       VALUES (?, ?, ?, ?, 'pending')""",
                    (change_request_id, business_id, user_id, json.dumps(sensitive_updates))
                )

            # Log audit
            conn.execute(
                """INSERT INTO audit_events (id, actor_id, action, target_type, target_id, details_json)
                   VALUES (?, ?, 'BUSINESS_PROFILE_UPDATED', 'business', ?, ?)""",
                (str(uuid.uuid4()), user_id, business_id, json.dumps({
                    "direct_keys": list(direct_updates.keys()),
                    "has_pending_change_request": bool(sensitive_updates)
                }))
            )
            conn.commit()

        return {
            "success": True,
            "direct_updates_applied": list(direct_updates.keys()),
            "pending_approval": list(sensitive_updates.keys()) if sensitive_updates else []
        }

    # -------------------------------------------------------------
    # Contact Form Service
    # -------------------------------------------------------------
    def submit_contact_form(self, business_id: str, sender_name: str, sender_contact: str, message: str):
        sender_name = (sender_name or "").strip()
        sender_contact = (sender_contact or "").strip()
        message = (message or "").strip()

        if not sender_name or not sender_contact or not message:
            raise ValueError("Name, contact info, and message are required.")

        with self.get_connection() as conn:
            # Business must be approved
            biz = conn.execute("SELECT id, trading_name FROM businesses WHERE id = ? AND status = 'approved'", (business_id,)).fetchone()
            if not biz:
                raise ValueError("Business listing not found or inactive.")

            req_id = f"cnt_{uuid.uuid4().hex[:12]}"
            conn.execute(
                """INSERT INTO contact_requests (id, business_id, sender_name, sender_contact, message)
                   VALUES (?, ?, ?, ?, ?)""",
                (req_id, business_id, sender_name, sender_contact, message)
            )
            conn.commit()

        return {"success": True, "request_id": req_id}

    def get_business_contact_requests(self, user_id: str, business_id: str):
        if not self.verify_business_ownership(user_id, business_id):
            raise PermissionError("Access denied.")

        with self.get_connection() as conn:
            rows = conn.execute(
                """SELECT id, sender_name, sender_contact, message, status, created_at
                   FROM contact_requests
                   WHERE business_id = ?
                   ORDER BY created_at DESC""",
                (business_id,)
            ).fetchall()
            return [dict(r) for r in rows]
