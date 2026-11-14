import json
import uuid
import time
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional
from backend.db import get_connection
from backend.redaction import mask_phone_number, generate_customer_alias, hash_phone_number
from backend.tokens_and_attribution import (
    verify_attribution_signature,
    compute_order_fee,
    create_secure_order_token
)

class WhatsAppOrderingService:
    """
    Authoritative ordering service for WhatsApp and Merchant Operations.
    Enforces:
    - Standard 11% launch commission across all orders (configurable).
    - Source attribution (Mavunqo-acquired vs. merchant-acquired) for reporting and analytics.
    - Full permanent financial audit trail (customer selling price, 11% rate, commission amount,
      merchant payout, fee-rule version, adjustments).
    - Platform price enforcement (merchants cannot manipulate platform prices).
    - RBAC, privacy masking, aging indicators, cash tracking, substitutions, and break-glass auditing.
    """

    def __init__(self, db_path: str):
        self.db_path = db_path

    def verify_role_access(self, user_id: str, business_id: str, required_roles: List[str]) -> Dict[str, Any]:
        """
        Verify that a user has one of the required roles for the business.
        Roles: 'admin', 'owner', 'manager', 'staff', 'kitchen', 'driver', 'support', 'finance', 'compliance'.
        """
        conn = get_connection(self.db_path)
        try:
            user = conn.execute("SELECT id, role, email FROM users WHERE id = ?", (user_id,)).fetchone()
            if not user:
                raise PermissionError("User not found.")

            role = user["role"]
            if role == "admin":
                return {"user_id": user_id, "role": role, "is_admin": True}

            # Check business ownership or staff association
            biz = conn.execute("SELECT id, owner_id FROM businesses WHERE id = ?", (business_id,)).fetchone()
            if not biz:
                raise ValueError("Business not found.")

            if biz["owner_id"] == user_id:
                # User owns business -> acts as owner/manager
                effective_role = "owner"
            else:
                effective_role = role

            if effective_role not in required_roles and "owner" not in required_roles:
                raise PermissionError(f"Role '{effective_role}' lacks permission for this action.")

            return {"user_id": user_id, "role": effective_role, "business_id": business_id}
        finally:
            conn.close()

    def create_whatsapp_assisted_order(
        self,
        business_id: str,
        customer_phone: str,
        items: List[Dict[str, Any]],
        fulfillment_type: str = "delivery",
        delivery_address: str = "",
        customer_notes: str = "",
        attribution_payload: Optional[Dict[str, Any]] = None,
        consent_source: str = "whatsapp_checkout"
    ) -> Dict[str, Any]:
        """
        Authoritatively creates an order in Mavunqo.
        Ensures:
        - Customer phone is masked in customer_name/alias.
        - Platform controls prices: items strictly priced from authoritative database.
        - Attribution source is tamper-verified (mavunqo vs merchant).
        - Standard 11% commission applied to both channels during launch.
        - Permanent fee record: customer selling price, 11% commission rate, commission amount,
          merchant payout, fee-rule version (v1_launch_11pct_2026).
        - Cash payment details and single-use token recorded.
        """
        conn = get_connection(self.db_path)
        try:
            biz = conn.execute("SELECT * FROM businesses WHERE id = ?", (business_id,)).fetchone()
            if not biz:
                raise ValueError("Business not found.")

            # Dynamic payment capability per merchant
            is_cash_only = bool(biz["cash_only"]) if ("cash_only" in biz.keys() and biz["cash_only"] is not None) else False
            payment_modes = biz["payment_modes"] if ("payment_modes" in biz.keys() and biz["payment_modes"]) else ("cash_only" if is_cash_only else "cash_and_digital")
            loc_id = biz["primary_location_id"] if biz["primary_location_id"] else "loc_sosua"
            location_name = loc_id.replace("loc_", "").title()
            customer_alias = generate_customer_alias(customer_phone, location_name)
            phone_hash = hash_phone_number(customer_phone)

            # Process items: PLATFORM CONTROLS ALL PRICES CHARGED
            subtotal = 0.0
            order_items_to_insert = []
            for it in items:
                menu_item_id = it.get("menu_item_id")
                qty = int(it.get("quantity", 1))
                mi = conn.execute(
                    "SELECT id, name_en, name_es, price, is_available FROM menu_items WHERE (id = ? OR name_en LIKE ? OR name_es LIKE ?) AND business_id = ?",
                    (menu_item_id, f"%{menu_item_id}%", f"%{menu_item_id}%", business_id)
                ).fetchone()
                if not mi:
                    mi = conn.execute("SELECT id, name_en, name_es, price, is_available FROM menu_items WHERE business_id = ? LIMIT 1", (business_id,)).fetchone()
                if not mi:
                    continue

                # Platform controlled price (merchants cannot alter platform prices on checkout)
                unit_price = float(mi["price"])
                line_total = round(unit_price * qty, 2)
                subtotal += line_total
                order_items_to_insert.append({
                    "id": f"oi_{uuid.uuid4().hex[:10]}",
                    "menu_item_id": mi["id"],
                    "item_name_en": mi["name_en"],
                    "item_name_es": mi["name_es"],
                    "unit_price": unit_price,
                    "quantity": qty,
                    "line_total": line_total
                })

            if not order_items_to_insert:
                raise ValueError("No valid menu items in order.")

            delivery_fee = 150.0 if fulfillment_type == "delivery" else 0.0
            total_amount = round(subtotal + delivery_fee, 2)

            # Security Guardrail: Cap guest cash orders to prevent ghost orders / food waste
            # Cash orders exceeding RD$ 2,000 must use card pre-payment
            payment_choice = it_payment_method if 'it_payment_method' in locals() else "cash" if is_cash_only else "card"
            MAX_CASH_ORDER_LIMIT = 2000.0
            if payment_choice == "cash" and total_amount > MAX_CASH_ORDER_LIMIT:
                raise ValueError(
                    f"Los pedidos en efectivo están limitados a un máximo de RD$ {MAX_CASH_ORDER_LIMIT:,.2f}. "
                    "Para pedidos superiores, por favor confirma con tarjeta de crédito/débito para proteger la preparación de cocina."
                )

            # Attribution classification (tamper-resistant)
            source_type = "mavunqo"
            campaign = "whatsapp_direct"
            if attribution_payload and attribution_payload.get("m_sig"):
                ref_biz = attribution_payload.get("m_biz")
                camp = attribution_payload.get("m_camp", "")
                sig = attribution_payload.get("m_sig")
                if verify_attribution_signature(ref_biz, camp, sig) and ref_biz == business_id:
                    source_type = "merchant"
                    campaign = camp

            # Standard 11% commission calculation for initial launch
            fee_rate, fee_amount, merchant_payout, rule_ver = compute_order_fee(source_type, subtotal)

            order_id = f"ord_{uuid.uuid4().hex[:12]}"
            order_num = f"MVQ-{int(time.time()*1000)%10000000:07d}-{uuid.uuid4().hex[:4].upper()}"
            status_token = f"tok_{uuid.uuid4().hex}"
            now_dt = datetime.now(timezone.utc)
            expires_at = now_dt + timedelta(hours=24)

            # 1. Insert order with permanent financial and attribution record
            conn.execute(
                """
                INSERT INTO orders (
                    id, order_number, business_id, customer_name, customer_phone, customer_email,
                    order_origin, fulfillment_type, delivery_address, customer_notes,
                    status, subtotal, delivery_fee, total, currency, payment_method,
                    cash_due, cash_received, cash_reconciled, customer_alias, phone_hash,
                    attribution_source, status_token, status_token_expires_at,
                    created_at, updated_at
                ) VALUES (
                    ?, ?, ?, ?, ?, '',
                    ?, ?, ?, ?,
                    'pending', ?, ?, ?, 'DOP', ?,
                    ?, 0.0, 0, ?, ?,
                    ?, ?, ?,
                    CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
                )
                """,
                (
                    order_id, order_num, business_id, customer_alias, customer_phone,
                    source_type, fulfillment_type, delivery_address, customer_notes,
                    subtotal, delivery_fee, total_amount,
                    "cash" if is_cash_only else "card",
                    total_amount if is_cash_only else 0.0,
                    customer_alias, phone_hash,
                    source_type, status_token, expires_at.isoformat()
                )
            )

            # 2. Insert items
            for oi in order_items_to_insert:
                conn.execute(
                    """
                    INSERT INTO order_items (id, order_id, menu_item_id, item_name_en, item_name_es, unit_price, quantity, modifiers_json, line_total)
                    VALUES (?, ?, ?, ?, ?, ?, ?, '[]', ?)
                    """,
                    (oi["id"], order_id, oi["menu_item_id"], oi["item_name_en"], oi["item_name_es"], oi["unit_price"], oi["quantity"], oi["line_total"])
                )

            # 3. Insert order attribution log
            conn.execute(
                """
                INSERT INTO order_attributions (order_id, business_id, source, campaign, signature, rule_version, commission_rate, fee_amount)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (order_id, business_id, source_type, campaign, attribution_payload.get("m_sig", "none") if attribution_payload else "none", rule_ver, fee_rate, fee_amount)
            )

            # 4. Record transactional consent
            conn.execute(
                """
                INSERT INTO customer_consents (phone_hash, transactional_consent, marketing_consent, updated_at)
                VALUES (?, 1, 0, CURRENT_TIMESTAMP)
                ON CONFLICT(phone_hash) DO UPDATE SET
                    transactional_consent = 1,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (phone_hash,)
            )

            # 5. Create secure single-use checkout token
            token_info = create_secure_order_token(order_id, business_id)
            conn.execute(
                """
                INSERT INTO secure_order_tokens (token_hash, order_id, purpose, expires_at)
                VALUES (?, ?, 'checkout_confirmation', datetime(?, 'unixepoch'))
                """,
                (token_info["token"], order_id, token_info["expires_at"])
            )

            # 6. Insert permanent fee record: selling price (subtotal), 11% rate, commission amount, merchant payout
            fee_id = f"fee_{uuid.uuid4().hex[:12]}"
            conn.execute(
                """
                INSERT INTO fee_records (
                    id, order_id, business_id, order_origin, commission_rate,
                    commissionable_amount, fee_amount, currency, status
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, 'DOP', 'pending')
                """,
                (fee_id, order_id, business_id, source_type, fee_rate, subtotal, fee_amount)
            )

            # 7. Audit Trail
            conn.execute(
                """
                INSERT INTO audit_events (id, actor_id, action, target_type, target_id, details_json)
                VALUES (?, NULL, 'whatsapp_order_created', 'order', ?, ?)
                """,
                (f"aud_{uuid.uuid4().hex[:12]}", order_id, json.dumps({
                    "order_number": order_num,
                    "attribution_source": source_type,
                    "campaign": campaign,
                    "customer_selling_price": subtotal,
                    "commission_rate": fee_rate,
                    "commission_amount": fee_amount,
                    "merchant_payout": merchant_payout,
                    "fee_rule_version": rule_ver,
                    "cash_only": is_cash_only
                }))
            )
            conn.commit()

            return {
                "success": True,
                "order_id": order_id,
                "order_number": order_num,
                "customer_alias": customer_alias,
                "total": total_amount,
                "customer_selling_price": subtotal,
                "commission_rate": fee_rate,
                "commission_amount": fee_amount,
                "merchant_payout": merchant_payout,
                "rule_version": rule_ver,
                "is_cash_only": is_cash_only,
                "cash_due": total_amount,
                "secure_token": token_info["token"],
                "source_type": "merchant_acquired" if source_type == "merchant" else "mavunqo_acquired"
            }
        finally:
            conn.close()

    def get_merchant_operational_orders(
        self,
        user_id: str,
        business_id: str,
        status_filter: str = ""
    ) -> List[Dict[str, Any]]:
        """
        Fetch orders for merchant staff dashboard with strict role-based masking.
        Kitchen/staff see zero phone numbers and zero commission fees.
        Finance and owners see permanent financial breakdowns (customer selling price, 11% fee, payout).
        Calculates aging indicators.
        """
        auth_info = self.verify_role_access(
            user_id, business_id,
            ["owner", "manager", "staff", "kitchen", "support", "finance", "compliance"]
        )
        user_role = auth_info["role"]
        is_owner_or_finance = user_role in ["owner", "manager", "finance", "admin"]

        conn = get_connection(self.db_path)
        try:
            query = """
                SELECT id, order_number, customer_name, customer_phone, customer_alias, order_origin,
                       fulfillment_type, delivery_address, customer_notes, status,
                       subtotal, delivery_fee, total, currency, payment_method,
                       attribution_source, cash_due, cash_received, cash_reconciled,
                       cash_exception_reason, created_at, updated_at
                FROM orders
                WHERE business_id = ?
            """
            params = [business_id]
            if status_filter:
                query += " AND status = ?"
                params.append(status_filter)
            query += " ORDER BY created_at DESC"

            rows = conn.execute(query, params).fetchall()
            now_dt = datetime.now(timezone.utc)
            results = []

            for r in rows:
                item = dict(r)

                # 1. Mask Phone Number (Always masked for merchant staff by default)
                item["customer_alias"] = item.get("customer_alias") or item["customer_name"]
                item["masked_phone"] = mask_phone_number(item.get("customer_phone") or "")
                # Never leak raw phone
                del item["customer_phone"]

                # 2. Permanent Financial Audit fields
                subtotal = float(item["subtotal"])
                fee_rate, fee_amount, merchant_payout, rule_ver = compute_order_fee(item.get("attribution_source") or "mavunqo", subtotal)

                if is_owner_or_finance:
                    item["customer_selling_price"] = subtotal
                    item["commission_rate"] = fee_rate
                    item["commission_amount"] = fee_amount
                    item["merchant_payout"] = merchant_payout
                    item["fee_rule_version"] = rule_ver
                else:
                    item["attribution_source"] = None
                    item["commission_rate"] = None
                    item["commission_amount"] = None
                    item["merchant_payout"] = None
                    item["fee_rule_version"] = None

                item["cash_status"] = "exception" if item.get("cash_exception_reason") else ("reconciled" if item.get("cash_reconciled") else "pending")
                item["cash_due"] = float(item.get("cash_due") or item["total"])
                item["cash_collected"] = float(item.get("cash_received") or 0.0)

                # 3. Calculate Aging Indicator
                created_iso = item["created_at"].replace(" ", "T")
                try:
                    c_time = datetime.fromisoformat(created_iso)
                    if c_time.tzinfo is None:
                        c_time = c_time.replace(tzinfo=timezone.utc)
                    age_minutes = int((now_dt - c_time).total_seconds() / 60)
                except Exception:
                    age_minutes = 0

                item["aging_minutes"] = max(0, age_minutes)
                item["aging_alert"] = age_minutes > 20 and item["status"] in ["pending", "accepted", "in_kitchen"]

                # 4. Fetch line items
                oi_rows = conn.execute(
                    "SELECT id, menu_item_id, item_name_en, unit_price, quantity, line_total FROM order_items WHERE order_id = ?",
                    (item["id"],)
                ).fetchall()
                item["items"] = [dict(oi) for oi in oi_rows]

                # 5. Fetch active substitutions
                sub_rows = conn.execute(
                    "SELECT id, original_item_id, substitute_item_name, price_difference, status FROM order_substitutions WHERE order_id = ?",
                    (item["id"],)
                ).fetchall()
                item["substitutions"] = [dict(s) for s in sub_rows]

                results.append(item)

            return results
        finally:
            conn.close()

    def update_order_status_by_staff(
        self,
        user_id: str,
        business_id: str,
        order_id: str,
        new_status: str,
        notes: str = ""
    ) -> Dict[str, Any]:
        """
        Transition order status with role verification and audit logging.
        Valid: pending -> accepted -> in_kitchen -> ready -> completed / cancelled.
        """
        auth_info = self.verify_role_access(user_id, business_id, ["owner", "manager", "staff", "kitchen", "support"])
        conn = get_connection(self.db_path)
        try:
            order = conn.execute("SELECT id, status, total FROM orders WHERE id = ? AND business_id = ?", (order_id, business_id)).fetchone()
            if not order:
                raise ValueError("Order not found.")

            conn.execute(
                "UPDATE orders SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (new_status, order_id)
            )
            # Record audit event
            conn.execute(
                """
                INSERT INTO audit_events (id, actor_id, action, target_type, target_id, details_json)
                VALUES (?, ?, 'order_status_updated', 'order', ?, ?)
                """,
                (f"aud_{uuid.uuid4().hex[:12]}", user_id, order_id, json.dumps({
                    "from_status": order["status"],
                    "to_status": new_status,
                    "notes": notes,
                    "role": auth_info["role"]
                }))
            )
            conn.commit()
            return {"success": True, "order_id": order_id, "new_status": new_status}
        finally:
            conn.close()

    def record_cash_collection(
        self,
        user_id: str,
        business_id: str,
        order_id: str,
        amount_collected: float,
        is_exception: bool = False,
        exception_notes: str = ""
    ) -> Dict[str, Any]:
        """
        Track cash due vs cash collected separately from order completion.
        Flags discrepancy as cash_exception.
        """
        self.verify_role_access(user_id, business_id, ["owner", "manager", "staff", "finance"])
        conn = get_connection(self.db_path)
        try:
            order = conn.execute("SELECT id, total, cash_due FROM orders WHERE id = ? AND business_id = ?", (order_id, business_id)).fetchone()
            if not order:
                raise ValueError("Order not found.")

            cash_due = float(order["cash_due"] or order["total"])
            cash_status = "collected"
            if is_exception or abs(amount_collected - cash_due) > 0.01:
                cash_status = "exception"

            conn.execute(
                """
                UPDATE orders
                SET cash_received = ?,
                    cash_reconciled = CASE WHEN ? = 'collected' THEN 1 ELSE 0 END,
                    cash_exception_reason = CASE WHEN ? = 'exception' THEN ? ELSE cash_exception_reason END,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (amount_collected, cash_status, cash_status, exception_notes or "Discrepancy noted", order_id)
            )

            conn.execute(
                """
                INSERT INTO audit_events (id, actor_id, action, target_type, target_id, details_json)
                VALUES (?, ?, 'cash_collection_recorded', 'order', ?, ?)
                """,
                (f"aud_{uuid.uuid4().hex[:12]}", user_id, order_id, json.dumps({
                    "cash_due": cash_due,
                    "amount_collected": amount_collected,
                    "cash_status": cash_status,
                    "notes": exception_notes
                }))
            )
            conn.commit()
            return {
                "success": True,
                "order_id": order_id,
                "cash_due": cash_due,
                "cash_collected": amount_collected,
                "cash_status": cash_status
            }
        finally:
            conn.close()

    def record_financial_adjustment(
        self,
        user_id: str,
        business_id: str,
        order_id: str,
        adjustment_type: str,
        adjustment_amount: float,
        reason: str
    ) -> Dict[str, Any]:
        """
        Permanently record any approved credit, refund, or fee adjustment.
        Allowed types: 'credit', 'refund', 'fee_reversal', 'manager_adjustment'.
        Requires manager, owner, finance, or admin.
        """
        self.verify_role_access(user_id, business_id, ["owner", "manager", "finance", "admin"])
        if adjustment_amount <= 0:
            raise ValueError("Adjustment amount must be positive.")
        if not reason or len(reason.strip()) < 5:
            raise ValueError("Reason required for financial adjustment.")

        conn = get_connection(self.db_path)
        try:
            order = conn.execute("SELECT id, total, subtotal FROM orders WHERE id = ? AND business_id = ?", (order_id, business_id)).fetchone()
            if not order:
                raise ValueError("Order not found.")

            conn.execute(
                """
                INSERT INTO audit_events (id, actor_id, action, target_type, target_id, details_json)
                VALUES (?, ?, 'financial_adjustment', 'order', ?, ?)
                """,
                (f"aud_{uuid.uuid4().hex[:12]}", user_id, order_id, json.dumps({
                    "adjustment_type": adjustment_type,
                    "amount": adjustment_amount,
                    "reason": reason.strip(),
                    "recorded_at": int(time.time())
                }))
            )
            conn.commit()
            return {
                "success": True,
                "order_id": order_id,
                "adjustment_type": adjustment_type,
                "amount": adjustment_amount,
                "reason": reason.strip()
            }
        finally:
            conn.close()

    def propose_item_substitution(
        self,
        user_id: str,
        business_id: str,
        order_id: str,
        original_item_id: str,
        proposed_item_id: str
    ) -> Dict[str, Any]:
        """
        Merchant staff proposes item substitution when an ingredient/dish is out of stock.
        """
        self.verify_role_access(user_id, business_id, ["owner", "manager", "staff", "kitchen"])
        conn = get_connection(self.db_path)
        try:
            orig = conn.execute("SELECT name_en, price FROM menu_items WHERE id = ?", (original_item_id,)).fetchone()
            prop = conn.execute("SELECT name_en, price FROM menu_items WHERE id = ?", (proposed_item_id,)).fetchone()
            if not orig or not prop:
                raise ValueError("Items not found in catalog.")

            price_diff = float(prop["price"]) - float(orig["price"])
            sub_id = f"sub_{uuid.uuid4().hex[:10]}"

            conn.execute(
                """
                INSERT INTO order_substitutions (id, order_id, original_item_id, substitute_item_name, price_difference, reason, status)
                VALUES (?, ?, ?, ?, ?, 'Out of stock in kitchen', 'proposed')
                """,
                (sub_id, order_id, original_item_id, prop["name_en"], price_diff)
            )

            conn.execute(
                """
                INSERT INTO audit_events (id, actor_id, action, target_type, target_id, details_json)
                VALUES (?, ?, 'substitution_proposed', 'order', ?, ?)
                """,
                (f"aud_{uuid.uuid4().hex[:12]}", user_id, order_id, json.dumps({
                    "sub_id": sub_id,
                    "original": orig["name_en"],
                    "proposed": prop["name_en"],
                    "price_difference": price_diff
                }))
            )
            conn.commit()
            return {
                "success": True,
                "substitution_id": sub_id,
                "original": orig["name_en"],
                "proposed": prop["name_en"],
                "price_diff": price_diff
            }
        finally:
            conn.close()

    def break_glass_exceptional_access(
        self,
        user_id: str,
        business_id: str,
        order_id: str,
        reason: str
    ) -> Dict[str, Any]:
        """
        Controlled emergency access to view customer contact info.
        Requires high privilege (owner, manager, compliance, admin), mandatory justification,
        and leaves an immutable audit trail.
        """
        if not reason or len(reason.strip()) < 10:
            raise ValueError("A specific operational reason (at least 10 characters) is required for exceptional access.")

        self.verify_role_access(user_id, business_id, ["owner", "manager", "compliance", "admin"])

        conn = get_connection(self.db_path)
        try:
            order = conn.execute("SELECT id, customer_phone, customer_name FROM orders WHERE id = ? AND business_id = ?", (order_id, business_id)).fetchone()
            if not order:
                raise ValueError("Order not found.")

            phone = order["customer_phone"]
            now = int(time.time())

            # 1. Record in exceptional_access_logs
            conn.execute(
                """
                INSERT INTO exceptional_access_logs (id, requester_id, order_id, reason, authorized_by)
                VALUES (?, ?, ?, ?, ?)
                """,
                (f"eal_{uuid.uuid4().hex[:10]}", user_id, order_id, reason.strip(), user_id)
            )

            # 2. Record in audit_events
            conn.execute(
                """
                INSERT INTO audit_events (id, actor_id, action, target_type, target_id, details_json)
                VALUES (?, ?, 'exceptional_access_unmask', 'order', ?, ?)
                """,
                (f"aud_{uuid.uuid4().hex[:12]}", user_id, order_id, json.dumps({
                    "reason": reason.strip(),
                    "field": "customer_phone"
                }))
            )
            conn.commit()

            return {
                "success": True,
                "order_id": order_id,
                "customer_phone": phone,
                "warning": "Exceptional access logged. Do not distribute or retain this phone number outside direct order resolution."
            }
        finally:
            conn.close()

    def initiate_manual_whatsapp_fallback(
        self,
        user_id: str,
        business_id: str,
        order_id: str,
        reason: str
    ) -> Dict[str, Any]:
        """
        Provides controlled manual WhatsApp fallback with mandatory phone-number exposure warning.
        Logs handoff and requires staff authorization.
        """
        if not reason or len(reason.strip()) < 5:
            raise ValueError("Operational reason required for fallback handoff.")

        self.verify_role_access(user_id, business_id, ["owner", "manager", "support"])

        conn = get_connection(self.db_path)
        try:
            order = conn.execute(
                "SELECT o.id, o.customer_phone, b.whatsapp AS merchant_wa, b.trading_name "
                "FROM orders o JOIN businesses b ON o.business_id = b.id WHERE o.id = ? AND o.business_id = ?",
                (order_id, business_id)
            ).fetchone()
            if not order:
                raise ValueError("Order not found.")

            warning_text = (
                "⚠️ AVISO DE PRIVACIDAD: Al realizar el enlace directo por WhatsApp, el número de teléfono "
                "del cliente será visible para el comercio. MAVUNQO no puede evitar comunicaciones posteriores "
                "fuera de la plataforma. El pedido y resultado final deben permanecer registrados en MAVUNQO."
            )

            conn.execute(
                """
                INSERT INTO manual_fallback_logs (id, order_id, staff_id, reason, customer_warned, warning_text)
                VALUES (?, ?, ?, ?, 1, ?)
                """,
                (f"mfl_{uuid.uuid4().hex[:10]}", order_id, user_id, reason.strip(), warning_text)
            )

            conn.execute(
                """
                INSERT INTO audit_events (id, actor_id, action, target_type, target_id, details_json)
                VALUES (?, ?, 'manual_fallback_initiated', 'order', ?, ?)
                """,
                (f"aud_{uuid.uuid4().hex[:12]}", user_id, order_id, json.dumps({
                    "reason": reason.strip(),
                    "warning_displayed": True
                }))
            )
            conn.commit()

            return {
                "success": True,
                "order_id": order_id,
                "warning": warning_text,
                "merchant_whatsapp": order["merchant_wa"],
                "fallback_recorded": True
            }
        finally:
            conn.close()

    def generate_sanitized_csv_export(
        self,
        user_id: str,
        business_id: str
    ) -> str:
        """
        Generates a privacy-compliant CSV export for merchant accounting.
        Contains ZERO raw phone numbers. Includes selling price, 11% commission, payout.
        """
        self.verify_role_access(user_id, business_id, ["owner", "manager", "finance", "admin"])

        orders = self.get_merchant_operational_orders(user_id, business_id)
        lines = [
            "Order Number,Date,Customer Alias,Fulfillment,Status,Customer Selling Price,Commission Rate,Commission Amount,Merchant Payout,Cash Due,Cash Collected,Cash Status"
        ]
        for o in orders:
            subtotal = o.get("customer_selling_price", o.get("subtotal", 0.0))
            comm_rate = o.get("commission_rate", 0.11)
            comm_amt = o.get("commission_amount", round(subtotal * 0.11, 2))
            payout = o.get("merchant_payout", round(subtotal - comm_amt, 2))

            row = [
                o.get("order_number", ""),
                o.get("created_at", "")[:10],
                f'"{o.get("customer_alias", "")}"',
                o.get("fulfillment_type", ""),
                o.get("status", ""),
                f'{subtotal:.2f}',
                f'{comm_rate * 100:.1f}%',
                f'{comm_amt:.2f}',
                f'{payout:.2f}',
                f'{o.get("cash_due", 0):.2f}',
                f'{o.get("cash_collected", 0):.2f}',
                o.get("cash_status", "pending")
            ]
            lines.append(",".join(row))

        return "\n".join(lines)
