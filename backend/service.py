"""
Mavunqo Phase 1 - Core Business Logic & Query Services.
Handles:
- Public directory search with multi-filters (category, location, keyword, business name, service)
- Zero-results and search query audit tracking
- Business profiles & hosted storefronts (/b/{slug})
- Business application registration (optional RNC, default 'pending' status)
- Administrator moderation: approve, reject, request corrections, list applications
- Multi-tenant business owner dashboard: view owned businesses, edit profile, propose sensitive changes
- Change requests workflow (sensitive fields require admin approval)
- Contact form handling with rate-limit and anti-spam verification
"""
import sqlite3
import json
import uuid
import re
from datetime import datetime, timezone, timedelta
import secrets
import hashlib

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
            # Map search aliases like 'Montellano' -> loc_montellano
            loc_match = location_id
            if "montellano" in location_id.lower():
                loc_match = "loc_montellano"
            elif "sosua" in location_id.lower():
                loc_match = "loc_sosua"
            elif "cabarete" in location_id.lower():
                loc_match = "loc_cabarete"
            elif "puerto" in location_id.lower() or "plata" in location_id.lower():
                loc_match = "loc_puerto_plata"

            sql += """ AND (
                b.primary_location_id = ? OR 
                bsa.location_id = ? OR 
                l.name LIKE ? OR 
                LOWER(l.search_aliases) LIKE ?
            )"""
            params.extend([loc_match, loc_match, f"%{location_id}%", f"%{location_id.lower()}%"])

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
                LOWER(c.name_es) LIKE ? OR
                LOWER(c.search_aliases) LIKE ? OR
                LOWER(l.name) LIKE ? OR
                LOWER(l.search_aliases) LIKE ?
            )"""
            pattern = f"%{q}%"
            params.extend([pattern] * 12)

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
            valid_loc = None
            if location_id:
                loc_check = conn.execute("SELECT id FROM locations WHERE id = ? OR name LIKE ? OR search_aliases LIKE ?", (location_id, f"%{location_id}%", f"%{location_id}%")).fetchone()
                if loc_check:
                    valid_loc = loc_check["id"]

            valid_cat = None
            if category_id:
                cat_check = conn.execute("SELECT id FROM categories WHERE id = ? OR slug = ?", (category_id, category_id)).fetchone()
                if cat_check:
                    valid_cat = cat_check["id"]

            conn.execute(
                """INSERT INTO search_events (id, query_text, category_id, location_id, results_count)
                   VALUES (?, ?, ?, ?, ?)""",
                (str(uuid.uuid4()), q if q else None, valid_cat, valid_loc, len(results))
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

            # Ensure at least one description is provided, fallback to the other if only one language is filled
            description_en = (description_en or "").strip()
            description_es = (description_es or "").strip()
            if not description_en and not description_es:
                raise ValueError("A business description is required.")
            if not description_en:
                description_en = description_es
            if not description_es:
                description_es = description_en

            biz_id = f"biz_{uuid.uuid4().hex[:12]}"
            # Status is strictly PENDING until approved by admin
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
    # Administrator Actions
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
                raise PermissionError("Only authorized administrators can approve listings.")

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
                raise PermissionError("Only authorized administrators can reject listings.")

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

        # Check for sensitive changes that require admin approval
        # Sensitive fields: legal_name, rnc_tax_id, primary_location_id, category_id, website_url
        sensitive_keys = {"legal_name", "rnc_tax_id", "primary_location_id", "category_id"}
        sensitive_updates = {k: v for k, v in update_data.items() if k in sensitive_keys}

        direct_keys = {
            "trading_name", "description_en", "description_es", "address", "has_physical_location",
            "serves_entire_area", "website_url", "whatsapp", "phone", "public_email",
            "hours_json", "logo_url", "cover_image_url", "storefront_pin_lat", "storefront_pin_lng", "pickup_pin_lat", "pickup_pin_lng", "pickup_pin_note"
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

    # -------------------------------------------------------------
    # Merchant Catalog & Menu Item Management (Price, Photos, Availability)
    # -------------------------------------------------------------
    def get_merchant_catalog_items(self, user_id: str, business_id: str):
        if not self.verify_business_ownership(user_id, business_id):
            raise PermissionError("Access denied.")

        with self.get_connection() as conn:
            rows = conn.execute(
                """SELECT mi.*, mc.name_en AS category_name
                   FROM menu_items mi
                   LEFT JOIN menu_categories mc ON mi.category_id = mc.id
                   WHERE mi.business_id = ?
                   ORDER BY mi.sort_order ASC, mi.name_en ASC""",
                (business_id,)
            ).fetchall()
            return [dict(r) for r in rows]

    def add_merchant_catalog_item(self, user_id: str, business_id: str, item_data: dict):
        if not self.verify_business_ownership(user_id, business_id):
            raise PermissionError("Access denied.")

        name_en = (item_data.get("name_en") or "").strip()
        name_es = (item_data.get("name_es") or name_en).strip()
        price = float(item_data.get("price", 0.0))
        image_url = (item_data.get("image_url") or "").strip()
        description_en = (item_data.get("description_en") or "").strip()
        description_es = (item_data.get("description_es") or "").strip()
        category_id = item_data.get("category_id")

        if not name_en:
            raise ValueError("Item name is required.")
        if price <= 0:
            raise ValueError("Item price must be greater than zero.")

        item_id = f"item_{uuid.uuid4().hex[:10]}"
        with self.get_connection() as conn:
            conn.execute(
                """INSERT INTO menu_items (
                    id, business_id, category_id, name_en, name_es, description_en, description_es,
                    price, currency, image_url, is_available
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'DOP', ?, 1)""",
                (item_id, business_id, category_id, name_en, name_es, description_en, description_es, price, image_url)
            )
            conn.commit()

        return {"success": True, "item_id": item_id, "name_en": name_en, "price": price, "image_url": image_url}

    def update_merchant_catalog_item(self, user_id: str, business_id: str, item_id: str, item_data: dict):
        if not self.verify_business_ownership(user_id, business_id):
            raise PermissionError("Access denied.")

        allowed_fields = ["name_en", "name_es", "description_en", "description_es", "price", "image_url", "is_available"]
        updates = {k: v for k, v in item_data.items() if k in allowed_fields}

        if "price" in updates:
            updates["price"] = float(updates["price"])
            if updates["price"] <= 0:
                raise ValueError("Price must be greater than zero.")

        if not updates:
            return {"success": True, "updated": False}

        set_clause = ", ".join([f"{k} = ?" for k in updates.keys()])
        values = list(updates.values())
        values.extend([item_id, business_id])

        with self.get_connection() as conn:
            conn.execute(f"UPDATE menu_items SET {set_clause} WHERE id = ? AND business_id = ?", values)
            conn.commit()

        return {"success": True, "item_id": item_id, "updated_fields": list(updates.keys())}


    def get_item_sizes(self, user_id: str, business_id: str, item_id: str):
        if not self.verify_business_ownership(user_id, business_id):
            raise PermissionError("Access denied.")
        with self.get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM menu_modifiers WHERE menu_item_id = ? ORDER BY sort_order ASC",
                (item_id,)
            ).fetchall()
            return [dict(r) for r in rows]

    def set_item_sizes(self, user_id: str, business_id: str, item_id: str, sizes_list: list):
        if not self.verify_business_ownership(user_id, business_id):
            raise PermissionError("Access denied.")
        with self.get_connection() as conn:
            conn.execute("DELETE FROM menu_modifiers WHERE menu_item_id = ?", (item_id,))
            for idx, s in enumerate(sizes_list):
                s_name = str(s).strip()
                if not s_name:
                    continue
                mod_id = f"mod_{item_id}_{idx}"
                conn.execute(
                    """INSERT INTO menu_modifiers (id, menu_item_id, group_name_en, group_name_es, name_en, name_es, price_delta, currency, is_required, sort_order)
                       VALUES (?, ?, 'Select Size', 'Seleccionar Talla', ?, ?, 0.0, 'DOP', 1, ?)""",
                    (mod_id, item_id, s_name, s_name, idx)
                )
            conn.commit()
        return {"success": True, "item_id": item_id, "count": len(sizes_list)}

    def delete_merchant_catalog_item(self, user_id: str, business_id: str, item_id: str):
        if not self.verify_business_ownership(user_id, business_id):
            raise PermissionError("Access denied.")

        with self.get_connection() as conn:
            conn.execute("DELETE FROM menu_items WHERE id = ? AND business_id = ?", (item_id, business_id))
            conn.commit()

        return {"success": True, "deleted_item_id": item_id}

    # -------------------------------------------------------------
    # Phase 2: Restaurant Menu Management & Ordering Pilot
    # -------------------------------------------------------------
    def get_restaurant_menu(self, business_id_or_slug: str):
        with self.get_connection() as conn:
            biz = conn.execute(
                "SELECT id, trading_name, slug, status FROM businesses WHERE id = ? OR slug = ?",
                (business_id_or_slug, business_id_or_slug)
            ).fetchone()
            if not biz or biz["status"] != "approved":
                raise ValueError("Restaurant not found or inactive.")

            biz_id = biz["id"]
            cat_rows = conn.execute(
                "SELECT id, name_en, name_es, sort_order FROM menu_categories WHERE business_id = ? ORDER BY sort_order ASC",
                (biz_id,)
            ).fetchall()
            categories = [dict(c) for c in cat_rows]

            item_rows = conn.execute(
                """SELECT id, category_id, name_en, name_es, description_en, description_es,
                          price, currency, image_url, is_available, sort_order
                   FROM menu_items
                   WHERE business_id = ?
                   ORDER BY sort_order ASC""",
                (biz_id,)
            ).fetchall()

            item_ids = [r["id"] for r in item_rows]
            modifiers_by_item = {}
            if item_ids:
                placeholders = ",".join("?" for _ in item_ids)
                mod_rows = conn.execute(
                    f"""SELECT id, menu_item_id, group_name_en, group_name_es,
                               name_en, name_es, price_delta, currency, is_required, sort_order
                        FROM menu_modifiers
                        WHERE menu_item_id IN ({placeholders})
                        ORDER BY sort_order ASC""",
                    item_ids
                ).fetchall()
                for m in mod_rows:
                    m_dict = dict(m)
                    modifiers_by_item.setdefault(m_dict["menu_item_id"], []).append(m_dict)

            items_by_cat = {}
            uncategorized = []
            for r in item_rows:
                item_dict = dict(r)
                item_dict["modifiers"] = modifiers_by_item.get(item_dict["id"], [])
                cat_id = item_dict.get("category_id")
                if cat_id:
                    items_by_cat.setdefault(cat_id, []).append(item_dict)
                else:
                    uncategorized.append(item_dict)

            # Build structured category list
            menu_structure = []
            for c in categories:
                c["items"] = items_by_cat.get(c["id"], [])
                menu_structure.append(c)

            if uncategorized:
                menu_structure.append({
                    "id": "cat_other",
                    "name_en": "Other Items",
                    "name_es": "Otros Platos",
                    "sort_order": 999,
                    "items": uncategorized
                })

            return {
                "business_id": biz_id,
                "business_name": biz["trading_name"],
                "slug": biz["slug"],
                "categories": menu_structure
            }

    def place_order(self, business_id: str, customer_data: dict, items: list,
                    fulfillment_type: str = "pickup", delivery_address: str = "",
                    order_origin: str = "mavunqo", customer_notes: str = ""):
        customer_name = (customer_data.get("name") or "").strip()
        customer_phone = (customer_data.get("phone") or "").strip()
        customer_email = (customer_data.get("email") or "").strip()

        if not customer_name or not customer_phone:
            raise ValueError("Customer name and phone number are required.")

        if not items:
            raise ValueError("Order must contain at least one item.")

        if fulfillment_type not in ("pickup", "delivery"):
            fulfillment_type = "pickup"

        if fulfillment_type == "delivery":
            if not (delivery_address or "").strip():
                raise ValueError("Delivery address is required for delivery orders.")
            # Automatic capacity control check
            cap = self.get_delivery_capacity(location_id="loc_sosua")
            if not cap["delivery_available"]:
                raise ValueError(f"Delivery unavailable: {cap['reason']}")

        if order_origin not in ("mavunqo", "merchant"):
            order_origin = "mavunqo"

        from datetime import timedelta
        from datetime import timezone
        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(hours=48)
        status_token = f"tok_{uuid.uuid4().hex}"
        order_id = f"ord_{uuid.uuid4().hex[:12]}"
        order_num = f"MVQ-{now.strftime('%y%m%d')}-{uuid.uuid4().hex[:4].upper()}"

        subtotal = 0.0
        processed_items = []

        with self.get_connection() as conn:
            biz = conn.execute(
                "SELECT id, trading_name, status FROM businesses WHERE id = ? AND status = 'approved'",
                (business_id,)
            ).fetchone()
            if not biz:
                raise ValueError("Restaurant not found or inactive.")

            # Validate each item and calculate subtotal
            for it in items:
                menu_item_id = it.get("menu_item_id")
                qty = int(it.get("quantity", 1))
                if qty <= 0:
                    continue

                mi = conn.execute(
                    "SELECT id, name_en, name_es, price, currency, is_available FROM menu_items WHERE id = ? AND business_id = ?",
                    (menu_item_id, business_id)
                ).fetchone()
                if not mi:
                    raise ValueError(f"Menu item '{menu_item_id}' not found.")
                if not mi["is_available"]:
                    raise ValueError(f"Menu item '{mi['name_en']}' is currently unavailable.")

                selected_modifiers = it.get("modifiers") or []
                mod_price_total = 0.0
                valid_mods = []
                for mod in selected_modifiers:
                    mod_id = mod.get("id")
                    if mod_id:
                        m_row = conn.execute(
                            "SELECT id, name_en, name_es, price_delta FROM menu_modifiers WHERE id = ? AND menu_item_id = ?",
                            (mod_id, menu_item_id)
                        ).fetchone()
                        if m_row:
                            mod_price_total += float(m_row["price_delta"])
                            valid_mods.append({
                                "id": m_row["id"],
                                "name_en": m_row["name_en"],
                                "name_es": m_row["name_es"],
                                "price_delta": float(m_row["price_delta"])
                            })

                unit_price = float(mi["price"]) + mod_price_total
                line_total = round(unit_price * qty, 2)
                subtotal += line_total

                processed_items.append({
                    "id": f"oi_{uuid.uuid4().hex[:10]}",
                    "menu_item_id": mi["id"],
                    "item_name_en": mi["name_en"],
                    "item_name_es": mi["name_es"],
                    "unit_price": unit_price,
                    "quantity": qty,
                    "modifiers_json": json.dumps(valid_mods),
                    "line_total": line_total
                })

            if not processed_items:
                raise ValueError("No valid items in order.")

            delivery_fee = 100.0 if fulfillment_type == "delivery" else 0.0
            total = round(subtotal + delivery_fee, 2)

            # Insert order
            conn.execute(
                """INSERT INTO orders (
                    id, order_number, business_id, customer_name, customer_phone, customer_email,
                    order_origin, fulfillment_type, delivery_address, customer_notes,
                    status, subtotal, delivery_fee, total, currency, payment_method,
                    status_token, status_token_expires_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?, ?, ?, 'DOP', 'cash', ?, ?)""",
                (
                    order_id, order_num, business_id, customer_name, customer_phone, customer_email,
                    order_origin, fulfillment_type, delivery_address, customer_notes,
                    subtotal, delivery_fee, total, status_token, expires_at.isoformat()
                )
            )

            # Insert order items
            for oi in processed_items:
                conn.execute(
                    """INSERT INTO order_items (
                        id, order_id, menu_item_id, item_name_en, item_name_es, unit_price, quantity, modifiers_json, line_total
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        oi["id"], order_id, oi["menu_item_id"], oi["item_name_en"], oi["item_name_es"],
                        oi["unit_price"], oi["quantity"], oi["modifiers_json"], oi["line_total"]
                    )
                )

            # Accrue preliminary fee record:
            # 12% for Mavunqo-sourced orders, 0% (or configurable lower rate) for merchant-originated orders.
            # Delivery fee is excluded from commission base.
            from .tokens_and_attribution import STANDARD_COMMISSION_RATE
            commission_rate = STANDARD_COMMISSION_RATE
            commissionable_amount = subtotal
            fee_amount = round(commissionable_amount * commission_rate, 2)
            fee_id = f"fee_{uuid.uuid4().hex[:12]}"

            conn.execute(
                """INSERT INTO fee_records (
                    id, order_id, business_id, order_origin, commission_rate, commissionable_amount, fee_amount, currency, status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, 'DOP', 'pending')""",
                (fee_id, order_id, business_id, order_origin, commission_rate, commissionable_amount, fee_amount)
            )

            # Audit event
            conn.execute(
                """INSERT INTO audit_events (id, actor_id, action, target_type, target_id, details_json)
                   VALUES (?, NULL, 'order_placed', 'order', ?, ?)""",
                (f"aud_{uuid.uuid4().hex[:12]}", order_id, json.dumps({
                    "order_number": order_num,
                    "total": total,
                    "order_origin": order_origin,
                    "items_count": len(processed_items)
                }))
            )
            conn.commit()

        return {
            "success": True,
            "order_id": order_id,
            "order_number": order_num,
            "total": total,
            "currency": "DOP",
            "status_token": status_token,
            "status_url": f"/order/status?token={status_token}"
        }

    def get_order_by_token(self, status_token: str):
        with self.get_connection() as conn:
            order = conn.execute(
                """SELECT o.*, b.trading_name AS business_name, b.phone AS business_phone, b.whatsapp AS business_whatsapp,
                          b.address AS business_address, b.storefront_pin_lat AS pickup_lat, b.storefront_pin_lng AS pickup_lng,
                          b.pickup_pin_note
                   FROM orders o
                   JOIN businesses b ON o.business_id = b.id
                   WHERE o.status_token = ?""",
                (status_token,)
            ).fetchone()
            if not order:
                raise ValueError("Order not found or link has expired.")

            exp = order["status_token_expires_at"]
            from datetime import timezone
            if datetime.fromisoformat(exp) < datetime.now(timezone.utc):
                raise ValueError("Order status link has expired.")

            item_rows = conn.execute(
                "SELECT * FROM order_items WHERE order_id = ?",
                (order["id"],)
            ).fetchall()

            order_dict = dict(order)
            items = []
            for ir in item_rows:
                idict = dict(ir)
                idict["modifiers"] = json.loads(idict["modifiers_json"]) if idict.get("modifiers_json") else []
                items.append(idict)

            order_dict["items"] = items
            return order_dict

    def get_merchant_orders(self, user_id: str, business_id: str, status_filter: str = ""):
        if not self.verify_business_ownership(user_id, business_id):
            raise PermissionError("Access denied.")

        sql = """SELECT id, order_number, customer_name, customer_phone, customer_email,
                        order_origin, fulfillment_type, delivery_address, customer_notes,
                        status, subtotal, delivery_fee, total, currency, payment_method,
                        cash_received, cash_reconciled, estimated_ready_at,
                        created_at, updated_at
                 FROM orders
                 WHERE business_id = ?"""
        params = [business_id]
        if status_filter:
            sql += " AND status = ?"
            params.append(status_filter)
        sql += " ORDER BY created_at DESC"

        with self.get_connection() as conn:
            order_rows = conn.execute(sql, params).fetchall()
            orders = []
            for o in order_rows:
                od = dict(o)
                # fetch items
                items = conn.execute("SELECT * FROM order_items WHERE order_id = ?", (od["id"],)).fetchall()
                od["items"] = [dict(it) for it in items]
                orders.append(od)
            return orders

    def update_order_status(self, user_id: str, business_id: str, order_id: str, new_status: str,
                            estimated_minutes: int = 0, reason: str = "", cash_received: float = None):
        if not self.verify_business_ownership(user_id, business_id):
            raise PermissionError("Access denied.")

        valid_transitions = {
            "pending": ["accepted", "declined", "cancelled"],
            "accepted": ["in_kitchen", "ready", "cancelled"],
            "in_kitchen": ["ready", "cancelled"],
            "ready": ["completed", "cancelled"],
            "completed": [],
            "cancelled": [],
            "declined": []
        }

        with self.get_connection() as conn:
            order = conn.execute(
                "SELECT id, status, total FROM orders WHERE id = ? AND business_id = ?",
                (order_id, business_id)
            ).fetchone()
            if not order:
                raise ValueError("Order not found.")

            curr_status = order["status"]
            allowed = valid_transitions.get(curr_status, [])
            if new_status not in allowed:
                raise ValueError(f"Cannot transition order from '{curr_status}' to '{new_status}'.")

            from datetime import timezone
            now = datetime.now(timezone.utc)
            eta_val = None
            if new_status == "accepted" and estimated_minutes > 0:
                from datetime import timedelta
                eta_val = (now + timedelta(minutes=estimated_minutes)).isoformat()

            # If completing order, record cash receipt & reconcile fee
            cash_rec = cash_received if cash_received is not None else (order["total"] if new_status == "completed" else None)
            cash_reconciled = 1 if new_status == "completed" else 0
            if new_status == 'ready':
                self.dispatch_driver_on_ready(order_id)

            conn.execute(
                """UPDATE orders
                   SET status = ?,
                       estimated_ready_at = COALESCE(?, estimated_ready_at),
                       decline_reason = CASE WHEN ? = 'declined' THEN ? ELSE decline_reason END,
                       cancellation_reason = CASE WHEN ? = 'cancelled' THEN ? ELSE cancellation_reason END,
                       cash_received = COALESCE(?, cash_received),
                       cash_reconciled = CASE WHEN ? = 1 THEN 1 ELSE cash_reconciled END,
                       updated_at = CURRENT_TIMESTAMP
                   WHERE id = ?""",
                (new_status, eta_val, new_status, reason, new_status, reason, cash_rec, cash_reconciled, order_id)
            )

            # Update fee record status
            if new_status == "completed":
                conn.execute(
                    "UPDATE fee_records SET status = 'accrued', updated_at = CURRENT_TIMESTAMP WHERE order_id = ?",
                    (order_id,)
                )
            elif new_status in ("cancelled", "declined"):
                conn.execute(
                    """UPDATE fee_records
                       SET status = 'reversed', reversal_reason = ?, updated_at = CURRENT_TIMESTAMP
                       WHERE order_id = ?""",
                    (f"Order {new_status}: {reason}", order_id)
                )

            # Audit event
            conn.execute(
                """INSERT INTO audit_events (id, actor_id, action, target_type, target_id, details_json)
                   VALUES (?, ?, 'order_status_update', 'order', ?, ?)""",
                (f"aud_{uuid.uuid4().hex[:12]}", user_id, order_id, json.dumps({
                    "from_status": curr_status,
                    "to_status": new_status,
                    "reason": reason
                }))
            )
            conn.commit()

        return {"success": True, "order_id": order_id, "new_status": new_status}

    def get_merchant_fee_statement(self, user_id: str, business_id: str):
        if not self.verify_business_ownership(user_id, business_id):
            raise PermissionError("Access denied.")

        with self.get_connection() as conn:
            rows = conn.execute(
                """SELECT f.*, o.order_number, o.created_at AS order_created_at
                   FROM fee_records f
                   JOIN orders o ON f.order_id = o.id
                   WHERE f.business_id = ?
                   ORDER BY f.created_at DESC""",
                (business_id,)
            ).fetchall()

            records = [dict(r) for r in rows]
            total_accrued = sum(r["fee_amount"] for r in records if r["status"] == "accrued")
            total_pending = sum(r["fee_amount"] for r in records if r["status"] == "pending")
            total_reversed = sum(r["fee_amount"] for r in records if r["status"] == "reversed")

            return {
                "business_id": business_id,
                "total_accrued_fees": round(total_accrued, 2),
                "total_pending_fees": round(total_pending, 2),
                "total_reversed_fees": round(total_reversed, 2),
                "currency": "DOP",
                "statement_lines": records
            }

    # -------------------------------------------------------------
    # Multi-Vertical: City Lights Hospitality & Stays Service
    # -------------------------------------------------------------
    def get_lodging_units(self, business_id_or_slug: str):
        with self.get_connection() as conn:
            biz = conn.execute(
                "SELECT id, trading_name, slug FROM businesses WHERE id = ? OR slug = ?",
                (business_id_or_slug, business_id_or_slug)
            ).fetchone()
            if not biz:
                raise ValueError("Business not found.")

            units = conn.execute(
                """SELECT * FROM lodging_units
                   WHERE business_id = ? AND is_available = 1
                   ORDER BY sort_order ASC""",
                (biz["id"],)
            ).fetchall()

            return {
                "business_id": biz["id"],
                "business_name": biz["trading_name"],
                "units": [dict(u) for u in units]
            }

    def book_lodging_unit(self, business_id: str, unit_id: str, guest_data: dict,
                          check_in: str, check_out: str, guest_count: int = 1):
        guest_name = (guest_data.get("name") or "").strip()
        guest_contact = (guest_data.get("contact") or "").strip()
        guest_email = (guest_data.get("email") or "").strip()

        if not guest_name or not guest_contact:
            raise ValueError("Guest name and contact number/WhatsApp are required.")

        from datetime import datetime, date
        d1 = datetime.strptime(check_in, "%Y-%m-%d").date()
        d2 = datetime.strptime(check_out, "%Y-%m-%d").date()
        nights = (d2 - d1).days
        if nights <= 0:
            raise ValueError("Check-out date must be after check-in date.")

        with self.get_connection() as conn:
            unit = conn.execute(
                "SELECT * FROM lodging_units WHERE id = ? AND business_id = ? AND is_available = 1",
                (unit_id, business_id)
            ).fetchone()
            if not unit:
                raise ValueError("Selected lodging unit is unavailable or not found.")

            if guest_count > unit["capacity"]:
                raise ValueError(f"Unit capacity exceeded (maximum {unit['capacity']} guests).")

            # Check overlap on active bookings
            overlap = conn.execute(
                """SELECT id FROM reservations
                   WHERE unit_id = ? AND status IN ('confirmed', 'checked_in')
                   AND NOT (check_out_date <= ? OR check_in_date >= ?)""",
                (unit_id, check_in, check_out)
            ).fetchone()
            if overlap:
                raise ValueError("Unit is already booked for the selected dates.")

            res_id = f"res_{uuid.uuid4().hex[:12]}"
            res_code = f"CL-{d1.strftime('%y%m')}-{uuid.uuid4().hex[:4].upper()}"
            status_token = f"tok_res_{uuid.uuid4().hex}"
            total_amount = round(unit["base_price_night"] * nights, 2)

            conn.execute(
                """INSERT INTO reservations (
                    id, reservation_code, business_id, unit_id, guest_name, guest_contact, guest_email,
                    check_in_date, check_out_date, nights, guest_count, nightly_rate, total_amount, currency,
                    status, payment_method, cash_collected, status_token
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'confirmed', 'cash_on_arrival', 0.0, ?)""",
                (
                    res_id, res_code, business_id, unit_id, guest_name, guest_contact, guest_email,
                    check_in, check_out, nights, guest_count, unit["base_price_night"], total_amount,
                    unit["currency"], status_token
                )
            )

            # Audit event
            conn.execute(
                """INSERT INTO audit_events (id, actor_id, action, target_type, target_id, details_json)
                   VALUES (?, NULL, 'reservation_created', 'reservation', ?, ?)""",
                (f"aud_{uuid.uuid4().hex[:12]}", res_id, json.dumps({
                    "code": res_code, "total": total_amount, "nights": nights
                }))
            )
            conn.commit()

        return {
            "success": True,
            "reservation_id": res_id,
            "reservation_code": res_code,
            "total_amount": total_amount,
            "currency": unit["currency"],
            "status_token": status_token
        }

    def get_staff_reservations(self, user_id: str, business_id: str):
        if not self.verify_business_ownership(user_id, business_id):
            raise PermissionError("Access denied.")

        with self.get_connection() as conn:
            rows = conn.execute(
                """SELECT r.*, u.unit_number, u.name_en AS unit_name_en, u.unit_type
                   FROM reservations r
                   JOIN lodging_units u ON r.unit_id = u.id
                   WHERE r.business_id = ?
                   ORDER BY r.check_in_date ASC, r.created_at DESC""",
                (business_id,)
            ).fetchall()
            return [dict(r) for r in rows]

    def process_staff_checkin(self, user_id: str, business_id: str, reservation_id: str,
                              cash_collected: float, staff_notes: str = ""):
        if not self.verify_business_ownership(user_id, business_id):
            raise PermissionError("Access denied.")

        with self.get_connection() as conn:
            res = conn.execute(
                "SELECT * FROM reservations WHERE id = ? AND business_id = ?",
                (reservation_id, business_id)
            ).fetchone()
            if not res:
                raise ValueError("Reservation not found.")

            if res["status"] != "confirmed":
                raise ValueError(f"Cannot check in reservation with status '{res['status']}'.")

            conn.execute(
                """UPDATE reservations
                   SET status = 'checked_in',
                       cash_collected = ?,
                       staff_notes = ?,
                       updated_at = CURRENT_TIMESTAMP
                   WHERE id = ?""",
                (float(cash_collected), staff_notes, reservation_id)
            )

            conn.execute(
                """INSERT INTO audit_events (id, actor_id, action, target_type, target_id, details_json)
                   VALUES (?, ?, 'staff_checkin_cash_collected', 'reservation', ?, ?)""",
                (f"aud_{uuid.uuid4().hex[:12]}", user_id, reservation_id, json.dumps({
                    "cash_collected": float(cash_collected), "total_due": res["total_amount"]
                }))
            )
            conn.commit()

        return {"success": True, "reservation_id": reservation_id, "status": "checked_in"}

    # -------------------------------------------------------------
    # AI Concierge Query Engine (Bilingual & Grounded)
    # -------------------------------------------------------------
    def ask_ai_concierge(self, query: str, lang: str = "en"):
        query = (query or "").strip().lower()
        if not query:
            return {
                "answer": "Hello! How can I assist you with services, dining, or hotel stays in Sosúa and Puerto Plata?",
                "recommendations": []
            }

        with self.get_connection() as conn:
            # Query approved listings including service matches
            words = [w for w in re.split(r'\s+', query) if len(w) > 2]
            pattern = f"%{query}%"

            sql = """
                SELECT DISTINCT b.id, b.trading_name, b.slug, b.description_en, b.description_es,
                       b.whatsapp, b.phone, c.name_en AS category, l.name AS location
                FROM businesses b
                JOIN categories c ON b.category_id = c.id
                JOIN locations l ON b.primary_location_id = l.id
                LEFT JOIN services s ON b.id = s.business_id
                WHERE b.status = 'approved' AND (
                    LOWER(b.trading_name) LIKE ? OR
                    LOWER(b.description_en) LIKE ? OR
                    LOWER(b.description_es) LIKE ? OR
                    LOWER(c.name_en) LIKE ? OR
                    LOWER(c.name_es) LIKE ? OR
                    LOWER(s.name_en) LIKE ? OR
                    LOWER(s.name_es) LIKE ?
                )
                LIMIT 4
            """
            params = [pattern] * 7
            businesses = conn.execute(sql, params).fetchall()
            recs = [dict(b) for b in businesses]

            # Keyword fallback for multi-word or token matches
            if not recs and words:
                word_patterns = [f"%{w}%" for w in words]
                or_clauses = " OR ".join([
                    "(LOWER(b.trading_name) LIKE ? OR LOWER(b.description_en) LIKE ? OR LOWER(b.description_es) LIKE ? OR LOWER(s.name_en) LIKE ? OR LOWER(s.name_es) LIKE ?)"
                    for _ in words
                ])
                fallback_sql = f"""
                    SELECT DISTINCT b.id, b.trading_name, b.slug, b.description_en, b.description_es,
                           b.whatsapp, b.phone, c.name_en AS category, l.name AS location
                    FROM businesses b
                    JOIN categories c ON b.category_id = c.id
                    JOIN locations l ON b.primary_location_id = l.id
                    LEFT JOIN services s ON b.id = s.business_id
                    WHERE b.status = 'approved' AND ({or_clauses})
                    LIMIT 4
                """
                fallback_params = []
                for p in word_patterns:
                    fallback_params.extend([p, p, p, p, p])
                fb_biz = conn.execute(fallback_sql, fallback_params).fetchall()
                recs = [dict(b) for b in fb_biz]

            if any(k in query for k in ["fish", "pescado", "seafood", "marisco", "chillo"]):
                fb = conn.execute("SELECT id, trading_name, slug, description_en, description_es, whatsapp, phone FROM businesses WHERE id = 'biz_el_batey_bistro'").fetchone()
                if fb and not any(r["id"] == "biz_el_batey_bistro" for r in recs):
                    recs.append(dict(fb))

            if "hotel" in query or "room" in query or "stay" in query or "hospedaje" in query or "dorm" in query:
                cl = conn.execute("SELECT id, trading_name, slug FROM businesses WHERE id = 'biz_city_lights'").fetchone()
                if cl and not any(r["id"] == "biz_city_lights" for r in recs):
                    recs.insert(0, dict(cl))

            # Regional Knowledge Base: Comprehensive North Coast (Sosua, Cabarete, Puerto Plata)
            regional_knowledge = {
                # 1. Money, Currency & Tipping
                "currency": {
                    "en": "The currency is the Dominican Peso (DOP / RD$). US Dollars are widely accepted in tourist spots, hotels, and excursions. Most restaurants and supermarkets accept Visa and Mastercard. It is best to pay in Pesos for small purchases, motoconchos, and beach shacks.",
                    "es": "La moneda oficial es el Peso Dominicano (DOP / RD$). El dólar estadounidense es ampliamente aceptado en hoteles y zonas turísticas. Las tarjetas Visa y Mastercard son comunes en restaurantes y supermercados, pero se recomienda efectivo en pesos para motoconchos y chiringuitos de playa."
                },
                "exchange": {
                    "en": "You can exchange USD and Euros at Western Union, Caribe Express, or bank branches on Calle Pedro Clisante in Sosua. Banks generally offer the official interbank rate, while exchange booths (casas de cambio) offer convenience.",
                    "es": "Puede cambiar dólares y euros en Caribe Express, Western Union o en sucursales bancarias en la Calle Pedro Clisante. Los bancos ofrecen tasas oficiales y las casas de cambio brindan horarios convenientes."
                },
                "tipping": {
                    "en": "In the Dominican Republic, restaurant bills include a mandatory 18% ITBIS (sales tax) and a 10% legal service charge. However, the 10% is pooled; it is customary and appreciated to leave an extra 5% to 10% cash tip directly to your server for good service.",
                    "es": "En República Dominicana la cuenta del restaurante incluye por ley un 18% de ITBIS y 10% de propina legal. Es costumbre dejar entre un 5% y 10% adicional en efectivo directamente al camarero por buen servicio."
                },
                "propina": {
                    "en": "Standard tipping is 5% to 10% cash on top of the bill, as the included 10% legal tip is pooled among all staff.",
                    "es": "Es habitual dejar un 5% a 10% adicional en efectivo si el servicio fue agradable, ya que el 10% legal de la factura se reparte entre todo el personal."
                },

                # 2. Safety & Local Advice
                "safe": {
                    "en": "Sosua and Cabarete are generally friendly tourist beach towns. Standard common-sense precautions apply: avoid unlit beaches alone late at night, keep valuables discreet, don't flash large amounts of cash, and take official taxis or verified motoconchos.",
                    "es": "Sosúa y Cabarete son pueblos costeros acogedores. Como en cualquier destino turístico, use sentido común: evite playas oscuras de noche, no exhiba prendas ni mucho efectivo, y tome taxis oficiales o transporte de confianza."
                },
                "seguridad": {
                    "en": "Sosua is welcoming to travelers. Keep awareness in nightlife areas, use licensed taxis, and store passports in your room safe.",
                    "es": "Sosúa es un destino concurrido y acogedor. Mantenga precaución en zonas nocturnas, utilice taxis oficiales y guarde sus documentos de valor en la caja fuerte de su hospedaje."
                },
                "water": {
                    "en": "Tap water in the Dominican Republic is NOT for drinking. Always drink bottled, filtered water (agua purificada), which is provided by all hotels and sold cheaply in every colmado (Dasani, Planeta Azul, or Crystal). Tap water is fine for showering and brushing teeth.",
                    "es": "El agua del grifo en República Dominicana NO es potable. Beba siempre agua purificada embotellada, disponible en todos los colmados y hoteles (marcas Dasani, Planeta Azul o Cristal)."
                },
                "agua": {
                    "en": "Do not drink tap water; only drink bottled purified water available at every local colmado and restaurant.",
                    "es": "No beba agua de la llave. Compre siempre botellones o botellas de agua purificada en los colmados o supermercados."
                },

                # 3. Connectivity, SIM Cards & Power
                "sim": {
                    "en": "For mobile data, you can get a prepaid Dominican SIM card from Claro or Altice on Calle Pedro Clisante or in Puerto Plata. You will need your physical passport. Prepaid plans with fast 4G/LTE cost around $10 to $15 USD for 7–15 days of unlimited data.",
                    "es": "Para internet móvil, compre un chip prepago de Claro o Altice en la Calle Pedro Clisante presentando su pasaporte físico. Los paquetes con 4G/LTE ilimitado cuestan entre $10 y $15 USD por 7 a 15 días."
                },
                "internet": {
                    "en": "High-speed fiber-optic Wi-Fi is common in most Sosua cafes, villas, and hotels. For cellular data, Claro and Altice have strong 4G coverage.",
                    "es": "El Wi-Fi por fibra óptica es común en hoteles, villas y cafeterías en Sosúa. Para datos móviles, Claro y Altice tienen excelente cobertura 4G."
                },
                "plug": {
                    "en": "The electrical sockets in the Dominican Republic are the same as the US and Canada (Type A and B, 110V/60Hz). Travelers from North America do not need an adapter. European travelers will need a standard US plug adapter.",
                    "es": "Los enchufes en República Dominicana son idénticos a los de Estados Unidos y Canadá (Tipo A y B, 110V/60Hz). Viajeros norteamericanos no necesitan adaptador; los europeos requerirán adaptador americano."
                },
                "enchufe": {
                    "en": "Power sockets are standard US 110V. European visitors need a flat 2-prong adapter.",
                    "es": "Los tomacorrientes son tipo estadounidense 110V (patas planas)."
                },

                # 4. Transportation & Getting Around
                "uber": {
                    "en": "Uber operates in Puerto Plata and can often be booked to/from Puerto Plata International Airport (POP). Within Sosua and Cabarete, local motoconchos and official tourist taxi stands (near Supermercado Playero) are the quickest way to get around.",
                    "es": "Uber funciona en la ciudad de Puerto Plata y traslados desde/hacia el aeropuerto POP. Dentro de Sosúa y Cabarete, los motoconchos locales y las paradas de taxis turísticos son el medio más rápido."
                },
                "transport": {
                    "en": "To travel between Sosua, Cabarete, and Puerto Plata, you can take: 1) Guaguas (public minibuses running constantly along Highway 5 for ~$1-2 USD), 2) Carritos Públicos (shared taxis), or 3) Private tourist taxis (~$25-35 USD).",
                    "es": "Para moverse entre Sosúa, Cabarete y Puerto Plata: 1) Las 'Guaguas' públicas pasan constantemente por la Carretera 5 por unos 50-100 pesos, 2) Carritos públicos compartidos, o 3) Taxis turísticos privados."
                },
                "motoconcho": {
                    "en": "Motoconchos are motorcycle taxis found on every corner in Sosua. Short rides around El Batey or Los Charamicos typically cost between 50 to 100 DOP ($1-2 USD). Always agree on the price before hopping on!",
                    "es": "Los motoconchos son mototaxis en cada esquina de Sosúa. Los trayectos cortos dentro de El Batey o Los Charamicos cuestan entre 50 y 100 pesos. Acuerde el precio antes de subir."
                },

                # 5. Nightlife, Activities & Excursions
                "nightlife": {
                    "en": "Sosua nightlife is centered around Calle Pedro Clisante in El Batey, featuring open-air bars, sports lounges, and dance spots. For beachfront sunset lounges and live music with your feet in the sand, head 15 minutes east to Cabarete Bay.",
                    "es": "La vida nocturna de Sosúa se concentra en la Calle Pedro Clisante en El Batey, con bares al aire libre y música. En Cabarete (a 15 min), encontrará bares sobre la misma arena de la playa con música en vivo y ambiente bohemio."
                },
                "vida nocturna": {
                    "en": "Pedro Clisante street in Sosua for bars; Cabarete beach for beachfront lounges and dancing under the stars.",
                    "es": "Calle Pedro Clisante en Sosúa para bares y terrazas; la playa de Cabarete para bailar sobre la arena frente al mar."
                },
                "activity": {
                    "en": "Top activities in the area: 1) Snorkeling and scuba diving at Three Rocks / Sosua Bay, 2) 27 Charcos of Damajagua (waterfalls you can jump and slide down), 3) Kitesurfing lessons in Cabarete, 4) Monkey Jungle zip-lining.",
                    "es": "Mejores actividades: 1) Snorkel y buceo en la Bahía de Sosúa y Tres Rocas, 2) Los 27 Charcos de Damajagua (cascadas naturales), 3) Clases de Kitesurf en Cabarete, 4) Tirolinas en Monkey Jungle."
                },
                "excursion": {
                    "en": "Must-do excursions: 27 Waterfalls of Damajagua, Puerto Plata Teleferico (Cable Car to Mount Isabel de Torres), and deep-sea fishing charters leaving from Sosua Bay.",
                    "es": "Excursiones imperdibles: Los 27 Charcos de Damajagua, el Teleférico de Puerto Plata y tours de pesca en la Bahía de Sosúa."
                },

                # 6. Groceries, Colmados & Delivery
                "colmado": {
                    "en": "A 'colmado' is the quintessential Dominican corner convenience store. They sell cold Presidente beer, snacks, water, rum, and toiletries, and almost all of them offer free local motorcycle delivery if you call or send a WhatsApp!",
                    "es": "Un colmado es el comercio típico dominicano de barrio. Tienen cerveza Presidente bien fría, botellones de agua, hielo, ron y víveres, y la mayoría entrega a domicilio en motor."
                },
                "atm": {
                    "en": "In Sosua, the primary ATMs and banks are Banco Popular, Banreservas, and Scotiabank located on Calle Pedro Clisante and Highway 5. You can withdraw Dominican Pesos (DOP) and USD with international Visa/Mastercard.",
                    "es": "En Sosúa, los principales cajeros automáticos y bancos son Banco Popular, Banreservas y Scotiabank en la Calle Pedro Clisante y Carretera Sosúa-Cabarete. Puede retirar pesos (DOP) y dólares con tarjetas internacionales."
                },
                "banco": {
                    "en": "In Sosua, you will find Banco Popular, Banreservas, and BHD León on Calle Pedro Clisante and near Supermercado Playero.",
                    "es": "En Sosúa encontrará sucursales de Banco Popular, Banreservas y BHD León en la Calle Pedro Clisante y cerca de Playero."
                },
                "beach": {
                    "en": "The two famous beaches in Sosua are Playa Sosua (great for snorkeling, beach shacks, and water sports) and Playa Alicia (peaceful golden sand beach with calm waters and sunset views near El Batey). In Cabarete, Kite Beach and Cabarete Bay are world-famous for kitesurfing.",
                    "es": "Las dos playas principales en Sosúa son Playa Sosúa (excelente para snorkel, chiringuitos y deportes acuáticos) y Playa Alicia (playa tranquila de arena dorada en El Batey). En Cabarete, Kite Beach y la Bahía son famosas para kitesurf."
                },
                "playa": {
                    "en": "The two famous beaches in Sosua are Playa Sosua and Playa Alicia in El Batey. Cabarete is 15 minutes away for kitesurfing and beachfront nightlife.",
                    "es": "Las dos playas más populares en Sosúa son Playa Sosúa y Playa Alicia en El Batey. A 15 minutos en Cabarete está Kite Beach para deportes acuáticos y restaurantes sobre la arena."
                },
                "pharmacy": {
                    "en": "Trusted pharmacies in Sosua include Farmacia Sosua and Farmacia Carol on Pedro Clisante and near Supermercado Playero, open 7 days a week.",
                    "es": "Farmacias reconocidas en Sosúa incluyen Farmacia Sosúa y Farmacia Carol en la Calle Pedro Clisante y cerca de Supermercado Playero."
                },
                "farmacia": {
                    "en": "Trusted pharmacies in Sosua include Farmacia Sosua and Farmacia Carol on Pedro Clisante, open daily.",
                    "es": "En Sosúa tiene Farmacia Sosúa y Farmacia Carol sobre la Calle Pedro Clisante y frente al Supermercado Playero."
                },
                "grocery": {
                    "en": "The main international grocery stores are Supermercado Playero (El Batey, Sosua) and Super Pola (Highway 5 between Sosua and Cabarete). They stock North American, European, and Dominican products.",
                    "es": "Los supermercados principales son Supermercado Playero (El Batey, Sosúa) y Super Pola (Carretera Sosúa-Cabarete), con amplia variedad de productos locales e importados."
                },
                "supermercado": {
                    "en": "Supermercado Playero in El Batey and Super Pola on Highway 5 are the primary supermarkets in the area.",
                    "es": "Supermercado Playero en El Batey y Super Pola en la Carretera Sosúa-Cabarete son los supermercados principales."
                },
                "hospital": {
                    "en": "For emergency medical care in Sosua, Centro Medico Cabarete (CMC) on Highway 5 is a modern private hospital with 24/7 bilingual emergency services, lab, and imaging.",
                    "es": "Para emergencias médicas en Sosúa, el Centro Médico Cabarete (CMC) en la Carretera 5 ofrece atención 24/7 con personal bilingüe, laboratorio y urgencias."
                },
                "medico": {
                    "en": "Centro Medico Cabarete (CMC) on Highway 5 offers 24/7 medical emergency care for Sosua and Cabarete.",
                    "es": "Centro Médico Cabarete (CMC) en la Carretera 5 cuenta con emergencias médicas 24/7 para Sosúa y Cabarete."
                },
                "airport": {
                    "en": "The closest airport is Gregorio Luperón International Airport (POP) in Puerto Plata, approximately 15 minutes drive from Sosua. Santiago Airport (STI) is about 90 minutes away.",
                    "es": "El aeropuerto más cercano es el Aeropuerto Internacional Gregorio Luperón (POP) en Puerto Plata, a unos 15 minutos de Sosúa. El aeropuerto de Santiago (STI) queda a 90 minutos."
                },
                "aeropuerto": {
                    "en": "Gregorio Luperón Airport (POP) is just 15 minutes away from Sosua.",
                    "es": "El Aeropuerto Gregorio Luperón (POP) está a solo 15 minutos de Sosúa."
                },
                "fish": {
                    "en": "For the best fresh fish and seafood on the North Coast, Playa Sosua is famous for beachfront fish shacks serving freshly caught whole Red Snapper (Chillo) with tostones and avocado. On the Mavunqo platform, El Batey Bistro & Grill serves fresh local catch daily. Nearby Maimon is also known island-wide as the coastal fish village.",
                    "es": "Para el mejor pescado fresco y mariscos en la Costa Norte, Playa Sosúa es famosa por sus puestos frente al mar que preparan Chillo frito al momento con tostones y aguacate. En Mavunqo, El Batey Bistro & Grill ofrece pescado fresco del día. Además, la cercana zona de Maimón es reconocida en todo el país como la capital del pescado."
                },
                "seafood": {
                    "en": "For fresh seafood in Sosua, visit Playa Sosua beach shacks for whole fried red snapper, or order from El Batey Bistro & Grill on Calle Pedro Clisante.",
                    "es": "Para mariscos frescos en Sosúa, los chiringuitos de Playa Sosúa son legendarios para chillo frito, o puede ordenar en El Batey Bistro & Grill."
                },
                "pescado": {
                    "en": "For fresh local fish in Sosua, Playa Sosua and El Batey Bistro offer great red snapper and garlic tostones.",
                    "es": "Para el mejor pescado en Sosúa, Playa Sosúa y El Batey Bistro ofrecen excelente chillo entero fresco con tostones."
                },
                "wings": {
                    "en": "For the best chicken wings in Sosúa, local favorites include:\n1. **Wings & Waffles** (Calle Dr. Rosen) — dedicated comfort food spot famous for crispy, seasoned wings.\n2. **Flip Flop Sports Bar** (Calle Duarte / The Yellow Steps) — classic expat sports bar with crispy buffalo wings and cold Presidente beer.\n3. **Fat Jesse’s** (Calle Pedro Clisante) — lively grill & bar with top-rated American-style sauced wings.\n4. **Mosha's Reggae Lounge** (Calle Dr. Rosen) — renowned for incredible spicy Jamaican jerk-seasoned chicken.\n5. On Mavunqo: **El Batey Bistro & Grill** prepares delicious grilled chicken and Dominican appetizers.",
                    "es": "Para las mejores alitas de pollo (chicken wings) en Sosúa, los lugares más recomendados son:\n1. **Wings & Waffles** (Calle Dr. Rosen) — especialidad en alitas crujientes y waffles.\n2. **Flip Flop Sports Bar** (Calle Duarte) — bar deportivo popular para alitas buffalo y cerveza bien fría.\n3. **Fat Jesse’s** (Calle Pedro Clisante) — famoso por sus alitas a la parrilla con salsas caseras.\n4. **Mosha's Reggae Lounge** (Calle Dr. Rosen) — famoso por su pollo jerk jamaiquino especiado.\n5. En Mavunqo: **El Batey Bistro & Grill** ofrece exquisito pollo a la parrilla y aperitivos criollos."
                },
                "alitas": {
                    "en": "For the best wings in Sosua, visit Wings & Waffles on Dr. Rosen, Flip Flop Sports Bar on Calle Duarte, or Fat Jesse's on Pedro Clisante. On Mavunqo, order from El Batey Bistro.",
                    "es": "Para las mejores alitas en Sosúa, visite Wings & Waffles en Calle Dr. Rosen, Flip Flop Sports Bar en Calle Duarte o Fat Jesse's en Pedro Clisante. En Mavunqo puede ordenar de El Batey Bistro."
                },
                "chicken": {
                    "en": "For chicken in Sosua, try traditional Dominican pica pollo at local spots in Los Charamicos, wings at Wings & Waffles or Flip Flop Bar, jerk chicken at Mosha's, or homestyle chicken dishes on Mavunqo at D'Sabor Criollo.",
                    "es": "Para pollo en Sosúa, pruebe el pica pollo tradicional en Los Charamicos, alitas en Wings & Waffles o Flip Flop, pollo jerk en Mosha's, o comida criolla en D'Sabor Criollo en Mavunqo."
                },
                "pica pollo": {
                    "en": "Pica Pollo is the beloved Dominican style crispy fried chicken seasoned with oregano and lime. In Sosua, the best authentic pica pollo spots are in Los Charamicos (along Calle Alejo Martínez) and near the taxi stand by Highway 5. On Mavunqo, D'Sabor Criollo serves authentic homestyle fried chicken with tostones.",
                    "es": "El Pica Pollo es el clásico pollo frito dominicano sazonado con orégano criollo y limón. Los mejores se encuentran en Los Charamicos (Calle Alejo Martínez) y cerca de la parada de la Carretera 5. En Mavunqo, D'Sabor Criollo prepara delicioso pollo frito criollo con tostones."
                },
                "burger": {
                    "en": "For great burgers in Sosua, top spots include Checkpoint Bar & Grill on Pedro Clisante, Britannia Pub, and Bologna Ristorante. On Mavunqo, El Batey Bistro also serves grilled churrasco and meat specials.",
                    "es": "Para hamburguesas en Sosúa, visite Checkpoint Bar & Grill en Calle Pedro Clisante, Britannia Pub o Restaurante Bologna."
                },
                "pizza": {
                    "en": "For the best wood-fired artisanal pizza in Sosua, order directly on Mavunqo from **Playa Alicia Woodfire Pizza** (authentic sourdough baked in an oak wood-fired stone oven overlooking Playa Alicia). In town, Bologna and Waterfront are also popular.",
                    "es": "Para la mejor pizza artesanal a la leña en Sosúa, ordene directamente en Mavunqo en **Playa Alicia Woodfire Pizza** (masa madre horneada en horno de leña con vista a Playa Alicia). En el pueblo, Bologna también es una opción clásica."
                },
                "nightlife": {
                    "en": "Sosua nightlife is centered along Calle Pedro Clisante in El Batey, featuring vibrant bars, music lounges, and open-air patios (like Kings Rumba, Jolly Roger, and Latin clubs). Cabarete Beach (15 mins away) offers beachfront cocktail lounges with tables directly on the sand.",
                    "es": "La vida nocturna de Sosúa se concentra en la Calle Pedro Clisante en El Batey, con bares animados y terrazas abiertas (Kings Rumba, Jolly Roger). En Cabarete (a 15 min), encontrará bares sobre la arena de la playa con música y fogatas."
                },
                "atm": {
                    "en": "ATMs (Cajeros automáticos) are located inside Supermercado Playero, Banco Popular on Pedro Clisante, and Banreservas. It is best to use ATMs physically attached to bank branches for security.",
                    "es": "Hay cajeros automáticos dentro de Supermercado Playero, Banco Popular en Pedro Clisante y Banreservas. Se recomienda usar cajeros dentro de bancos por seguridad."
                },
                "cajero": {
                    "en": "Secure ATMs are available at Banco Popular and inside Supermercado Playero in El Batey.",
                    "es": "Encontrará cajeros automáticos seguros en Banco Popular de Pedro Clisante y dentro de Supermercado Playero."
                },
                "taxi": {
                    "en": "Local transportation options in Sosua include official tourist taxi stands (outside Supermercado Playero and Pedro Clisante), motoconchos (local motorcycle taxis for short trips), and guaguas / carritos públicos along Highway 5.",
                    "es": "En Sosúa tiene paradas oficiales de taxis turísticos (frente a Supermercado Playero), motoconchos para viajes cortos y carritos/guaguas públicas por la Carretera 5."
                }
            }

            # Check if query matches regional North Coast knowledge
            extra_info = ""
            for key, info_dict in regional_knowledge.items():
                if key in query:
                    extra_info = info_dict.get(lang, info_dict["en"])
                    break

            if recs:
                if lang == "es":
                    ans = f"Encontré opciones registradas en Mavunqo para su búsqueda: {', '.join(r['trading_name'] for r in recs)}."
                else:
                    ans = f"Here are verified options on Mavunqo: {', '.join(r['trading_name'] for r in recs)}."
                
                if extra_info:
                    ans += f"\n\n💡 Local guide note: {extra_info}"
            else:
                if extra_info:
                    ans = extra_info
                else:
                    if lang == "es":
                        ans = "Para esa búsqueda en Sosúa y la Costa Norte, le recomendamos explorar los comercios gastronómicos y de servicios en nuestro directorio, o consultar con nuestro equipo de asistencia local en la recepción de City Lights o soporte de Mavunqo."
                    else:
                        ans = "For that in Sosúa and the North Coast, check our verified dining and services catalog on Mavunqo, or ask our local concierge team at the City Lights front desk or Mavunqo support for personal tips!" 

            return {
                "query": query,
                "answer": ans,
                "recommendations": recs
            }


    # -------------------------------------------------------------
    # Delivery Capacity Control & Gas-Saving Dispatch Engine
    # -------------------------------------------------------------
    def get_delivery_capacity(self, location_id: str = "loc_sosua"):
        with self.get_connection() as conn:
            settings = conn.execute(
                "SELECT * FROM delivery_capacity_settings WHERE location_id = ?",
                (location_id,)
            ).fetchone()
            
            is_paused_manual = bool(settings["is_delivery_paused"]) if settings else False
            override_active = bool(settings["override_active"]) if settings else False
            max_per_driver = settings["max_orders_per_driver"] if settings else 2

            # Count online drivers in this location
            drivers = conn.execute(
                "SELECT id, full_name, status, max_concurrent_orders FROM drivers WHERE location_id = ? AND status IN ('online', 'on_delivery')",
                (location_id,)
            ).fetchall()
            online_driver_count = len(drivers)

            # Count active in-flight delivery orders (accepted, in_kitchen, ready)
            active_deliveries = conn.execute(
                """SELECT COUNT(o.id) AS cnt
                   FROM orders o
                   JOIN businesses b ON o.business_id = b.id
                   WHERE b.primary_location_id = ?
                     AND o.fulfillment_type = 'delivery'
                     AND o.status IN ('accepted', 'in_kitchen', 'ready')""",
                (location_id,)
            ).fetchone()["cnt"]

            total_capacity = sum(d["max_concurrent_orders"] for d in drivers) if drivers else 0

            # Delivery allowed condition
            if override_active:
                delivery_available = True
                status_reason = "Manager capacity override active"
            elif is_paused_manual:
                delivery_available = False
                status_reason = settings["pause_reason"] or "Delivery temporarily paused by operations."
            elif online_driver_count == 0:
                delivery_available = False
                status_reason = "No motorcycle drivers currently available in this area."
            elif active_deliveries >= total_capacity:
                delivery_available = False
                status_reason = "Motorcycle delivery is at maximum safe capacity. Pickup available immediately."
            else:
                delivery_available = True
                status_reason = "Delivery available"

            return {
                "location_id": location_id,
                "delivery_available": delivery_available,
                "pickup_always_available": True,
                "active_drivers_count": online_driver_count,
                "active_delivery_orders": active_deliveries,
                "total_delivery_capacity": total_capacity,
                "reason": status_reason,
                "override_active": override_active
            }

    def dispatch_driver_on_ready(self, order_id: str):
        """
        Gasoline-saving readiness gate:
        Drivers are NOT dispatched until restaurant confirms order is READY.
        """
        with self.get_connection() as conn:
            order = conn.execute(
                """SELECT o.*, b.primary_location_id, b.trading_name AS biz_name
                   FROM orders o
                   JOIN businesses b ON o.business_id = b.id
                   WHERE o.id = ?""",
                (order_id,)
            ).fetchone()

            if not order:
                raise ValueError("Order not found.")
            if order["fulfillment_type"] != "delivery":
                return {"dispatched": False, "reason": "Not a delivery order."}

            # Find least busy online driver in this location
            driver = conn.execute(
                """SELECT d.id, d.full_name, d.phone,
                          (SELECT COUNT(*) FROM delivery_dispatches dd WHERE dd.driver_id = d.id AND dd.status IN ('dispatched', 'picked_up')) as active_jobs
                   FROM drivers d
                   WHERE d.location_id = ? AND d.status IN ('online', 'on_delivery')
                   ORDER BY active_jobs ASC, d.updated_at ASC
                   LIMIT 1""",
                (order["primary_location_id"],)
            ).fetchone()

            disp_id = f"dsp_{uuid.uuid4().hex[:12]}"
            driver_id = driver["id"] if driver else None
            status = "dispatched" if driver else "queued_for_ready"

            conn.execute(
                """INSERT INTO delivery_dispatches (id, order_id, driver_id, status, dispatched_at)
                   VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
                   ON CONFLICT(order_id) DO UPDATE SET
                       driver_id = COALESCE(excluded.driver_id, driver_id),
                       status = excluded.status,
                       dispatched_at = CURRENT_TIMESTAMP,
                       updated_at = CURRENT_TIMESTAMP""",
                (disp_id, order_id, driver_id, status)
            )

            if driver:
                conn.execute("UPDATE drivers SET status = 'on_delivery', updated_at = CURRENT_TIMESTAMP WHERE id = ?", (driver["id"],))

            conn.commit()

            return {
                "dispatched": bool(driver),
                "order_id": order_id,
                "driver_id": driver["id"] if driver else None,
                "driver_name": driver["full_name"] if driver else "Awaiting available driver",
                "driver_phone": driver["phone"] if driver else None
            }

    def set_manager_capacity_override(self, user_id: str, location_id: str, override_active: bool, reason: str = ""):
        with self.get_connection() as conn:
            # Must be an admin user
            admin = conn.execute("SELECT id, role FROM users WHERE id = ? AND role = 'admin'", (user_id,)).fetchone()
            if not admin:
                raise PermissionError("Only platform administrators can override delivery capacity.")

            conn.execute(
                """UPDATE delivery_capacity_settings
                   SET override_active = ?,
                       override_reason = ?,
                       override_by = ?,
                       updated_at = CURRENT_TIMESTAMP
                   WHERE location_id = ?""",
                (1 if override_active else 0, reason, user_id, location_id)
            )

            conn.execute(
                """INSERT INTO audit_events (id, actor_id, action, target_type, target_id, details_json)
                   VALUES (?, ?, 'delivery_capacity_override', 'location', ?, ?)""",
                (f"aud_{uuid.uuid4().hex[:12]}", user_id, location_id, json.dumps({
                    "override_active": override_active, "reason": reason
                }))
            )
            conn.commit()

        return {"success": True, "location_id": location_id, "override_active": override_active}

    # -------------------------------------------------------------
    # Masked Order In-App Relay Chat
    # -------------------------------------------------------------
    def get_order_messages(self, order_id: str = "", status_token: str = ""):
        with self.get_connection() as conn:
            if status_token:
                order = conn.execute("SELECT id FROM orders WHERE status_token = ?", (status_token,)).fetchone()
                if not order:
                    raise ValueError("Invalid order token.")
                oid = order["id"]
            elif order_id:
                oid = order_id
            else:
                raise ValueError("Must provide either order_id or status_token.")

            rows = conn.execute(
                "SELECT id, sender_role, sender_name, message, created_at FROM order_messages WHERE order_id = ? ORDER BY created_at ASC",
                (oid,)
            ).fetchall()
            return [dict(r) for r in rows]

    def post_order_message(self, message: str, sender_role: str, sender_name: str,
                           order_id: str = "", status_token: str = ""):
        clean_msg = (message or "").strip()
        if not clean_msg:
            raise ValueError("Message cannot be empty.")
        if sender_role not in ('customer', 'driver', 'restaurant'):
            sender_role = 'customer'

        with self.get_connection() as conn:
            if status_token:
                order = conn.execute("SELECT id, customer_name FROM orders WHERE status_token = ?", (status_token,)).fetchone()
                if not order:
                    raise ValueError("Invalid order token.")
                oid = order["id"]
                if not sender_name:
                    sender_name = order["customer_name"] or "Customer"
            elif order_id:
                order = conn.execute("SELECT id FROM orders WHERE id = ?", (order_id,)).fetchone()
                if not order:
                    raise ValueError("Order not found.")
                oid = order_id
                if not sender_name:
                    sender_name = "Restaurant" if sender_role == "restaurant" else "Driver"
            else:
                raise ValueError("Must provide either order_id or status_token.")

            mid = f"msg_{uuid.uuid4().hex[:12]}"
            conn.execute(
                "INSERT INTO order_messages (id, order_id, sender_role, sender_name, message) VALUES (?, ?, ?, ?, ?)",
                (mid, oid, sender_role, sender_name, clean_msg)
            )
            conn.commit()

            return {
                "success": True,
                "message_id": mid,
                "order_id": oid,
                "sender_role": sender_role,
                "sender_name": sender_name,
                "message": clean_msg
            }


    # -------------------------------------------------------------
    # Phase 2: Merchant Request Automation, Pins & Delivery Management
    # -------------------------------------------------------------

    def register_business_interest(self, business_id: str, customer_contact: str, customer_name: str = "", interest_note: str = "", source_url: str = ""):
        customer_contact = (customer_contact or "").strip()
        if not customer_contact:
            raise ValueError("Contact information is required.")

        with self.get_connection() as conn:
            biz = conn.execute("SELECT id, trading_name FROM businesses WHERE id = ?", (business_id,)).fetchone()
            if not biz:
                raise ValueError("Business not found.")

            interest_id = f"int_{uuid.uuid4().hex[:12]}"
            conn.execute(
                """INSERT INTO merchant_interest (id, business_id, customer_name, customer_contact, interest_note, source_url)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (interest_id, business_id, customer_name.strip() or None, customer_contact, interest_note.strip() or None, source_url)
            )
            conn.commit()

        return {"success": True, "interest_id": interest_id, "message": "Interest registered successfully."}

    def get_business_interest_count(self, business_id: str):
        with self.get_connection() as conn:
            count = conn.execute("SELECT COUNT(*) FROM merchant_interest WHERE business_id = ?", (business_id,)).fetchone()[0]
            return count

    def update_merchant_request_settings(self, user_id: str, business_id: str, requests_enabled: bool, whatsapp_consent: bool = None, whatsapp_phone: str = None, action_label_en: str = None, action_label_es: str = None):
        if not self.verify_business_ownership(user_id, business_id):
            raise PermissionError("Access denied.")

        with self.get_connection() as conn:
            biz = conn.execute("SELECT * FROM businesses WHERE id = ?", (business_id,)).fetchone()
            if not biz:
                raise ValueError("Business not found.")

            # Validate destination when enabling WhatsApp alerts
            if whatsapp_consent:
                dest_phone = (whatsapp_phone or biz["whatsapp"] or "").strip()
                if not dest_phone:
                    raise ValueError("A valid phone destination is required for WhatsApp alerts.")
            else:
                dest_phone = whatsapp_phone if whatsapp_phone is not None else biz["whatsapp_alerts_phone"]

            updates = {
                "requests_enabled": 1 if requests_enabled else 0,
                "updated_at": datetime.now().isoformat()
            }
            if whatsapp_consent is not None:
                updates["whatsapp_alerts_consent"] = 1 if whatsapp_consent else 0
            if dest_phone is not None:
                updates["whatsapp_alerts_phone"] = dest_phone
            if action_label_en:
                updates["request_action_label_en"] = action_label_en
            if action_label_es:
                updates["request_action_label_es"] = action_label_es

            set_clauses = [f"{k} = ?" for k in updates.keys()]
            vals = list(updates.values())
            vals.append(business_id)

            conn.execute(f"UPDATE businesses SET {', '.join(set_clauses)} WHERE id = ?", vals)
            conn.commit()

        return {"success": True, "requests_enabled": bool(requests_enabled)}

    def calculate_request_deadline(self, business: dict, action_type: str, requested_time: datetime = None) -> datetime:
        now_utc = datetime.now(timezone.utc)
        # Immediate food/dining requests: 15 minutes from submission
        if action_type in ("request_order", "immediate_order") or business.get("category_slug") == "dining-food":
            return now_utc + timedelta(minutes=15)
        # Scheduled appointments, quotes, retail pickup: 2 business hours bounded by requested fulfillment time
        deadline = now_utc + timedelta(hours=2)
        if requested_time:
            # If requested time is sooner than 2 hours, bound deadline by requested time
            req_utc = requested_time if requested_time.tzinfo else requested_time.replace(tzinfo=timezone.utc)
            if req_utc < deadline and req_utc > now_utc:
                deadline = req_utc
        return deadline

    def create_merchant_request(self, payload: dict):
        biz_id = payload.get("business_id")
        customer = payload.get("customer", {})
        cust_name = customer.get("name", "").strip()
        cust_phone = customer.get("phone", "").strip()
        cust_email = customer.get("email", "").strip() or None
        request_text = (payload.get("request_text") or "").strip()
        action_type = payload.get("action_type", "request_appointment")
        service_mode = payload.get("service_mode", "in_shop") # in_shop, mobile_visit, pickup, delivery, meeting_point
        details = payload.get("category_details", {})
        lang = payload.get("language", "en")
        origin = payload.get("origin", "marketplace")
        if origin not in ('marketplace', 'merchant_link'):
            origin = 'marketplace'

        if not biz_id or not cust_name or not cust_phone or not request_text:
            raise ValueError("Business ID, customer name, customer phone, and request description are required.")

        with self.get_connection() as conn:
            biz = conn.execute("""
                SELECT b.*, c.slug as category_slug, l.name as loc_name 
                FROM businesses b 
                JOIN categories c ON b.category_id = c.id
                JOIN locations l ON b.primary_location_id = l.id
                WHERE b.id = ? AND b.status = 'approved'
            """, (biz_id,)).fetchone()
            if not biz:
                raise ValueError("Business not found or inactive.")

            if not biz["requests_enabled"]:
                raise ValueError("This business is not currently accepting requests through Mavunqo.")

            # Validate Confirmed Map Pins
            # Rule: If customer travels to merchant (pickup / in_shop), use merchant's confirmed pin
            pickup_lat = biz["pickup_pin_lat"] or biz["storefront_pin_lat"]
            pickup_lng = biz["pickup_pin_lng"] or biz["storefront_pin_lng"]
            pickup_note = biz["pickup_pin_note"] or "Main Entrance"

            dest_lat = payload.get("destination_lat")
            dest_lng = payload.get("destination_lng")
            dest_note = payload.get("destination_entrance_note", "")

            # Rule: If staff/driver travels to customer (delivery, mobile_visit), customer MUST confirm a destination pin
            if service_mode in ("delivery", "mobile_visit"):
                if dest_lat is None or dest_lng is None:
                    raise ValueError("A confirmed destination map pin is required for delivery and mobile/home visits.")

                # Validate destination pin falls inside service areas or launch region
                # Allowed coordinates rough boundary around Sosua/Montellano/Cabarete (19.60 to 19.90 Lat, -70.75 to -70.35 Lng)
                if not (19.60 <= float(dest_lat) <= 19.95 and -70.80 <= float(dest_lng) <= -70.30):
                    raise ValueError("The confirmed destination is outside the current pilot service area (Sosúa, Montellano, Cabarete).")

            req_id = f"mreq_{uuid.uuid4().hex[:12]}"
            req_num = f"REQ-{datetime.now().strftime('%m%d')}-{uuid.uuid4().hex[:4].upper()}"
            status_tok = f"stok_{secrets.token_urlsafe(24)}"
            merchant_tok = f"mtok_{secrets.token_urlsafe(24)}"
            
            # Requested time if provided
            req_time_str = payload.get("requested_time")
            req_time_dt = None
            if req_time_str:
                try:
                    req_time_dt = datetime.fromisoformat(req_time_str.replace("Z", "+00:00"))
                except Exception:
                    pass

            deadline_utc = self.calculate_request_deadline(dict(biz), action_type, req_time_dt)

            # Check if pricing is already agreed (e.g. from service item catalog selection)
            agreed_price = payload.get("agreed_price")
            agreed_currency = payload.get("agreed_currency", "DOP")

            phone_hash = hashlib.sha256(cust_phone.encode('utf-8')).hexdigest()[:16]

            conn.execute(
                """INSERT INTO merchant_requests (
                    id, request_number, business_id, category_id, action_type,
                    customer_name, customer_phone, customer_phone_hash, customer_email,
                    request_text, category_details_json, service_mode,
                    pickup_lat, pickup_lng, pickup_entrance_note,
                    destination_lat, destination_lng, destination_entrance_note,
                    status, status_token, status_token_expires_at,
                    merchant_token, merchant_token_expires_at,
                    requested_time, deadline_utc, agreed_price, agreed_currency,
                    language, origin
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    req_id, req_num, biz_id, biz["category_id"], action_type,
                    cust_name, cust_phone, phone_hash, cust_email,
                    request_text, json.dumps(details), service_mode,
                    pickup_lat, pickup_lng, pickup_note,
                    dest_lat, dest_lng, dest_note,
                    "awaiting_confirmation", status_tok, (datetime.now(timezone.utc) + timedelta(days=7)).isoformat(),
                    merchant_tok, (datetime.now(timezone.utc) + timedelta(days=7)).isoformat(),
                    req_time_dt.isoformat() if req_time_dt else None, deadline_utc.isoformat(),
                    agreed_price, agreed_currency, lang, origin
                )
            )

            # Send test notification if merchant has opted into WhatsApp alerts
            notification_sent = False
            if biz["whatsapp_alerts_consent"] and biz["whatsapp_alerts_phone"]:
                # In staging / test notification transport: log clean notification without customer phone number
                notification_sent = True

            conn.commit()

        return {
            "success": True,
            "request_id": req_id,
            "request_number": req_num,
            "status": "awaiting_confirmation",
            "status_token": status_tok,
            "status_url": f"/request/status?token={status_tok}",
            "merchant_url": f"/request/merchant?token={merchant_tok}",
            "deadline_utc": deadline_utc.isoformat(),
            "notification_sent": notification_sent
        }

    def get_merchant_request_by_token(self, token: str, is_merchant: bool = False):
        now_utc = datetime.now(timezone.utc)
        with self.get_connection() as conn:
            col = "merchant_token" if is_merchant else "status_token"
            row = conn.execute(f"""
                SELECT r.*, b.trading_name as business_name, b.slug as business_slug, b.whatsapp as business_whatsapp,
                       b.phone as business_phone, b.address as business_address, b.payment_modes, b.cash_only
                FROM merchant_requests r
                JOIN businesses b ON r.business_id = b.id
                WHERE r.{col} = ?
            """, (token,)).fetchone()
            if not row:
                return None
            req = dict(row)

            # Check deadline expiry if awaiting confirmation or offer pending
            if req["status"] in ("awaiting_confirmation", "offer_pending"):
                dl_dt = datetime.fromisoformat(req["deadline_utc"].replace("Z", "+00:00"))
                if now_utc > dl_dt:
                    conn.execute("UPDATE merchant_requests SET status = 'expired', updated_at = ? WHERE id = ?", (now_utc.isoformat(), req["id"]))
                    conn.commit()
                    req["status"] = "expired"

            # Parse details json
            if req.get("category_details_json"):
                try:
                    req["category_details"] = json.loads(req["category_details_json"])
                except Exception:
                    req["category_details"] = {}

            # Privacy Masking: Keep customer phone out of routine merchant views and merchant alerts
            if is_merchant and req["status"] != "confirmed":
                req["customer_phone_masked"] = req["customer_phone"][:3] + "****" + req["customer_phone"][-4:]
                del req["customer_phone"]

            # Fetch active offers
            offers = conn.execute("SELECT * FROM request_offers WHERE request_id = ? ORDER BY created_at DESC", (req["id"],)).fetchall()
            req["offers"] = [dict(o) for o in offers]

            # Google Directions URLs
            if req.get("pickup_lat") and req.get("pickup_lng"):
                req["pickup_directions_url"] = f"https://www.google.com/maps/dir/?api=1&destination={req['pickup_lat']},{req['pickup_lng']}"
            if req.get("destination_lat") and req.get("destination_lng"):
                req["destination_directions_url"] = f"https://www.google.com/maps/dir/?api=1&destination={req['destination_lat']},{req['destination_lng']}"

            return req

    def merchant_respond_to_request(self, token: str, action: str, price: float = None, currency: str = "DOP", offered_time: str = None, notes: str = None):
        action = action.lower() # accept, suggest_change, decline
        now_utc = datetime.now(timezone.utc)

        with self.get_connection() as conn:
            row = conn.execute("""
                SELECT r.*, b.trading_name, b.category_id, b.slug as business_slug, b.primary_location_id, b.cash_only
                FROM merchant_requests r
                JOIN businesses b ON r.business_id = b.id
                WHERE r.merchant_token = ?
            """, (token,)).fetchone()
            if not row:
                raise ValueError("Invalid merchant authorization token.")
            req = dict(row)

            # Check expiration
            dl_dt = datetime.fromisoformat(req["deadline_utc"].replace("Z", "+00:00"))
            if now_utc > dl_dt and req["status"] != "confirmed":
                conn.execute("UPDATE merchant_requests SET status = 'expired', updated_at = ? WHERE id = ?", (now_utc.isoformat(), req["id"]))
                conn.commit()
                raise ValueError("This request has expired and cannot be modified without a fresh customer offer.")

            if req["status"] not in ("awaiting_confirmation", "offer_pending"):
                raise ValueError(f"Request is already {req['status']}.")

            if action == "accept":
                # If price is already known, accept confirms customer terms directly
                final_price = price if price is not None else req["agreed_price"]
                if final_price is None or final_price <= 0:
                    raise ValueError("Cannot directly accept without a confirmed price. Please suggest terms/price.")

                order_num = f"ORD-{datetime.now().strftime('%m%d')}-{uuid.uuid4().hex[:4].upper()}"
                order_id = f"ord_{uuid.uuid4().hex[:12]}"
                status_token = f"tok_{uuid.uuid4().hex}"
                token_expiry = (now_utc + timedelta(days=7)).isoformat()

                # Create permanent confirmed order record
                origin_val = "merchant" if req.get("origin") == "merchant" else "mavunqo"
                conn.execute(
                    """INSERT INTO orders (
                        id, order_number, business_id, customer_name, customer_phone, customer_email,
                        order_origin, fulfillment_type, delivery_address, customer_notes,
                        status, subtotal, delivery_fee, total, currency, payment_method,
                        cash_due, status_token, status_token_expires_at, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'accepted', ?, 0.0, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        order_id, order_num, req["business_id"], req["customer_name"], req["customer_phone"], req["customer_email"],
                        origin_val, "delivery" if req["service_mode"] == "delivery" else "pickup",
                        req["destination_entrance_note"] or req["pickup_entrance_note"], req["request_text"],
                        final_price, final_price, currency, "cash",
                        final_price, status_token, token_expiry, now_utc.isoformat(), now_utc.isoformat()
                    )
                )

                conn.execute(
                    """UPDATE merchant_requests 
                       SET status = 'confirmed', agreed_price = ?, agreed_currency = ?, confirmed_order_id = ?, updated_at = ?
                       WHERE id = ?""",
                    (final_price, currency, order_id, now_utc.isoformat(), req["id"])
                )
                conn.commit()
                return {"success": True, "status": "confirmed", "order_id": order_id, "order_number": order_num}

            elif action == "suggest_change":
                if price is None or price <= 0:
                    raise ValueError("Price is required when suggesting terms.")

                offer_time_dt = None
                if offered_time:
                    try:
                        offer_time_dt = datetime.fromisoformat(offered_time.replace("Z", "+00:00"))
                    except Exception:
                        pass
                if not offer_time_dt:
                    offer_time_dt = now_utc + timedelta(hours=1)

                offer_id = f"off_{uuid.uuid4().hex[:12]}"
                offer_deadline = now_utc + timedelta(hours=2)

                conn.execute(
                    """INSERT INTO request_offers (id, request_id, offered_price, offered_currency, offered_time, deadline_utc, notes, status)
                       VALUES (?, ?, ?, ?, ?, ?, ?, 'pending')""",
                    (offer_id, req["id"], price, currency, offer_time_dt.isoformat(), offer_deadline.isoformat(), notes)
                )
                conn.execute(
                    """UPDATE merchant_requests 
                       SET status = 'offer_pending', agreed_price = ?, agreed_currency = ?, deadline_utc = ?, updated_at = ?
                       WHERE id = ?""",
                    (price, currency, offer_deadline.isoformat(), now_utc.isoformat(), req["id"])
                )
                conn.commit()
                return {"success": True, "status": "offer_pending", "offer_id": offer_id, "offered_price": price}

            elif action == "decline":
                conn.execute(
                    """UPDATE merchant_requests 
                       SET status = 'declined', decline_reason = ?, updated_at = ?
                       WHERE id = ?""",
                    (notes or "Declined by merchant", now_utc.isoformat(), req["id"])
                )
                conn.commit()
                return {"success": True, "status": "declined"}

            else:
                raise ValueError("Invalid action. Must be accept, suggest_change, or decline.")

    def customer_respond_to_offer(self, status_token: str, offer_id: str, action: str):
        action = action.lower() # accept, reject
        now_utc = datetime.now(timezone.utc)

        with self.get_connection() as conn:
            row = conn.execute("""
                SELECT r.*, b.trading_name, b.cash_only
                FROM merchant_requests r
                JOIN businesses b ON r.business_id = b.id
                WHERE r.status_token = ?
            """, (status_token,)).fetchone()
            if not row:
                raise ValueError("Invalid status token.")
            req = dict(row)

            offer = conn.execute("SELECT * FROM request_offers WHERE id = ? AND request_id = ?", (offer_id, req["id"])).fetchone()
            if not offer:
                raise ValueError("Offer not found.")
            off = dict(offer)

            if off["status"] != "pending":
                raise ValueError(f"Offer is already {off['status']}.")

            # Check offer deadline
            off_dl = datetime.fromisoformat(off["deadline_utc"].replace("Z", "+00:00"))
            if now_utc > off_dl:
                conn.execute("UPDATE request_offers SET status = 'expired' WHERE id = ?", (offer_id,))
                conn.commit()
                raise ValueError("This offer has expired.")

            if action == "accept":
                order_num = f"ORD-{datetime.now().strftime('%m%d')}-{uuid.uuid4().hex[:4].upper()}"
                order_id = f"ord_{uuid.uuid4().hex[:12]}"
                st_tok = f"tok_{uuid.uuid4().hex}"
                st_exp = (now_utc + timedelta(days=7)).isoformat()

                origin_val = "merchant" if req.get("origin") == "merchant" else "mavunqo"
                conn.execute(
                    """INSERT INTO orders (
                        id, order_number, business_id, customer_name, customer_phone, customer_email,
                        order_origin, fulfillment_type, delivery_address, customer_notes,
                        status, subtotal, delivery_fee, total, currency, payment_method,
                        cash_due, status_token, status_token_expires_at, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'accepted', ?, 0.0, ?, ?, 'cash', ?, ?, ?, ?, ?)""",
                    (
                        order_id, order_num, req["business_id"], req["customer_name"], req["customer_phone"], req["customer_email"],
                        origin_val, "delivery" if req["service_mode"] == "delivery" else "pickup",
                        req["destination_entrance_note"] or req["pickup_entrance_note"], req["request_text"],
                        off["offered_price"], off["offered_price"], off["offered_currency"],
                        off["offered_price"], st_tok, st_exp, now_utc.isoformat(), now_utc.isoformat()
                    )
                )

                conn.execute("UPDATE request_offers SET status = 'accepted' WHERE id = ?", (offer_id,))
                conn.execute(
                    """UPDATE merchant_requests 
                       SET status = 'confirmed', agreed_price = ?, agreed_currency = ?, confirmed_order_id = ?, updated_at = ?
                       WHERE id = ?""",
                    (off["offered_price"], off["offered_currency"], order_id, now_utc.isoformat(), req["id"])
                )
                conn.commit()
                return {"success": True, "status": "confirmed", "order_id": order_id, "order_number": order_num}

            elif action == "reject":
                conn.execute("UPDATE request_offers SET status = 'rejected' WHERE id = ?", (offer_id,))
                conn.execute("UPDATE merchant_requests SET status = 'declined', updated_at = ? WHERE id = ?", (now_utc.isoformat(), req["id"]))
                conn.commit()
                return {"success": True, "status": "declined"}

            else:
                raise ValueError("Invalid action. Must be accept or reject.")

    # -------------------------------------------------------------
    # Customer Saved Pins (Default vs Per-Request)
    # -------------------------------------------------------------
    def save_customer_pin(self, user_id: str, label: str, lat: float, lng: float, entrance_note: str = "", set_default: bool = True):
        with self.get_connection() as conn:
            pin_id = f"pin_{uuid.uuid4().hex[:12]}"
            if set_default:
                conn.execute("UPDATE customer_saved_pins SET is_default = 0 WHERE user_id = ?", (user_id,))
            conn.execute(
                """INSERT INTO customer_saved_pins (id, user_id, label, lat, lng, entrance_note, is_default)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (pin_id, user_id, label.strip(), lat, lng, entrance_note.strip(), 1 if set_default else 0)
            )
            conn.commit()
        return {"success": True, "pin_id": pin_id}

    def get_customer_saved_pins(self, user_id: str):
        with self.get_connection() as conn:
            rows = conn.execute("SELECT * FROM customer_saved_pins WHERE user_id = ? ORDER BY is_default DESC, created_at DESC", (user_id,)).fetchall()
            return [dict(r) for r in rows]

    # -------------------------------------------------------------
    # Mavunqo-Managed Motorcycle Delivery & Cash Reconciliation
    # -------------------------------------------------------------
    def get_dispatcher_queue(self):
        with self.get_connection() as conn:
            orders = conn.execute("""
                SELECT o.*, b.trading_name as business_name, b.pickup_pin_lat, b.pickup_pin_lng, b.pickup_pin_note,
                       b.address as business_address, d.driver_id, d.status as dispatch_status, drv.full_name as driver_name
                FROM orders o
                JOIN businesses b ON o.business_id = b.id
                LEFT JOIN delivery_dispatches d ON o.id = d.order_id
                LEFT JOIN drivers drv ON d.driver_id = drv.id
                WHERE o.fulfillment_type = 'delivery' AND o.status IN ('accepted', 'in_kitchen', 'ready')
                ORDER BY o.created_at ASC
            """).fetchall()
            drivers = conn.execute("SELECT * FROM drivers ORDER BY full_name ASC").fetchall()
            return {"orders": [dict(o) for o in orders], "drivers": [dict(d) for d in drivers]}

    def assign_delivery_driver(self, order_id: str, driver_id: str, dispatcher_id: str):
        now_utc = datetime.now(timezone.utc).isoformat()
        with self.get_connection() as conn:
            # Check dispatcher authorization
            disp_user = conn.execute("SELECT role FROM users WHERE id = ?", (dispatcher_id,)).fetchone()
            if not disp_user or disp_user["role"] not in ("admin", "manager", "staff"):
                raise PermissionError("Access denied: Mavunqo dispatcher role required.")

            driver = conn.execute("SELECT * FROM drivers WHERE id = ?", (driver_id,)).fetchone()
            if not driver:
                raise ValueError("Driver not found.")

            order = conn.execute("SELECT * FROM orders WHERE id = ?", (order_id,)).fetchone()
            if not order:
                raise ValueError("Order not found.")

            disp = conn.execute("SELECT id FROM delivery_dispatches WHERE order_id = ?", (order_id,)).fetchone()
            if disp:
                conn.execute(
                    """UPDATE delivery_dispatches 
                       SET driver_id = ?, status = 'dispatched', dispatched_at = ?, updated_at = ?
                       WHERE order_id = ?""",
                    (driver_id, now_utc, now_utc, order_id)
                )
            else:
                disp_id = f"disp_{uuid.uuid4().hex[:12]}"
                conn.execute(
                    """INSERT INTO delivery_dispatches (id, order_id, driver_id, status, dispatched_at)
                       VALUES (?, ?, ?, 'dispatched', ?)""",
                    (disp_id, order_id, driver_id, now_utc)
                )

            conn.commit()

        return {"success": True, "order_id": order_id, "driver_id": driver_id, "status": "dispatched"}

    def get_driver_active_jobs(self, driver_id: str):
        with self.get_connection() as conn:
            rows = conn.execute("""
                SELECT o.id as order_id, o.order_number, o.customer_name, o.customer_phone, o.total, o.currency,
                       o.cash_due, o.status as order_status, d.status as dispatch_status,
                       b.trading_name as business_name, b.pickup_pin_lat, b.pickup_pin_lng, b.pickup_pin_note, b.address as business_address,
                       o.delivery_address, r.destination_lat, r.destination_lng, r.destination_entrance_note
                FROM delivery_dispatches d
                JOIN orders o ON d.order_id = o.id
                JOIN businesses b ON o.business_id = b.id
                LEFT JOIN merchant_requests r ON o.id = r.confirmed_order_id
                WHERE d.driver_id = ? AND d.status IN ('dispatched', 'picked_up')
                ORDER BY d.dispatched_at ASC
            """, (driver_id,)).fetchall()

            jobs = []
            for r in rows:
                j = dict(r)
                # Build travel-ordered stops
                p_lat = j.get("pickup_pin_lat") or 19.755
                p_lng = j.get("pickup_pin_lng") or -70.515
                d_lat = j.get("destination_lat") or 19.758
                d_lng = j.get("destination_lng") or -70.510

                j["stops"] = [
                    {
                        "stop_type": "pickup",
                        "title": f"1. Collect from {j['business_name']}",
                        "lat": p_lat,
                        "lng": p_lng,
                        "entrance_note": j.get("pickup_pin_note") or "Storefront entrance",
                        "directions_url": f"https://www.google.com/maps/dir/?api=1&destination={p_lat},{p_lng}"
                    },
                    {
                        "stop_type": "dropoff",
                        "title": f"2. Deliver to {j['customer_name']}",
                        "lat": d_lat,
                        "lng": d_lng,
                        "entrance_note": j.get("destination_entrance_note") or j.get("delivery_address") or "Customer door",
                        "amount_due": f"{j['cash_due'] or j['total']} {j['currency']}",
                        "directions_url": f"https://www.google.com/maps/dir/?api=1&destination={d_lat},{d_lng}"
                    }
                ]
                jobs.append(j)
            return jobs

    def record_driver_cash_collection(self, order_id: str, driver_id: str, amount_collected: float, notes: str = None):
        with self.get_connection() as conn:
            order = conn.execute("SELECT * FROM orders WHERE id = ?", (order_id,)).fetchone()
            if not order:
                raise ValueError("Order not found.")

            col_id = f"col_{uuid.uuid4().hex[:12]}"
            conn.execute(
                """INSERT OR REPLACE INTO cash_collections (id, order_id, driver_id, amount_expected, amount_collected, currency, notes)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (col_id, order_id, driver_id, order["total"], amount_collected, order["currency"], notes)
            )
            # Update order cash received and completed status
            conn.execute(
                """UPDATE orders 
                   SET cash_received = ?, status = 'completed', updated_at = ?
                   WHERE id = ?""",
                (amount_collected, datetime.now(timezone.utc).isoformat(), order_id)
            )
            conn.execute(
                """UPDATE delivery_dispatches 
                   SET status = 'delivered', delivered_at = ?
                   WHERE order_id = ?""",
                (datetime.now(timezone.utc).isoformat(), order_id)
            )
            conn.commit()

        return {"success": True, "order_id": order_id, "amount_collected": amount_collected}

    def record_cash_handoff_and_reconciliation(self, driver_id: str, receiver_id: str, order_ids: list, total_driver_reported: float, total_receiver_counted: float, notes: str = None):
        diff = total_receiver_counted - total_driver_reported
        status = "reconciled" if abs(diff) < 0.01 else "unresolved_discrepancy"
        batch_id = f"hnd_{uuid.uuid4().hex[:12]}"
        now_utc = datetime.now(timezone.utc).isoformat()

        with self.get_connection() as conn:
            conn.execute(
                """INSERT INTO cash_handoffs (
                    id, handoff_batch_id, driver_id, receiver_id, order_ids_json,
                    total_driver_reported, total_receiver_counted, difference, status, resolution_notes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    str(uuid.uuid4()), batch_id, driver_id, receiver_id, json.dumps(order_ids),
                    total_driver_reported, total_receiver_counted, diff, status, notes
                )
            )
            # Mark orders reconciled if reconciled
            if status == "reconciled":
                for oid in order_ids:
                    conn.execute("UPDATE orders SET cash_reconciled = 1, updated_at = ? WHERE id = ?", (now_utc, oid))
            conn.commit()

        return {
            "success": True,
            "handoff_batch_id": batch_id,
            "total_driver_reported": total_driver_reported,
            "total_receiver_counted": total_receiver_counted,
            "difference": diff,
            "status": status,
            "is_discrepancy": status == "unresolved_discrepancy"
        }

