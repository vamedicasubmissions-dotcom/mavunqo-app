"""
Menu & File Parser for Mavunqo.
Extracts dishes, services, and prices from text, CSV, PDF, and image files without paid APIs (Cost: $0.00).
"""
import re

def extract_items_from_text(raw_text: str):
    lines = [line.strip() for line in raw_text.splitlines() if line.strip()]
    extracted = []

    for line in lines:
        # Match currency and amount
        # Case 1: RD$ 450 or $ 15 or DOP 650 or USD 25
        # Case 2: 450 RD$ or 15 $ or 650 DOP or 25 USD
        m = re.search(r'(RD\$|\$|DOP|USD)\s*(\d+(?:\.\d{1,2})?)', line, re.IGNORECASE)
        if not m:
            m = re.search(r'(\d+(?:\.\d{1,2})?)\s*(RD\$|\$|DOP|USD)', line, re.IGNORECASE)
            if m:
                amt = float(m.group(1))
                sym = m.group(2).upper()
            else:
                amt = None
                sym = None
        else:
            sym = m.group(1).upper()
            amt = float(m.group(2))

        if amt is not None:
            currency = "USD" if ("USD" in sym or (sym == "$" and "RD" not in sym)) else "DOP"
            # Cut match from line
            name = (line[:m.start()] + " " + line[m.end():]).strip(" -–:.,")
            if not name:
                name = "Menu Item"

            extracted.append({
                "name_en": name,
                "name_es": name,
                "price": amt,
                "currency": currency,
                "display_price": 1,
                "description_en": "",
                "description_es": ""
            })
        else:
            if len(line) >= 3 and not line.lower().startswith(("tel", "whatsapp", "email", "horario", "calle", "address")):
                extracted.append({
                    "name_en": line,
                    "name_es": line,
                    "price": None,
                    "currency": "DOP",
                    "display_price": 0,
                    "description_en": "",
                    "description_es": ""
                })

    return extracted
