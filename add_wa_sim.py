with open("backend/server.py", "rb") as f:
    text = f.read().decode("utf-8")

# We want to add /api/whatsapp/test-message in do_POST
old_target = """        # WhatsApp Inbound Webhook (POST)
        if path == "/api/whatsapp/webhook":"""

new_target = """        # WhatsApp Test Message Simulator Endpoint (POST)
        if path == "/api/whatsapp/test-message":
            content_length = int(self.headers.get("Content-Length", 0))
            payload = json.loads(self.rfile.read(content_length).decode("utf-8"))
            phone = payload.get("phone", "+18296414722")
            msg_text = payload.get("message", "")
            biz_slug = payload.get("business_slug", "yaha-style-rd")
            
            from backend.whatsapp_bot import WhatsAppOrderBot
            bot = WhatsAppOrderBot(DB_PATH)
            bot_res = bot.handle_message(
                customer_phone=phone,
                message_text=msg_text,
                business_slug_or_id=biz_slug
            )
            return self.send_json({"reply": bot_res.get("text", "")})

        # WhatsApp Inbound Webhook (POST)
        if path == "/api/whatsapp/webhook":"""

text = text.replace(old_target, new_target)

# Also in do_GET to serve /whatsapp directly
old_get = """        if path == "/dashboard":
            return self.serve_file("frontend/dashboard.html", "text/html; charset=utf-8")"""

new_get = """        if path == "/dashboard":
            return self.serve_file("frontend/dashboard.html", "text/html; charset=utf-8")

        if path == "/whatsapp" or path == "/whatsapp-simulator":
            return self.serve_file("frontend/whatsapp_simulator.html", "text/html; charset=utf-8")"""

text = text.replace(old_get, new_get)

with open("backend/server.py", "wb") as f:
    f.write(text.encode("utf-8"))

print("Added /api/whatsapp/test-message and /whatsapp route to server.py!")
