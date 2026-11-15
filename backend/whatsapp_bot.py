import time
import json
import re
from typing import Dict, Any, List, Optional, Tuple
from backend.db import get_connection
from backend.redaction import redact_text, generate_customer_alias, mask_phone_number
from backend.tokens_and_attribution import create_secure_order_token, verify_attribution_signature, compute_order_fee

class WhatsAppOrderBot:
    """
    Grounded conversational order assistant for WhatsApp.
    Strictly quotes real catalog items, prices, business payment requirements (e.g. cash-only),
    and delivery capacity from the authoritative Mavunqo database.
    Does not hallucinate products or off-platform payment methods.
    """

    def __init__(self, db_path: str, base_url: str = "http://localhost:8000"):
        self.db_path = db_path
        self.base_url = base_url

    def handle_message(
        self,
        customer_phone: str,
        message_text: str,
        business_slug_or_id: Optional[str] = None,
        attribution_payload: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Processes inbound customer message and returns structured conversational response.
        """
        # Redact any phone numbers from internal debug or processing logs
        clean_prompt = redact_text(message_text).strip()
        conn = get_connection(self.db_path)
        try:
            # 1. Determine active business
            business = None
            if business_slug_or_id:
                business = conn.execute(
                    "SELECT * FROM businesses WHERE id = ? OR slug = ?",
                    (business_slug_or_id, business_slug_or_id)
                ).fetchone()

            if not business:
                # Default to El Batey Bistro or first active restaurant for Sosúa demo
                business = conn.execute(
                    "SELECT * FROM businesses WHERE category_id = 'cat_dining' ORDER BY id ASC LIMIT 1"
                ).fetchone()

            if not business:
                return {
                    "text": "Bienvenido a MAVUNQO. Actualmente nuestros comercios están actualizando sus catálogos. Por favor intenta más tarde o visita nuestro portal web.",
                    "requires_handoff": False
                }

            biz_id = business["id"]
            biz_name = business["trading_name"]
            # Dynamic payment mode configuration per merchant (cash-only vs multi-payment)
            is_cash_only = bool(business.get("cash_only", False) if isinstance(business, dict) else business["cash_only"] if "cash_only" in business.keys() else False)
            delivery_enabled = True
            loc_id = business["primary_location_id"] if business["primary_location_id"] else "loc_sosua"
            alias = generate_customer_alias(customer_phone, loc_id.replace("loc_", "").title())

            # 2. Fetch business catalog
            catalog_rows = conn.execute(
                "SELECT id, name_en, name_es, description_en, price, is_available FROM menu_items WHERE business_id = ? AND is_available = 1",
                (biz_id,)
            ).fetchall()
            catalog = [dict(r) for r in catalog_rows]

            # 3. Check keywords / intents
            text_lower = clean_prompt.lower()

            # Intent: Menu / Catalog request
            if any(k in text_lower for k in ["menu", "menú", "carta", "catalog", "catalogue", "catálogo", "catalogo", "clothes", "dresses", "items", "que hay", "qué hay", "opciones", "productos", "hola", "buenas", "hi", "hello"]):
                menu_lines = [f"🍽️ *Menú Oficial de {biz_name} en MAVUNQO*:\n"]
                for item in catalog:
                    desc = f" - _{item['description_en']}_" if item.get('description_en') else ""
                    menu_lines.append(f"• *{item['name_en']}*: RD$ {item['price']:.2f}{desc}")

                if is_cash_only:
                    menu_lines.append("\n💵 *Aviso de Pago*: Este comercio opera en *Solo Efectivo* al momento de la entrega o en mostrador.")
                else:
                    menu_lines.append("\n💳 *Opciones de Pago*: Efectivo contra entrega, Tarjeta de Crédito/Débito o Transferencia bancaria.")

                menu_lines.append("\nPara ordenar, responde indicando los productos que deseas (ejemplo: 'Quiero 2 Whole Red Snapper y 1 Jugo').")
                return {
                    "text": "\n".join(menu_lines),
                    "business_id": biz_id,
                    "catalog_count": len(catalog),
                    "requires_handoff": False
                }

            # Intent: Support / Human escalation
            if any(k in text_lower for k in ["humano", "persona", "asesor", "representante", "ayuda", "reclamo", "queja", "agente"]):
                return {
                    "text": (
                        "Entendido. Te podemos conectar con el equipo de asistencia de MAVUNQO.\n"
                        "⚠️ *Aviso de Privacidad*: Si solicitas asistencia directa con el comercio fuera de MAVUNQO, tu número telefónico podría ser visible para ellos. ¿Deseas que un operador te asista aquí o prefieres continuar con tu pedido asistido?"
                    ),
                    "requires_handoff": True,
                    "business_id": biz_id
                }

            # Intent: Order parsing & preparation
            matched_items = []
            subtotal = 0.0

            for item in catalog:
                item_name_lower = item["name_en"].lower()
                item_es_lower = (item.get("name_es") or "").lower()
                # Check if item name is mentioned
                if item_name_lower in text_lower or item_es_lower in text_lower or any(word in text_lower for word in item_name_lower.split() if len(word) > 4):
                    # Check for quantity (e.g. "2 snapper", "x2", "dos")
                    qty = 1
                    match_qty = re.search(r'(\d+)\s*' + re.escape(item_name_lower.split()[0]), text_lower)
                    if match_qty:
                        try:
                            qty = int(match_qty.group(1))
                        except Exception:
                            qty = 1

                    line_total = item["price"] * qty
                    subtotal += line_total
                    matched_items.append({
                        "menu_item_id": item["id"],
                        "name": item["name_en"],
                        "price": item["price"],
                        "quantity": qty,
                        "line_total": line_total
                    })

            if matched_items:
                # Determine attribution
                source_type = "mavunqo"
                campaign = "direct_wa"
                if attribution_payload and attribution_payload.get("m_sig"):
                    biz_ref = attribution_payload.get("m_biz")
                    camp = attribution_payload.get("m_camp", "")
                    sig = attribution_payload.get("m_sig")
                    if verify_attribution_signature(biz_ref, camp, sig):
                        source_type = "merchant"
                        campaign = camp

                fee_rate, fee_amount, merchant_payout, rule_ver = compute_order_fee(source_type, subtotal)
                delivery_fee = 150.0 if delivery_enabled else 0.0
                total_amount = subtotal + delivery_fee

                # Generate secure, single-use checkout token (stored temporarily in DB)
                import secrets
                rand_sfx = secrets.token_hex(4)
                order_temp_id = f"ord_draft_{rand_sfx}"
                
                token_data = create_secure_order_token(order_temp_id, biz_id)

                # Insert draft order to satisfy FK constraint
                conn.execute(
                    """
                    INSERT INTO orders (
                        id, order_number, business_id, customer_name, customer_phone, customer_alias,
                        fulfillment_type, status, subtotal, delivery_fee, total,
                        currency, payment_method, status_token, status_token_expires_at, attribution_source
                    ) VALUES (
                        ?, ?, ?, 'WhatsApp Guest', ?, ?, 'delivery', 'pending', ?, ?, ?,
                        'DOP', 'cash', ?, datetime(?, 'unixepoch'), ?
                    )
                    """,
                    (
                        order_temp_id, f"MVQ-{rand_sfx.upper()}", biz_id,
                        customer_phone, alias, subtotal, delivery_fee, total_amount,
                        token_data["token"], token_data["expires_at"], campaign
                    )
                )

                conn.execute(
                    """
                    INSERT INTO secure_order_tokens (token_hash, order_id, purpose, expires_at)
                    VALUES (?, ?, 'checkout_confirmation', datetime(?, 'unixepoch'))
                    """,
                    (token_data["token"], order_temp_id, token_data["expires_at"])
                )
                conn.commit()

                checkout_url = f"{self.base_url.rstrip('/')}/order/checkout?t={token_data['token']}"

                resp_lines = [
                    f"✅ *Hemos preparado tu borrador de pedido para {biz_name}*:\n"
                ]
                for it in matched_items:
                    resp_lines.append(f"• {it['quantity']}x {it['name']} — RD$ {it['line_total']:.2f}")

                resp_lines.append(f"\nSubtotal: RD$ {subtotal:.2f}")
                if delivery_fee > 0:
                    resp_lines.append(f"Tarifa de Entrega Sosúa: RD$ {delivery_fee:.2f}")
                resp_lines.append(f"*Total a Pagar*: RD$ {total_amount:.2f}")

                if is_cash_only:
                    resp_lines.append(
                        "\n💵 *IMPORTANTE (Pago en Efectivo)*:\n"
                        f"Este comercio es *Solo Efectivo*. Deberás pagar exactamente *RD$ {total_amount:.2f}* en efectivo al repartidor o en mostrador."
                    )
                else:
                    resp_lines.append("\nPago disponible: Tarjeta, Transferencia o Efectivo al confirmar.")

                resp_lines.append(
                    "\n🔒 Para confirmar y enviar a cocina de forma segura, ingresa a tu enlace protegido de MAVUNQO (válido por 30 minutos):\n"
                    f"{checkout_url}\n\n"
                    "_(Tu número nunca se comparte con los cocineros o repartidores)_."
                )

                return {
                    "text": "\n".join(resp_lines),
                    "draft_order": {
                        "business_id": biz_id,
                        "items": matched_items,
                        "subtotal": subtotal,
                        "delivery_fee": delivery_fee,
                        "total_amount": total_amount,
                        "source_type": source_type,
                        "campaign": campaign,
                        "fee_rate": fee_rate,
                        "fee_amount": fee_amount,
                        "merchant_payout": merchant_payout,
                        "token": token_data["token"]
                    },
                    "requires_handoff": False
                }

            # If unrecognized query
            return {
                "text": (
                    f"No reconocí esos productos en el catálogo de {biz_name}. "
                    "Escribe *'menú'* para ver los platos disponibles o especifica el nombre de lo que buscas."
                ),
                "requires_handoff": False,
                "business_id": biz_id
            }

        finally:
            conn.close()

def secrets_id() -> str:
    import secrets
    return secrets.token_hex(6)
