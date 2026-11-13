"""
Mavunqo Merchant Discovery & WhatsApp Outreach Engine
- Formats Google Maps business leads (Name, Category, Location, Phone/WhatsApp, Google Maps URL)
- Generates high-converting, personalized bilingual WhatsApp invitation pitches
- Generates 1-click 'https://wa.me/{phone}?text={encoded_message}' direct action links
- Supports batch pre-populating draft listings directly into Mavunqo
"""
import urllib.parse
import re

class MerchantOutreachEngine:
    def __init__(self, platform_domain="https://mavunqo-app.onrender.com"):
        self.platform_domain = platform_domain

    def clean_phone_number(self, phone: str):
        """Standardize phone to international format (Dominican Republic: +1 809 / 829 / 849)"""
        if not phone:
            return ""
        digits = re.sub(r'[^0-9]', '', str(phone))
        # If starts with 809, 829, 849 and 10 digits, prepend '1'
        if len(digits) == 10 and digits.startswith(('809', '829', '849')):
            digits = '1' + digits
        return digits

    def generate_whatsapp_pitch(self, business_name: str, category_name: str, location_name: str = "Sosúa", lang: str = "es"):
        """
        Creates a natural, warm Caribbean outreach invitation for a local merchant found on Google Maps.
        Highlights: 100% Free listing, free hosted storefront/menu, and direct WhatsApp customer orders.
        """
        reg_link = f"{self.platform_domain}/register"

        if lang == "es":
            message = (
                f"¡Hola equipo de *{business_name}*! 👋 Saludos desde Sosúa.\n\n"
                f"Los vimos en Google Maps y nos encantó su trabajo en *{category_name}*.\n\n"
                f"Estamos lanzando *Mavunqo*, el nuevo directorio y portal comercial para Sosúa y la Costa Norte. "
                f"Queremos incluir a *{business_name}* con un perfil y vitrina digital gratuita (con menú/servicios y botón directo a su WhatsApp).\n\n"
                f"✨ Es *100% gratuito* y toma menos de 2 minutos registrarse aquí:\n"
                f"👉 {reg_link}\n\n"
                f"¿Tienen alguna pregunta o les gustaría que les ayudemos a configurarlo gratis? ¡Quedamos a su orden!"
            )
        else:
            message = (
                f"Hi team at *{business_name}*! 👋 Greetings from Sosúa.\n\n"
                f"We found your business on Google Maps and love what you're doing in *{category_name}*.\n\n"
                f"We are launching *Mavunqo*, the local directory and commerce platform for Sosúa and the North Coast. "
                f"We'd love to feature *{business_name}* with a free listing and hosted storefront (with your services/menu and direct WhatsApp button).\n\n"
                f"✨ It is *100% free* and takes 2 minutes to activate here:\n"
                f"👉 {reg_link}\n\n"
                f"Let us know if you have any questions or if you'd like us to set up your profile for you!"
            )

        return message

    def create_whatsapp_click_link(self, phone: str, business_name: str, category_name: str, location_name: str = "Sosúa", lang: str = "es"):
        clean_num = self.clean_phone_number(phone)
        pitch = self.generate_whatsapp_pitch(business_name, category_name, location_name, lang)
        encoded_text = urllib.parse.quote(pitch)
        
        wa_url = f"https://wa.me/{clean_num}?text={encoded_text}" if clean_num else None
        return {
            "business_name": business_name,
            "category": category_name,
            "location": location_name,
            "phone_raw": phone,
            "phone_international": clean_num,
            "pitch_text": pitch,
            "whatsapp_link": wa_url
        }

    def process_leads(self, leads: list, lang: str = "es"):
        results = []
        for lead in leads:
            bname = lead.get("name") or lead.get("business_name")
            cat = lead.get("category", "Comercio Local")
            loc = lead.get("location", "Sosúa")
            ph = lead.get("phone") or lead.get("whatsapp", "")
            
            outreach = self.create_whatsapp_click_link(ph, bname, cat, loc, lang)
            outreach["maps_url"] = lead.get("maps_url", "")
            results.append(outreach)
        return results
