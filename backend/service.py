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
                   b.logo_url, b.cover_image_url, b.power_backup_type,
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
                l.name LIKE ? OR 
                LOWER(l.search_aliases) LIKE ?
            )"""
            params.extend([loc_match, f"%{location_id}%", f"%{location_id.lower()}%"])

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
                          initial_services: list = None, legal_name: str = None,
                          referred_by_rep_code: str = None):
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
                    rnc_tax_id, rnc_status, referred_by_rep_code
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?, ?, ?, ?, ?, ?, ?, ?, 'unverified', ?)""",
                (
                    biz_id, owner_id, trading_name, legal_name or trading_name, final_slug,
                    category_id, primary_location_id, description_en, description_es,
                    1 if address else 0, address, 1 if serves_entire_area else 0,
                    website_url or None, whatsapp or None, phone or None, owner_email,
                    rnc_tax_id or None, (referred_by_rep_code or "").strip().upper() or None
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
                    order_origin: str = "mavunqo", customer_notes: str = "",
                    payment_method: str = "cash", driver_tip: float = 0.0,
                    payment_proof_url: str = None, payment_proof_hash: str = None,
                    delivery_pin_lat: float = None, delivery_pin_lng: float = None,
                    promo_opt_in: bool = True, promo_longterm_opt_in: bool = False,
                    idempotency_key: str = None):
        customer_name = (customer_data.get("name") or "").strip()
        customer_phone = (customer_data.get("phone") or "").strip()
        customer_email = (customer_data.get("email") or "").strip()

        if not customer_name or not customer_phone:
            raise ValueError("Customer name and phone number are required.")

        if payment_method not in ("cash", "transfer", "zelle", "wise", "card", "cash_or_card"):
            payment_method = "cash"

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
                "SELECT id, trading_name, status, primary_location_id, custom_commission_rate FROM businesses WHERE id = ? AND status = 'approved'",
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

            cap_row = conn.execute(
                "SELECT rain_mode_active FROM delivery_capacity_settings WHERE location_id = 'loc_sosua'"
            ).fetchone()
            rain_mode_active = bool(cap_row["rain_mode_active"]) if cap_row else False

            base_del_fee = self._get_setting_float(conn, "delivery_fee_dop", 100.0)
            rain_fee = self._get_setting_float(conn, "rain_hazard_fee_dop", 50.0)
            dist_fee = self._calculate_distance_delivery_fee(conn, business_id, delivery_pin_lat, delivery_pin_lng, base_del_fee)
            delivery_fee = (dist_fee + (rain_fee if rain_mode_active else 0.0)) if fulfillment_type == "delivery" else 0.0
            tip_amount = round(max(0.0, float(driver_tip or 0.0)), 2) if fulfillment_type == "delivery" else 0.0
            total = round(subtotal + delivery_fee + tip_amount, 2)

            idem_key = (idempotency_key or "").strip() or None
            dup = None
            if idem_key:
                dup = conn.execute(
                    """SELECT id, order_number, status_token, total, subtotal, delivery_fee, driver_tip, payment_method, payment_proof_url, status
                       FROM orders WHERE idempotency_key = ? LIMIT 1""",
                    (idem_key,)
                ).fetchone()
            if not dup:
                # 15-second double-tap / duplicate order guard fallback
                dup = conn.execute(
                    """SELECT id, order_number, status_token, total, subtotal, delivery_fee, driver_tip, payment_method, payment_proof_url, status
                       FROM orders
                       WHERE business_id = ?
                         AND customer_phone = ?
                         AND payment_method = ?
                         AND fulfillment_type = ?
                         AND COALESCE(payment_proof_hash, '') = COALESCE(?, '')
                         AND ABS(total - ?) < 0.01
                         AND datetime(created_at) >= datetime('now', '-15 seconds')
                       ORDER BY created_at DESC LIMIT 1""",
                    (business_id, customer_phone, payment_method, fulfillment_type, payment_proof_hash, total)
                ).fetchone()
            if dup:
                return {
                    "success": True,
                    "duplicate_prevented": True,
                    "order_id": dup["id"],
                    "order_number": dup["order_number"],
                    "business_id": business_id,
                    "business_name": biz["trading_name"],
                    "status": dup["status"],
                    "status_token": dup["status_token"],
                    "status_url": f"/order/status?token={dup['status_token']}",
                    "subtotal": dup["subtotal"],
                    "delivery_fee": dup["delivery_fee"],
                    "driver_tip": dup["driver_tip"],
                    "total": dup["total"],
                    "currency": "DOP",
                    "payment_method": dup["payment_method"],
                    "payment_proof_url": dup["payment_proof_url"],
                    "cash_due": dup["total"] if dup["payment_method"] == "cash" else 0.0,
                }

            # Insert order
            conn.execute(
                """INSERT INTO orders (
                    id, order_number, business_id, customer_name, customer_phone, customer_email,
                    order_origin, fulfillment_type, delivery_address, delivery_pin_lat, delivery_pin_lng, customer_notes,
                    status, subtotal, delivery_fee, driver_tip, total, currency, payment_method,
                    payment_proof_url, payment_proof_hash, promo_opt_in, promo_longterm_opt_in,
                    idempotency_key, cash_due, status_token, status_token_expires_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?, ?, ?, ?, 'DOP', ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    order_id, order_num, business_id, customer_name, customer_phone, customer_email,
                    order_origin, fulfillment_type, delivery_address, delivery_pin_lat, delivery_pin_lng, customer_notes,
                    subtotal, delivery_fee, tip_amount, total, payment_method,
                    payment_proof_url, payment_proof_hash,
                    1 if promo_opt_in else 0,
                    1 if promo_longterm_opt_in else 0,
                    idem_key,
                    total if payment_method == 'cash' else 0.0,
                    status_token, expires_at.isoformat()
                )
            )

            conn.execute(
                """INSERT INTO promo_preferences (phone, customer_name, promo_opt_in, promo_longterm_opt_in, last_location_id, in_service_area, last_order_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                   ON CONFLICT(phone) DO UPDATE SET
                     customer_name = excluded.customer_name,
                     promo_opt_in = excluded.promo_opt_in,
                     promo_longterm_opt_in = CASE WHEN excluded.promo_longterm_opt_in = 1 THEN 1 ELSE promo_preferences.promo_longterm_opt_in END,
                     last_location_id = COALESCE(excluded.last_location_id, promo_preferences.last_location_id),
                     in_service_area = 1,
                     last_order_at = CURRENT_TIMESTAMP,
                     updated_at = CURRENT_TIMESTAMP""",
                (customer_phone, customer_name, 1 if promo_opt_in else 0, 1 if promo_longterm_opt_in else 0, biz["primary_location_id"])
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
            # Uses per-business negotiated override if set, otherwise global platform standard commission rate.
            # Delivery fee and driver tip are excluded from commission base.
            from .tokens_and_attribution import STANDARD_COMMISSION_RATE
            global_rate = self._get_setting_float(conn, "standard_commission_rate", STANDARD_COMMISSION_RATE)
            commission_rate = float(biz["custom_commission_rate"]) if biz["custom_commission_rate"] is not None else global_rate
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
            "business_name": biz["trading_name"],
            "total": total,
            "currency": "DOP",
            "payment_method": payment_method,
            "payment_proof_url": payment_proof_url,
            "status_token": status_token,
            "status_url": f"/order/status?token={status_token}"
        }

    def verify_order_payment(self, order_id: str, dispatcher_id: str, source: str = "dispatcher_manual"):
        with self.get_connection() as conn:
            disp_user = conn.execute("SELECT role FROM users WHERE id = ?", (dispatcher_id,)).fetchone()
            if not disp_user or disp_user["role"] not in ("admin", "manager", "staff"):
                raise PermissionError("Access denied: Mavunqo dispatcher role required.")
            order = conn.execute("SELECT id, order_number FROM orders WHERE id = ?", (order_id,)).fetchone()
            if not order:
                raise ValueError("Order not found.")
            conn.execute(
                """UPDATE orders
                   SET payment_verified = 1, payment_verified_source = ?, updated_at = CURRENT_TIMESTAMP
                   WHERE id = ?""",
                (source, order_id)
            )
            conn.commit()
        return {"success": True, "order_id": order_id, "order_number": order["order_number"], "payment_verified": True}

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
            from .tokens_and_attribution import STANDARD_COMMISSION_RATE
            biz_row = conn.execute("SELECT custom_commission_rate FROM businesses WHERE id = ?", (business_id,)).fetchone()
            global_rate = self._get_setting_float(conn, "standard_commission_rate", STANDARD_COMMISSION_RATE)
            effective_rate = float(biz_row["custom_commission_rate"]) if (biz_row and biz_row["custom_commission_rate"] is not None) else global_rate

            rows = conn.execute(
                """SELECT f.*, o.order_number, o.status AS order_status, o.payment_method, o.created_at AS order_created_at
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
            gross_completed = sum(r["commissionable_amount"] for r in records if r["status"] == "accrued")
            gross_pending = sum(r["commissionable_amount"] for r in records if r["status"] == "pending")
            completed_count = sum(1 for r in records if r["status"] == "accrued")
            pending_count = sum(1 for r in records if r["status"] == "pending")

            payout_rows = conn.execute(
                """SELECT payout_batch_id, gross_subtotal, commission_retained, net_payout_amount, payout_method, status, settled_at, created_at
                   FROM merchant_payouts
                   WHERE business_id = ?
                   ORDER BY created_at DESC LIMIT 20""",
                (business_id,)
            ).fetchall()

            return {
                "business_id": business_id,
                "effective_commission_rate": effective_rate,
                "total_orders_count": len(records),
                "completed_orders_count": completed_count,
                "pending_orders_count": pending_count,
                "gross_completed_sales": round(gross_completed, 2),
                "gross_pending_sales": round(gross_pending, 2),
                "net_completed_payout": round(gross_completed - total_accrued, 2),
                "total_accrued_fees": round(total_accrued, 2),
                "total_pending_fees": round(total_pending, 2),
                "total_reversed_fees": round(total_reversed, 2),
                "currency": "DOP",
                "statement_lines": records,
                "payouts_history": [dict(p) for p in payout_rows]
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
    # AI Concierge Query Engine (Bilingual/Trilingual, Role-Aware & Grounded)
    # -------------------------------------------------------------
    @staticmethod
    def _strip_accents(text: str) -> str:
        trans = str.maketrans("áéíóúàèìòùâêîôûäëïöüñç", "aeiouaeiouaeiouaeiounc")
        return (text or "").lower().translate(trans)

    @staticmethod
    def _format_hours_dict(hours_json_raw: str, lang: str = "en") -> str:
        try:
            hours_obj = json.loads(hours_json_raw or "{}")
        except Exception:
            hours_obj = {}
        if not isinstance(hours_obj, dict) or not hours_obj:
            return ""
        key_map = {
            "monday_saturday": {"en": "Monday – Saturday", "es": "Lunes – Sábado", "fr": "Lundi – Samedi"},
            "monday_friday": {"en": "Monday – Friday", "es": "Lunes – Viernes", "fr": "Lundi – Vendredi"},
            "sunday": {"en": "Sunday", "es": "Domingo", "fr": "Dimanche"},
            "saturday": {"en": "Saturday", "es": "Sábado", "fr": "Samedi"},
            "daily": {"en": "Daily", "es": "Todos los días", "fr": "Tous les jours"},
        }
        parts = []
        for k, v in hours_obj.items():
            kl = str(k).lower()
            if kl in key_map:
                label = key_map[kl].get(lang, key_map[kl]["en"])
            else:
                label = " – ".join(w.capitalize() for w in kl.split("_") if w)
            val = str(v)
            if val.strip().lower() == "closed":
                val = "Cerrado" if lang == "es" else ("Fermé" if lang == "fr" else "Closed")
            parts.append(f"{label}: {val}")
        return "; ".join(parts)

    def ask_ai_concierge(self, query: str, lang: str = "en", role: str = "customer", slug: str = ""):
        raw_query = (query or "").strip()
        query = raw_query.lower()
        norm_query = self._strip_accents(query)
        lang = (lang or "en").lower()
        is_es = (lang == "es")
        is_fr = (lang == "fr")

        if not query:
            if is_es:
                greeting = "Hola, ¿en qué puedo ayudarte hoy en Mavunqo?"
            elif is_fr:
                greeting = "Bonjour ! Comment puis-je vous aider à Sosúa et Puerto Plata ?"
            else:
                greeting = "Hello! How can I assist you with services, dining, or hotel stays in Sosúa and Puerto Plata?"
            return {"answer": greeting, "recommendations": []}

        # Role-specific platform guidance (Owners, Drivers, Admins)
        if role == "owner":
            if any(k in norm_query for k in ["price", "precio", "photo", "foto", "edit", "editar", "update", "actualizar", "service", "servicio"]):
                return {
                    "answer": (
                        "Para actualizar precios, fotos o servicios: haz clic en '+ Add Item / Photo' en tu panel, o envíanos los cambios por WhatsApp y nosotros los actualizamos por ti."
                        if is_es else
                        "To update prices, photos, or services: click '+ Add Item / Photo' in your dashboard, or simply send your updates via WhatsApp and our team will update your storefront."
                    ),
                    "recommendations": []
                }
            if any(k in norm_query for k in ["commission", "comision", "fee", "tarifa", "plan", "monthly", "mensual", "10%"]):
                return {
                    "answer": (
                        "Tu perfil básico es gratis. En citas generadas por Mavunqo aplica la comisión acordada (sin recargo al cliente), o puedes optar por un plan mensual fijo después del periodo introductorio gratis."
                        if is_es else
                        "Your basic listing is free. Platform-booked appointments carry the agreed commission (never added onto the customer's price), or you can switch to a flat monthly plan after the free intro period."
                    ),
                    "recommendations": []
                }
        elif role == "driver":
            if any(k in norm_query for k in ["pay", "pago", "distance", "distancia", "fee", "tarifa", "pin", "address", "direccion"]):
                return {
                    "answer": (
                        "Tarifa base de 100 DOP hasta 3 km, más 25 DOP por km adicional (y 100% de la propina). Por privacidad del cliente, solo verás el pin de Google Maps y nota de entrada."
                        if is_es else
                        "Base payout is 100 DOP within 3 km, plus 25 DOP per extra km (plus 100% of driver tips). For customer privacy, you receive the Google Maps pin and entrance note only."
                    ),
                    "recommendations": []
                }
        elif role == "admin":
            if any(k in norm_query for k in ["security", "alert", "alerta", "seguridad", "audit"]):
                return {
                    "answer": "Security Monitor active: check /api/admin/security-alerts for rate-limit blocks and threat probes logged to audit_events.",
                    "recommendations": []
                }

        stopwords = {
            "what", "are", "the", "for", "and", "with", "this", "that", "your", "about",
            "when", "where", "how", "does", "have", "can", "you", "find", "near", "open",
            "close", "hours", "hour", "time", "schedule", "much", "cost", "price", "prices",
            "que", "cual", "cuales", "son", "los", "las", "para", "con", "una", "uno", "del",
            "por", "como", "donde", "horario", "horarios", "hora", "horas", "abierto",
            "cierran", "abren", "precio", "precios", "cuanto", "les", "des", "pour", "avec",
            "est", "sont", "quel", "quels", "quelles", "heures", "heure", "horaire", "horaires",
            "ouvert", "prix", "tarif", "tarifs", "in", "en", "at", "de", "la", "el", "un",
        }
        loc_words = {"puerto", "plata", "sosua", "cabarete", "montellano", "batey", "charamicos", "maimon"}
        synonym_groups = [
            {"massage", "masaje", "masajes", "masajista", "spa"},
            {"facial", "pedicure", "manicure", "depilacion", "reflexologia", "drenaje", "terapia", "fisica", "rehab", "rehabilitacion"},
            {"lawyer", "lawyers", "abogado", "abogados", "legal", "avocat", "notary", "notario", "residency", "residencia", "realestate"},
            {"tour", "tours", "excursion", "excursiones", "waterfall", "waterfalls", "charcos", "damajagua", "catamaran", "buggy", "atv", "snorkel", "fishing", "pesca"},
            {"hotel", "hotels", "room", "rooms", "stay", "stays", "hospedaje", "habitacion", "habitaciones", "dorm", "dorms", "hostel", "villa", "villas"},
            {"car", "carro", "carros", "auto", "autos", "vehicle", "vehiculo", "mecanico", "mechanic", "aire", "ac", "a/c", "brake", "freno", "frenos", "repair", "reparar", "reparacion", "taller"},
            {"food", "comida", "restaurant", "restaurante", "eat", "comer", "dinner", "lunch", "breakfast", "pizza", "taco", "tacos", "burger", "seafood", "fish", "pescado", "chillo", "pollo"},
            {"fashion", "clothing", "clothes", "ropa", "dress", "dresses", "vestido", "vestidos", "boutique", "bikini", "swimsuit", "jeans"},
            {"vet", "veterinario", "pet", "pets", "dog", "perro", "cat", "gato", "animal", "clinica"},
            {"scooter", "moto", "motorcycle", "pasola", "rental", "rentar", "alquiler"},
        ]

        tokens = re.findall(r"[a-z0-9]+", norm_query)
        location_tokens = [w for w in tokens if w in loc_words]
        intent_tokens = [w for w in tokens if len(w) >= 2 and w not in stopwords and w not in loc_words]

        expanded_terms = set(intent_tokens)
        for tok in intent_tokens:
            for grp in synonym_groups:
                if tok in grp:
                    expanded_terms.update(grp)

        with self.get_connection() as conn:
            biz_rows = conn.execute(
                """
                SELECT b.id, b.trading_name, b.slug, b.description_en, b.description_es,
                       b.whatsapp, b.phone, b.hours_json, b.address, b.logo_url, b.cover_image_url,
                       b.primary_location_id, c.name_en AS category, c.name_es AS category_es,
                       l.name AS location
                FROM businesses b
                JOIN categories c ON b.category_id = c.id
                JOIN locations l ON b.primary_location_id = l.id
                WHERE b.status = 'approved'
                """
            ).fetchall()

            srv_by_biz = {}
            for sr in conn.execute("SELECT business_id, name_en, name_es, description_en, description_es, price, currency, display_price FROM services ORDER BY sort_order ASC").fetchall():
                srv_by_biz.setdefault(sr["business_id"], []).append(dict(sr))

            areas_by_biz = {}
            for ar in conn.execute(
                "SELECT bsa.business_id, l.name FROM business_service_areas bsa JOIN locations l ON bsa.location_id = l.id"
            ).fetchall():
                areas_by_biz.setdefault(ar["business_id"], []).append(ar["name"])

            scored = []
            slug_norm = self._strip_accents(slug or "")
            context_biz = None

            for row in biz_rows:
                b = dict(row)
                bid = b["id"]
                name_norm = self._strip_accents(b["trading_name"])
                cat_norm = self._strip_accents(f"{b['category']} {b['category_es']}")
                desc_norm = self._strip_accents(f"{b['description_en'] or ''} {b['description_es'] or ''}")
                srv_list = srv_by_biz.get(bid, [])
                srv_names_norm = self._strip_accents(" ".join(f"{s['name_en']} {s['name_es']}" for s in srv_list))
                srv_desc_norm = self._strip_accents(" ".join(f"{s['description_en'] or ''} {s['description_es'] or ''}" for s in srv_list))
                area_text_norm = self._strip_accents(b["location"] + " " + " ".join(areas_by_biz.get(bid, [])))

                if slug_norm and self._strip_accents(b["slug"]) == slug_norm:
                    context_biz = b

                name_words = [w for w in re.findall(r"[a-z0-9]+", name_norm) if len(w) >= 3]
                direct_name_hit = False
                score = 0

                if len(name_norm) >= 4 and name_norm in norm_query:
                    score += 150
                    direct_name_hit = True
                elif len(name_words) >= 2 and sum(1 for nw in name_words if nw in tokens) >= min(2, len(name_words)):
                    score += 110
                    direct_name_hit = True

                intent_score = 0
                for term in expanded_terms:
                    is_orig = term in intent_tokens
                    weight_mult = 1.0 if is_orig else 0.75
                    if re.search(rf"\b{re.escape(term)}\b", name_norm):
                        intent_score += int(40 * weight_mult)
                    if re.search(rf"\b{re.escape(term)}\b", cat_norm) or re.search(rf"\b{re.escape(term)}\b", srv_names_norm):
                        intent_score += int(28 * weight_mult)
                    if re.search(rf"\b{re.escape(term)}\b", desc_norm) or re.search(rf"\b{re.escape(term)}\b", srv_desc_norm):
                        intent_score += int(12 * weight_mult)

                loc_score = 0
                for lw in location_tokens:
                    if lw in area_text_norm:
                        loc_score += 20

                # Location boost applies only if query had no specific service intent OR this business matched that intent
                if intent_tokens and intent_score == 0 and not direct_name_hit:
                    total_score = 0
                else:
                    total_score = score + intent_score + loc_score

                if total_score > 0:
                    b["_score"] = total_score
                    b["_direct"] = direct_name_hit
                    scored.append(b)

            scored.sort(key=lambda item: (-item["_score"], item["trading_name"]))
            recs = scored[:4]

            # Explicit legacy boosts only when relevant keywords are present
            if any(k in norm_query for k in ["fish", "pescado", "seafood", "marisco", "chillo"]) and not any(r["id"] == "biz_el_batey_bistro" for r in recs):
                fb = conn.execute("SELECT id, trading_name, slug, description_en, description_es, whatsapp, phone, hours_json, logo_url, cover_image_url FROM businesses WHERE id = 'biz_el_batey_bistro'").fetchone()
                if fb:
                    recs.append(dict(fb))

            if any(k in norm_query for k in ["hotel", "room", "stay", "hospedaje", "dorm"]) and not any(r["id"] == "biz_city_lights" for r in recs):
                cl = conn.execute("SELECT id, trading_name, slug, logo_url, cover_image_url, hours_json FROM businesses WHERE id = 'biz_city_lights'").fetchone()
                if cl:
                    recs.insert(0, dict(cl))

            # Determine direct target business before stripping internal scoring keys
            target_biz = None
            if scored and scored[0].get("_direct"):
                target_biz = scored[0]
            elif context_biz and (not scored or scored[0]["slug"] == context_biz["slug"]):
                target_biz = context_biz

            # Clean internal scoring keys before JSON serialization
            for r in recs:
                r.pop("_score", None)
                r.pop("_direct", None)
                r.pop("primary_location_id", None)
            if target_biz:
                target_biz.pop("_score", None)
                target_biz.pop("_direct", None)
                target_biz.pop("primary_location_id", None)

            asks_hours = any(k in tokens for k in ["hour", "hours", "open", "opens", "close", "closes", "horario", "horarios", "abierto", "abren", "cierran", "heure", "heures", "horaire", "horaires", "ouvert"])
            asks_prices = any(k in tokens for k in ["price", "prices", "cost", "costs", "service", "services", "menu", "precio", "precios", "servicio", "servicios", "tarifa", "tarifas", "prix", "tarif", "tarifs"])
            asks_location = any(k in tokens for k in ["where", "location", "address", "area", "areas", "donde", "ubicacion", "zona", "ou", "adresse", "zone"])

            if target_biz and asks_hours:
                hours_str = self._format_hours_dict(target_biz.get("hours_json") or "", lang)
                if hours_str:
                    if target_biz not in recs:
                        recs = [target_biz] + [r for r in recs if r["id"] != target_biz["id"]][:3]
                    if is_es:
                        ans = f"Horario de {target_biz['trading_name']}: {hours_str}."
                    elif is_fr:
                        ans = f"Horaires de {target_biz['trading_name']} : {hours_str}."
                    else:
                        ans = f"{target_biz['trading_name']} hours: {hours_str}."
                    return {"query": query, "answer": ans, "recommendations": recs}

            if target_biz and asks_prices:
                srvs = srv_by_biz.get(target_biz["id"], [])
                if srvs:
                    if target_biz not in recs:
                        recs = [target_biz] + [r for r in recs if r["id"] != target_biz["id"]][:3]
                    sample = []
                    for s in srvs[:5]:
                        sn = s["name_es"] if is_es else s["name_en"]
                        sp = f"{s['currency']} ${int(s['price']) if float(s['price']).is_integer() else s['price']}" if s.get("display_price") and s.get("price") else ("Consultar precio" if is_es else ("Prix sur demande" if is_fr else "Contact for price"))
                        sample.append(f"{sn} ({sp})")
                    joined = ", ".join(sample)
                    if is_es:
                        ans = f"Servicios principales de {target_biz['trading_name']}: {joined}."
                    elif is_fr:
                        ans = f"Principaux services de {target_biz['trading_name']} : {joined}."
                    else:
                        ans = f"Featured services at {target_biz['trading_name']}: {joined}."
                    return {"query": query, "answer": ans, "recommendations": recs}

            if target_biz and asks_location:
                areas = areas_by_biz.get(target_biz["id"], [])
                area_str = ", ".join(areas) if areas else (target_biz.get("location") or "")
                if area_str:
                    if target_biz not in recs:
                        recs = [target_biz] + [r for r in recs if r["id"] != target_biz["id"]][:3]
                    if is_es:
                        ans = f"{target_biz['trading_name']} atiende en: {area_str}."
                    elif is_fr:
                        ans = f"{target_biz['trading_name']} dessert : {area_str}."
                    else:
                        ans = f"{target_biz['trading_name']} serves: {area_str}."
                    return {"query": query, "answer": ans, "recommendations": recs}

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
                "vida nocturna": {
                    "en": "Pedro Clisante street in Sosua for bars; Cabarete beach for beachfront lounges and dancing under the stars.",
                    "es": "Calle Pedro Clisante en Sosúa para bares y terrazas; la playa de Cabarete para bailar sobre la arena frente al mar."
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

            extra_info = ""
            for key, info_dict in regional_knowledge.items():
                if key in norm_query:
                    extra_info = info_dict.get(lang, info_dict["en"])
                    break

            if recs:
                if is_es:
                    ans = f"Encontré opciones registradas en Mavunqo para su búsqueda: {', '.join(r['trading_name'] for r in recs)}."
                elif is_fr:
                    ans = f"Voici les options vérifiées sur Mavunqo : {', '.join(r['trading_name'] for r in recs)}."
                else:
                    ans = f"Here are verified options on Mavunqo: {', '.join(r['trading_name'] for r in recs)}."

                if extra_info:
                    ans += f"\n\n💡 Local guide note: {extra_info}"
            else:
                if extra_info:
                    ans = extra_info
                else:
                    if is_es:
                        ans = "Para esa búsqueda en Sosúa y la Costa Norte, le recomendamos explorar los comercios gastronómicos y de servicios en nuestro directorio, o consultar con nuestro equipo de asistencia local en la recepción de City Lights o soporte de Mavunqo."
                    elif is_fr:
                        ans = "Pour cette recherche à Sosúa et sur la Côte Nord, explorez nos commerces vérifiés dans l'annuaire Mavunqo ou contactez notre assistance WhatsApp."
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
            rain_mode_active = bool(settings["rain_mode_active"]) if settings and "rain_mode_active" in settings.keys() else False
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

            base_del_fee = self._get_setting_float(conn, "delivery_fee_dop", 100.0)
            rain_fee = self._get_setting_float(conn, "rain_hazard_fee_dop", 50.0)
            return {
                "location_id": location_id,
                "delivery_available": delivery_available,
                "pickup_always_available": True,
                "active_drivers_count": online_driver_count,
                "active_delivery_orders": active_deliveries,
                "total_delivery_capacity": total_capacity,
                "reason": status_reason,
                "override_active": override_active,
                "rain_mode_active": rain_mode_active,
                "delivery_fee": base_del_fee + (rain_fee if rain_mode_active else 0.0)
            }

    def set_rain_mode(self, user_id: str, location_id: str, rain_mode_active: bool):
        with self.get_connection() as conn:
            disp_user = conn.execute("SELECT id, role FROM users WHERE id = ?", (user_id,)).fetchone()
            if not disp_user or disp_user["role"] not in ("admin", "manager", "staff"):
                raise PermissionError("Access denied: Mavunqo dispatcher role required.")

            existing = conn.execute(
                "SELECT location_id FROM delivery_capacity_settings WHERE location_id = ?",
                (location_id,)
            ).fetchone()
            if existing:
                conn.execute(
                    """UPDATE delivery_capacity_settings
                       SET rain_mode_active = ?, updated_at = CURRENT_TIMESTAMP
                       WHERE location_id = ?""",
                    (1 if rain_mode_active else 0, location_id)
                )
            else:
                conn.execute(
                    """INSERT INTO delivery_capacity_settings (location_id, rain_mode_active)
                       VALUES (?, ?)""",
                    (location_id, 1 if rain_mode_active else 0)
                )
            conn.commit()
        return {
            "success": True,
            "location_id": location_id,
            "rain_mode_active": bool(rain_mode_active),
            "delivery_fee": 150.0 if rain_mode_active else 100.0
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

            promo_opt_in = bool(payload.get("promo_opt_in", True))
            promo_longterm_opt_in = bool(payload.get("promo_longterm_opt_in", False))
            conn.execute(
                """INSERT INTO promo_preferences (
                       phone, customer_name, promo_opt_in, promo_longterm_opt_in,
                       last_location_id, in_service_area, booked_for_at, last_source_type,
                       last_order_at, updated_at
                   )
                   VALUES (?, ?, ?, ?, ?, 1, ?, 'booking', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                   ON CONFLICT(phone) DO UPDATE SET
                     customer_name = excluded.customer_name,
                     promo_opt_in = excluded.promo_opt_in,
                     promo_longterm_opt_in = CASE WHEN excluded.promo_longterm_opt_in = 1 THEN 1 ELSE promo_preferences.promo_longterm_opt_in END,
                     last_location_id = COALESCE(excluded.last_location_id, promo_preferences.last_location_id),
                     in_service_area = 1,
                     booked_for_at = COALESCE(excluded.booked_for_at, promo_preferences.booked_for_at),
                     last_source_type = 'booking',
                     last_order_at = CURRENT_TIMESTAMP,
                     updated_at = CURRENT_TIMESTAMP""",
                (
                    cust_phone, cust_name, 1 if promo_opt_in else 0, 1 if promo_longterm_opt_in else 0,
                    biz["primary_location_id"], req_time_dt.isoformat() if req_time_dt else None
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

            # Strict Mid-Shift Cash Cap Check (RD$ 3,000 maximum unreconciled cash in hand)
            unsettled_cash = conn.execute("""
                SELECT COALESCE(SUM(amount_collected), 0.0) as unreconciled_total
                FROM cash_collections cc
                JOIN orders o ON cc.order_id = o.id
                WHERE cc.driver_id = ? AND (o.cash_reconciled = 0 OR o.cash_reconciled IS NULL)
            """, (driver_id,)).fetchone()
            
            current_float = float(unsettled_cash["unreconciled_total"]) if unsettled_cash else 0.0
            MAX_DRIVER_CASH_FLOAT = self._get_setting_float(conn, "max_driver_cash_float_dop", 3000.0)
            
            if current_float >= MAX_DRIVER_CASH_FLOAT:
                raise ValueError(
                    f"Driver cash limit reached! Driver {driver['full_name']} currently holds "
                    f"RD$ {current_float:.2f} in unreconciled cash (Cap is RD$ {MAX_DRIVER_CASH_FLOAT:.2f}). "
                    f"A cash drop or settlement at Central Dispatch is required before assigning new jobs."
                )

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

    def _calculate_distance_delivery_fee(self, conn, business_id: str, dest_lat, dest_lng, base_fee: float) -> float:
        """Tiered distance-based delivery fee: <=3km flat base_fee (100 DOP), >3km adds 25 DOP/km."""
        if dest_lat is None or dest_lng is None:
            return base_fee
        try:
            d_lat = float(dest_lat)
            d_lng = float(dest_lng)
        except (TypeError, ValueError):
            return base_fee
        row = conn.execute(
            "SELECT pickup_pin_lat, pickup_pin_lng, storefront_pin_lat, storefront_pin_lng FROM businesses WHERE id = ?",
            (business_id,)
        ).fetchone()
        if not row:
            return base_fee
        p_lat = row["pickup_pin_lat"] or row["storefront_pin_lat"]
        p_lng = row["pickup_pin_lng"] or row["storefront_pin_lng"]
        if p_lat is None or p_lng is None:
            return base_fee
        import math
        r_km = 6371.0
        phi1, phi2 = math.radians(float(p_lat)), math.radians(d_lat)
        dphi = math.radians(d_lat - float(p_lat))
        dlambda = math.radians(d_lng - float(p_lng))
        a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
        km = 2 * r_km * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        if km <= 3.0:
            return base_fee
        extra_km = math.ceil(km - 3.0)
        return round(base_fee + (extra_km * 25.0), 2)

    def get_driver_active_jobs(self, driver_id: str):
        with self.get_connection() as conn:
            rows = conn.execute("""
                SELECT o.id as order_id, o.order_number, o.customer_name, o.customer_phone, o.total, o.currency,
                       o.payment_method, o.driver_tip, o.cash_due, o.status as order_status, d.status as dispatch_status,
                       b.trading_name as business_name, b.pickup_pin_lat, b.pickup_pin_lng, b.pickup_pin_note, b.address as business_address,
                       o.delivery_address,
                       COALESCE(o.delivery_pin_lat, r.destination_lat) as destination_lat,
                       COALESCE(o.delivery_pin_lng, r.destination_lng) as destination_lng,
                       r.destination_entrance_note
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
                # Build travel-ordered stops with customer PII redacted for driver privacy
                p_lat = j.get("pickup_pin_lat") or 19.755
                p_lng = j.get("pickup_pin_lng") or -70.515
                d_lat = j.get("destination_lat") or 19.758
                d_lng = j.get("destination_lng") or -70.510

                raw_name = (j.get("customer_name") or "Customer").strip()
                parts = raw_name.split()
                display_name = f"{parts[0]} {parts[1][0]}." if len(parts) > 1 else raw_name
                entrance_note = j.get("destination_entrance_note") or "Use Google Maps pin (contact via Mavunqo Dispatch)"

                j["customer_display_name"] = display_name
                j["customer_name"] = display_name
                j["customer_phone"] = "Protected (Mavunqo Dispatch)"
                j["delivery_address"] = entrance_note
                j["entrance_note"] = entrance_note

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
                        "title": f"2. Deliver to {display_name}",
                        "lat": d_lat,
                        "lng": d_lng,
                        "entrance_note": entrance_note,
                        "amount_due": f"{j['cash_due'] or j['total']} {j['currency']}",
                        "directions_url": f"https://www.google.com/maps/dir/?api=1&destination={d_lat},{d_lng}"
                    }
                ]
                jobs.append(j)
            return jobs

    def verify_driver_pin(self, driver_id: str, pin_code: str):
        with self.get_connection() as conn:
            driver = conn.execute(
                "SELECT id, full_name, phone, pin_code FROM drivers WHERE id = ?",
                (driver_id,)
            ).fetchone()
            if not driver:
                raise ValueError("Driver not found.")
            expected_pin = driver["pin_code"] or "1234"
            if str(pin_code or "").strip() != str(expected_pin):
                raise PermissionError("Invalid driver PIN.")
            return {"success": True, "driver_id": driver["id"], "full_name": driver["full_name"], "phone": driver["phone"]}

    def record_driver_cash_collection(self, order_id: str, driver_id: str, amount_collected: float, notes: str = None, pin_code: str = None):
        with self.get_connection() as conn:
            if pin_code is not None:
                driver = conn.execute("SELECT pin_code FROM drivers WHERE id = ?", (driver_id,)).fetchone()
                if not driver or str(pin_code).strip() != str(driver["pin_code"] or "1234"):
                    raise PermissionError("Invalid driver PIN.")
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

    def _get_setting_float(self, conn, key: str, default: float) -> float:
        try:
            row = conn.execute("SELECT value FROM platform_settings WHERE key = ?", (key,)).fetchone()
            if row and row["value"] is not None:
                return float(row["value"])
        except Exception:
            pass
        return float(default)

    def get_platform_settings(self):
        from .tokens_and_attribution import STANDARD_COMMISSION_RATE
        defaults = {
            "standard_commission_rate": STANDARD_COMMISSION_RATE,
            "delivery_fee_dop": 100.0,
            "rain_hazard_fee_dop": 50.0,
            "max_driver_cash_float_dop": 3000.0,
            "dop_to_usd_rate": 60.0,
        }
        with self.get_connection() as conn:
            result = {k: self._get_setting_float(conn, k, v) for k, v in defaults.items()}
            biz_rows = conn.execute(
                """SELECT id, trading_name, slug, category_id, custom_commission_rate, status
                   FROM businesses
                   ORDER BY trading_name ASC"""
            ).fetchall()
            result["businesses"] = [dict(b) for b in biz_rows]
        return result

    def update_platform_settings(self, admin_id: str, updates: dict):
        with self.get_connection() as conn:
            u = conn.execute("SELECT role FROM users WHERE id = ?", (admin_id,)).fetchone()
            if not u or u["role"] != "admin":
                raise PermissionError("Admin role required to update platform settings.")

            allowed = {
                "standard_commission_rate": (0.0, 0.50),
                "delivery_fee_dop": (0.0, 2000.0),
                "rain_hazard_fee_dop": (0.0, 1000.0),
                "max_driver_cash_float_dop": (500.0, 50000.0),
                "dop_to_usd_rate": (30.0, 120.0),
            }
            for k, (min_v, max_v) in allowed.items():
                if k in updates and updates[k] is not None and updates[k] != "":
                    val = float(updates[k])
                    if val < min_v or val > max_v:
                        raise ValueError(f"{k} must be between {min_v} and {max_v}.")
                    conn.execute(
                        """INSERT INTO platform_settings (key, value, updated_at)
                           VALUES (?, ?, CURRENT_TIMESTAMP)
                           ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = CURRENT_TIMESTAMP""",
                        (k, str(val))
                    )
            conn.commit()
        return self.get_platform_settings()

    def set_business_commission_rate(self, admin_id: str, business_id: str, custom_rate):
        with self.get_connection() as conn:
            u = conn.execute("SELECT role FROM users WHERE id = ?", (admin_id,)).fetchone()
            if not u or u["role"] != "admin":
                raise PermissionError("Admin role required to set business commission rate.")

            biz = conn.execute("SELECT id, trading_name FROM businesses WHERE id = ?", (business_id,)).fetchone()
            if not biz:
                raise ValueError("Business not found.")

            if custom_rate is None or custom_rate == "":
                rate_val = None
            else:
                rate_val = float(custom_rate)
                if rate_val < 0.0 or rate_val > 0.50:
                    raise ValueError("Commission rate must be between 0.0 (0%) and 0.50 (50%).")

            conn.execute(
                "UPDATE businesses SET custom_commission_rate = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (rate_val, business_id)
            )
            conn.commit()
        return {"success": True, "business_id": business_id, "trading_name": biz["trading_name"], "custom_commission_rate": rate_val}

    def update_promo_preference_by_token(self, status_token: str, promo_opt_in: bool, promo_longterm_opt_in: bool = False):
        with self.get_connection() as conn:
            order = conn.execute(
                "SELECT id, customer_name, customer_phone FROM orders WHERE status_token = ?",
                (status_token,)
            ).fetchone()
            if not order:
                raise ValueError("Invalid order token.")
            conn.execute(
                """UPDATE orders
                   SET promo_opt_in = ?, promo_longterm_opt_in = ?, updated_at = CURRENT_TIMESTAMP
                   WHERE id = ?""",
                (1 if promo_opt_in else 0, 1 if promo_longterm_opt_in else 0, order["id"])
            )
            conn.execute(
                """INSERT INTO promo_preferences (phone, customer_name, promo_opt_in, promo_longterm_opt_in, updated_at)
                   VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
                   ON CONFLICT(phone) DO UPDATE SET
                     promo_opt_in = excluded.promo_opt_in,
                     promo_longterm_opt_in = excluded.promo_longterm_opt_in,
                     updated_at = CURRENT_TIMESTAMP""",
                (order["customer_phone"], order["customer_name"], 1 if promo_opt_in else 0, 1 if promo_longterm_opt_in else 0)
            )
            conn.commit()
        return {
            "success": True,
            "promo_opt_in": bool(promo_opt_in),
            "promo_longterm_opt_in": bool(promo_longterm_opt_in)
        }

    def update_promo_location_checkin(self, phone: str = None, status_token: str = None,
                                      location_id: str = None, in_service_area: bool = True):
        with self.get_connection() as conn:
            target_phone = (phone or "").strip()
            if not target_phone and status_token:
                ord_row = conn.execute(
                    "SELECT customer_phone FROM orders WHERE status_token = ?",
                    (status_token,)
                ).fetchone()
                if ord_row:
                    target_phone = ord_row["customer_phone"]
            if not target_phone:
                raise ValueError("Phone or valid order token is required.")

            row = conn.execute(
                "SELECT phone, promo_opt_in FROM promo_preferences WHERE phone = ?",
                (target_phone,)
            ).fetchone()
            if not row:
                conn.execute(
                    """INSERT INTO promo_preferences (phone, promo_opt_in, promo_longterm_opt_in, last_location_id, in_service_area, last_order_at, updated_at)
                       VALUES (?, 1, 0, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)""",
                    (target_phone, location_id, 1 if in_service_area else 0)
                )
            else:
                conn.execute(
                    """UPDATE promo_preferences
                       SET last_location_id = COALESCE(?, last_location_id),
                           in_service_area = ?,
                           last_order_at = CASE WHEN ? = 1 AND promo_opt_in = 1 THEN CURRENT_TIMESTAMP ELSE last_order_at END,
                           updated_at = CURRENT_TIMESTAMP
                       WHERE phone = ?""",
                    (location_id, 1 if in_service_area else 0, 1 if in_service_area else 0, target_phone)
                )
            conn.commit()
        return {
            "success": True,
            "phone": target_phone,
            "last_location_id": location_id,
            "in_service_area": bool(in_service_area),
        }

    def get_promo_audience(self, admin_id: str, window_days: int = 14,
                           business_id: str = None, location_id: str = None):
        with self.get_connection() as conn:
            u = conn.execute("SELECT role FROM users WHERE id = ?", (admin_id,)).fetchone()
            if not u or u["role"] != "admin":
                raise PermissionError("Admin role required.")

            reach_mode = "all_areas"
            covered_locations = None  # None means all areas

            if business_id:
                biz = conn.execute(
                    "SELECT id, trading_name, primary_location_id, serves_entire_area FROM businesses WHERE id = ?",
                    (business_id,)
                ).fetchone()
                if not biz:
                    raise ValueError("Business not found.")
                if biz["serves_entire_area"]:
                    reach_mode = "serves_entire_area"
                    covered_locations = None
                else:
                    reach_mode = "local_coverage"
                    area_rows = conn.execute(
                        "SELECT location_id FROM business_service_areas WHERE business_id = ?",
                        (business_id,)
                    ).fetchall()
                    locs = {biz["primary_location_id"]}
                    for ar in area_rows:
                        locs.add(ar["location_id"])
                    covered_locations = sorted(locs)
            elif location_id:
                reach_mode = "location_filter"
                covered_locations = [location_id]

            loc_clause = ""
            loc_params = []
            if covered_locations is not None:
                placeholders = ",".join("?" for _ in covered_locations)
                loc_clause = f" AND last_location_id IN ({placeholders})"
                loc_params = list(covered_locations)

            win_arg = f"-{int(window_days)} days"
            active_in_town = conn.execute(
                f"""SELECT phone, customer_name, promo_opt_in, promo_longterm_opt_in,
                           last_location_id, in_service_area, booked_for_at, last_source_type, last_order_at
                    FROM promo_preferences
                    WHERE promo_opt_in = 1
                      AND COALESCE(in_service_area, 1) = 1
                      AND (
                        datetime(last_order_at) >= datetime('now', ?)
                        OR (
                          booked_for_at IS NOT NULL
                          AND datetime(booked_for_at) BETWEEN datetime('now', ?) AND datetime('now', '+2 days')
                        )
                      ){loc_clause}
                    ORDER BY last_order_at DESC""",
                [win_arg, win_arg] + loc_params
            ).fetchall()
            longterm_list = conn.execute(
                f"""SELECT phone, customer_name, promo_opt_in, promo_longterm_opt_in,
                           last_location_id, in_service_area, booked_for_at, last_source_type, last_order_at
                    FROM promo_preferences
                    WHERE promo_opt_in = 1
                      AND COALESCE(in_service_area, 1) = 1
                      AND promo_longterm_opt_in = 1{loc_clause}
                    ORDER BY last_order_at DESC""",
                loc_params
            ).fetchall()
        return {
            "window_days": int(window_days),
            "business_id": business_id,
            "reach_mode": reach_mode,
            "covered_locations": covered_locations,
            "active_in_town_count": len(active_in_town),
            "active_in_town": [dict(r) for r in active_in_town],
            "longterm_count": len(longterm_list),
            "longterm": [dict(r) for r in longterm_list],
        }

    def get_merchant_clearinghouse_settlements(self):
        """
        Calculates accumulated cash settlements owed to merchants for orders
        where cash has been collected/completed, subtracting Mavunqo platform commission.
        Grouped by business.
        """
        with self.get_connection() as conn:
            # Query completed orders with fee records that haven't been settled yet
            query = """
                SELECT 
                    b.id as business_id,
                    b.trading_name,
                    b.slug,
                    b.phone,
                    b.address,
                    o.id as order_id,
                    o.order_number,
                    o.subtotal,
                    o.total,
                    o.currency,
                    o.created_at,
                    f.commission_rate,
                    f.fee_amount as commission_amount,
                    f.status as fee_status
                FROM orders o
                JOIN businesses b ON o.business_id = b.id
                LEFT JOIN fee_records f ON o.id = f.order_id
                WHERE o.status = 'completed'
                  AND o.id NOT IN (
                      SELECT json_each.value 
                      FROM merchant_payouts mp, json_each(mp.order_ids_json)
                      WHERE mp.status = 'settled'
                  )
                ORDER BY b.trading_name ASC, o.created_at ASC
            """
            rows = conn.execute(query).fetchall()

            # Group by merchant
            merchants = {}
            for r in rows:
                biz_id = r["business_id"]
                if biz_id not in merchants:
                    merchants[biz_id] = {
                        "business_id": biz_id,
                        "trading_name": r["trading_name"],
                        "slug": r["slug"],
                        "phone": r["phone"],
                        "address": r["address"],
                        "pending_orders": [],
                        "gross_sales": 0.0,
                        "commission_retained": 0.0,
                        "net_payout_due": 0.0,
                        "currency": r["currency"] or "DOP"
                    }
                
                subtotal = float(r["subtotal"] or 0.0)
                comm = float(r["commission_amount"] or 0.0)
                # If fee record wasn't generated or fee is 0, compute fallback based on 10%
                if comm <= 0.0 and subtotal > 0.0:
                    comm = round(subtotal * 0.10, 2)
                
                net = max(0.0, subtotal - comm)

                merchants[biz_id]["gross_sales"] += subtotal
                merchants[biz_id]["commission_retained"] += comm
                merchants[biz_id]["net_payout_due"] += net
                merchants[biz_id]["pending_orders"].append({
                    "order_id": r["order_id"],
                    "order_number": r["order_number"],
                    "subtotal": subtotal,
                    "commission": comm,
                    "net": net,
                    "created_at": r["created_at"]
                })

            # Round amounts
            merchant_list = list(merchants.values())
            for m in merchant_list:
                m["gross_sales"] = round(m["gross_sales"], 2)
                m["commission_retained"] = round(m["commission_retained"], 2)
                m["net_payout_due"] = round(m["net_payout_due"], 2)

            # Fetch recent settled payouts
            settled_rows = conn.execute("""
                SELECT mp.*, b.trading_name, u.full_name as settled_by_name
                FROM merchant_payouts mp
                JOIN businesses b ON mp.business_id = b.id
                LEFT JOIN users u ON mp.settled_by = u.id
                ORDER BY mp.created_at DESC
                LIMIT 20
            """).fetchall()

            return {
                "merchants": merchant_list,
                "recent_payouts": [dict(sr) for sr in settled_rows]
            }

    def record_merchant_cash_settlement(self, business_id: str, dispatcher_id: str, order_ids: list, payout_method: str = "cash_envelope", notes: str = None):
        """
        Records the physical cash envelope handoff from Mavunqo Central Dispatch to merchant owner.
        """
        now_utc = datetime.now(timezone.utc).isoformat()
        batch_id = f"pay_{uuid.uuid4().hex[:12]}"

        with self.get_connection() as conn:
            # Check dispatcher authorization
            disp_user = conn.execute("SELECT role FROM users WHERE id = ?", (dispatcher_id,)).fetchone()
            if not disp_user or disp_user["role"] not in ("admin", "manager", "staff"):
                raise PermissionError("Access denied: Mavunqo dispatcher role required.")

            biz = conn.execute("SELECT * FROM businesses WHERE id = ?", (business_id,)).fetchone()
            if not biz:
                raise ValueError("Merchant business not found.")

            if not order_ids:
                raise ValueError("No order IDs provided for settlement.")

            # Calculate gross and commission for these orders
            placeholders = ",".join(["?"] * len(order_ids))
            orders_data = conn.execute(f"""
                SELECT o.id, o.subtotal, COALESCE(f.fee_amount, o.subtotal * 0.10) as fee
                FROM orders o
                LEFT JOIN fee_records f ON o.id = f.order_id
                WHERE o.id IN ({placeholders}) AND o.business_id = ?
            """, (*order_ids, business_id)).fetchall()

            if not orders_data:
                raise ValueError("No matching eligible orders found for this merchant.")

            gross_subtotal = sum(float(od["subtotal"]) for od in orders_data)
            commission_retained = sum(float(od["fee"]) for od in orders_data)
            net_payout = max(0.0, gross_subtotal - commission_retained)

            payout_id = str(uuid.uuid4())
            conn.execute("""
                INSERT INTO merchant_payouts (
                    id, payout_batch_id, business_id, order_ids_json,
                    gross_subtotal, commission_retained, net_payout_amount, currency,
                    status, settled_by, settled_at, payout_method, notes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, 'DOP', 'settled', ?, ?, ?, ?)
            """, (
                payout_id, batch_id, business_id, json.dumps(order_ids),
                gross_subtotal, commission_retained, net_payout,
                dispatcher_id, now_utc, payout_method, notes
            ))

            # Mark fee_records as reconciled
            conn.execute(f"""
                UPDATE fee_records
                SET status = 'reconciled', updated_at = ?
                WHERE order_id IN ({placeholders})
            """, (now_utc, *order_ids))

            conn.commit()

        return {
            "success": True,
            "payout_batch_id": batch_id,
            "business_id": business_id,
            "business_name": biz["trading_name"],
            "orders_count": len(order_ids),
            "gross_subtotal": round(gross_subtotal, 2),
            "commission_retained": round(commission_retained, 2),
            "net_payout_amount": round(net_payout, 2),
            "settled_at": now_utc
        }

    # --- WELLNESS APPOINTMENT & TRAVEL-BUFFER SCHEDULING ---
    def get_wellness_travel_buffer_minutes(self, origin_location_id: str, dest_location_id: str, service_mode: str = "mobile_visit") -> int:
        """Returns required turnaround + travel buffer in minutes between appointments."""
        if service_mode == "in_shop":
            return 15
        if not origin_location_id or not dest_location_id or origin_location_id == dest_location_id:
            return 30
        pair = {origin_location_id, dest_location_id}
        if pair == {"loc_puerto_plata", "loc_montellano"} or pair == {"loc_montellano", "loc_sosua"}:
            return 45
        return 60

    def book_wellness_appointment(self, business_id: str, service_name: str, customer_name: str,
                                  customer_phone: str, start_at: str, end_at: str,
                                  location_id: str = "loc_puerto_plata", service_mode: str = "mobile_visit",
                                  price: float = 0.0, service_id: str = None, notes: str = None):
        """Books a wellness appointment while enforcing travel buffers and external availability blocks."""
        from datetime import datetime, timedelta
        start_dt = datetime.fromisoformat(start_at)
        end_dt = datetime.fromisoformat(end_at)
        if end_dt <= start_dt:
            raise ValueError("Appointment end_at must be after start_at.")

        with self.get_connection() as conn:
            biz = conn.execute(
                "SELECT id, primary_location_id, custom_commission_rate FROM businesses WHERE id = ? AND status = 'approved'",
                (business_id,)
            ).fetchone()
            if not biz:
                raise ValueError("Approved wellness business not found.")

            buffer_min = self.get_wellness_travel_buffer_minutes(biz["primary_location_id"], location_id, service_mode)
            padded_start = (start_dt - timedelta(minutes=buffer_min)).strftime("%Y-%m-%dT%H:%M")
            padded_end = (end_dt + timedelta(minutes=buffer_min)).strftime("%Y-%m-%dT%H:%M")

            conflict = conn.execute("""
                SELECT id, start_at, end_at FROM appointments
                WHERE business_id = ? AND status IN ('pending', 'confirmed')
                  AND start_at < ? AND end_at > ?
                LIMIT 1
            """, (business_id, padded_end, padded_start)).fetchone()
            if conflict:
                raise ValueError("Selected time overlaps an existing booking or required travel buffer.")

            blocked = conn.execute("""
                SELECT id FROM provider_availability
                WHERE business_id = ? AND block_start < ? AND block_end > ?
                LIMIT 1
            """, (business_id, end_at, start_at)).fetchone()
            if blocked:
                raise ValueError("Provider is unavailable during this time block.")

            appt_id = f"appt_{uuid.uuid4().hex[:12]}"
            appt_code = f"WL-{uuid.uuid4().hex[:6].upper()}"
            comm_rate = float(biz["custom_commission_rate"] or 0.10)
            conn.execute("""
                INSERT INTO appointments (
                    id, appointment_code, business_id, service_id, service_name, service_mode,
                    location_id, customer_name, customer_phone, start_at, end_at,
                    travel_buffer_min, price, currency, commission_rate, status, notes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'DOP', ?, 'confirmed', ?)
            """, (
                appt_id, appt_code, business_id, service_id, service_name, service_mode,
                location_id, customer_name, customer_phone, start_at, end_at,
                buffer_min, float(price or 0.0), comm_rate, notes
            ))
            conn.commit()

        return {
            "id": appt_id,
            "appointment_code": appt_code,
            "business_id": business_id,
            "start_at": start_at,
            "end_at": end_at,
            "travel_buffer_min": buffer_min,
            "commission_rate": comm_rate,
            "status": "confirmed"
        }

    # --- MONTHLY SAAS PLANS & SUBSCRIPTIONS ---
    def list_saas_plans(self):
        with self.get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM saas_plans WHERE is_active = 1 ORDER BY sort_order ASC"
            ).fetchall()
            out = []
            for r in rows:
                item = dict(r)
                try:
                    item["features"] = json.loads(item.get("features_json") or "[]")
                except Exception:
                    item["features"] = []
                out.append(item)
            return out

    def assign_business_subscription(self, business_id: str, plan_code: str, billing_currency: str = "DOP", status: str = "trial"):
        with self.get_connection() as conn:
            plan = conn.execute("SELECT id, code, commission_rate FROM saas_plans WHERE code = ?", (plan_code,)).fetchone()
            if not plan:
                raise ValueError(f"Plan '{plan_code}' not found.")
            sub_id = f"sub_{uuid.uuid4().hex[:12]}"
            conn.execute(
                """INSERT INTO business_subscriptions (id, business_id, plan_id, status, billing_currency)
                   VALUES (?, ?, ?, ?, ?)""",
                (sub_id, business_id, plan["id"], status, billing_currency)
            )
            conn.commit()
            return {"subscription_id": sub_id, "business_id": business_id, "plan_code": plan["code"], "status": status}

    def get_business_subscription(self, user_id: str, business_id: str):
        with self.get_connection() as conn:
            biz = conn.execute("SELECT owner_id FROM businesses WHERE id = ?", (business_id,)).fetchone()
            if not biz:
                raise ValueError("Business not found.")
            if biz["owner_id"] != user_id:
                raise PermissionError("Forbidden: you do not own this business.")
            row = conn.execute(
                """SELECT s.id, s.status, s.billing_currency, s.started_at, p.code, p.name_en, p.name_es,
                          p.monthly_price_usd, p.monthly_price_dop, p.commission_rate
                   FROM business_subscriptions s
                   JOIN saas_plans p ON s.plan_id = p.id
                   WHERE s.business_id = ?
                   ORDER BY s.rowid DESC LIMIT 1""",
                (business_id,)
            ).fetchone()
            return dict(row) if row else None

    def subscribe_owner_business(self, user_id: str, business_id: str, plan_code: str, billing_currency: str = "DOP"):
        with self.get_connection() as conn:
            biz = conn.execute("SELECT owner_id FROM businesses WHERE id = ?", (business_id,)).fetchone()
            if not biz:
                raise ValueError("Business not found.")
            if biz["owner_id"] != user_id:
                raise PermissionError("Forbidden: you do not own this business.")
        status = "active" if plan_code == "free_basic" else "trial"
        return self.assign_business_subscription(business_id, plan_code, billing_currency, status)

    def create_sales_rep(self, full_name: str, phone: str = "", email: str = "",
                         commission_share_rate: float = 0.25, rep_code: str = None):
        clean_name = (full_name or "").strip()
        if not clean_name:
            raise ValueError("Sales rep full name is required.")
        rate = float(commission_share_rate)
        if rate <= 0 or rate > 0.5:
            raise ValueError("Commission share rate must be between 0.01 and 0.50.")
        code = (rep_code or re.sub(r'[^A-Z0-9]+', '', clean_name.upper())[:6] or "REP")
        rep_id = f"rep_{uuid.uuid4().hex[:10]}"
        with self.get_connection() as conn:
            existing = conn.execute("SELECT id FROM sales_reps WHERE rep_code = ?", (code,)).fetchone()
            if existing:
                code = f"{code}_{uuid.uuid4().hex[:4].upper()}"
            conn.execute(
                """INSERT INTO sales_reps (id, rep_code, full_name, phone, email, commission_share_rate)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (rep_id, code, clean_name, (phone or "").strip() or None, (email or "").strip() or None, rate)
            )
            conn.commit()
        return {"id": rep_id, "rep_code": code, "full_name": clean_name, "commission_share_rate": rate}

    def list_sales_rep_payouts(self):
        with self.get_connection() as conn:
            reps = conn.execute("SELECT * FROM sales_reps ORDER BY created_at DESC").fetchall()
            out = []
            for r in reps:
                rep = dict(r)
                referred = conn.execute(
                    """SELECT b.id, b.trading_name, b.status,
                              COALESCE(SUM(CASE WHEN o.status IN ('delivered', 'completed') THEN o.platform_fee_amount ELSE 0 END), 0) AS collected_order_fees
                       FROM businesses b
                       LEFT JOIN orders o ON o.business_id = b.id
                       WHERE b.referred_by_rep_code = ?
                       GROUP BY b.id""",
                    (rep["rep_code"],)
                ).fetchall()
                total_fees = sum(float(row["collected_order_fees"] or 0.0) for row in referred)
                rep["referred_businesses"] = [dict(row) for row in referred]
                rep["referred_count"] = len(referred)
                rep["total_collected_platform_fees"] = round(total_fees, 2)
                rep["estimated_rep_payout"] = round(total_fees * float(rep["commission_share_rate"]), 2)
                out.append(rep)
            return out


