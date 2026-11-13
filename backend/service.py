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
            commission_rate = 0.12 if order_origin == "mavunqo" else 0.00
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
                """SELECT o.*, b.trading_name AS business_name, b.phone AS business_phone, b.whatsapp AS business_whatsapp
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

            if "hotel" in query or "room" in query or "stay" in query or "hospedaje" in query or "dorm" in query:
                cl = conn.execute("SELECT id, trading_name, slug FROM businesses WHERE id = 'biz_city_lights'").fetchone()
                if cl and not any(r["id"] == "biz_city_lights" for r in recs):
                    recs.insert(0, dict(cl))

            # Regional Knowledge Base (Knowledge of Sosua, Cabarete, Puerto Plata outside the platform)
            regional_knowledge = {
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
                        ans = "Aunque este comercio no está todavía registrado en el portal Mavunqo, Sosúa y la Costa Norte ofrecen excelentes opciones. Puede explorar el directorio general o solicitar asistencia directa por WhatsApp."
                    else:
                        ans = "While this specific business is not yet on the Mavunqo platform, Sosúa and the North Coast have great local options. You can explore our verified directory or reach out via WhatsApp for a direct local recommendation."

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
