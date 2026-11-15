from backend.whatsapp_bot import WhatsAppOrderBot

bot = WhatsAppOrderBot("mavunqo.db")

print("--- Test 1: Inquire about Catalog ---")
res1 = bot.handle_message(
    customer_phone="+18296414722",
    message_text="Show me the catalog for Yaha Style",
    business_slug_or_id="yaha-style-rd"
)
print("Catalog Items Count:", res1.get("catalog_count"))
print(res1["text"][:200].encode("ascii", "ignore").decode("ascii") + "...\n")

print("--- Test 2: Inquire about Red Dress ---")
res2 = bot.handle_message(
    customer_phone="+18296414722",
    message_text="I want to buy 1 Red Twist-Front Ribbed Long Sleeve Dress",
    business_slug_or_id="yaha-style-rd"
)
print("Order created successfully!")
print(res2["text"][:200].encode("ascii", "ignore").decode("ascii") + "...\n")
