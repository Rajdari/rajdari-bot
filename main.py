import os
import requests
from fastapi import FastAPI, Request, Response
from google import genai

app = FastAPI()

# --- Configuration (Loaded from Environment Variables) ---
META_ACCESS_TOKEN = os.getenv("META_ACCESS_TOKEN")
PHONE_NUMBER_ID = os.getenv("PHONE_NUMBER_ID")
VERIFY_TOKEN = os.getenv("WEBHOOK_VERIFY_TOKEN", "rajdari_ai_secret_2026")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Owner phone number with country code (e.g. 917992054770)
OWNER_PHONE = os.getenv("OWNER_PHONE", "917992054770")

# Initialize Gemini Client
client = genai.Client(api_key=GEMINI_API_KEY)

# --- Prompts ---
OWNER_SYSTEM_PROMPT = """
You are the Executive AI Assistant to Digvijay Singh, owner of Rajdari Resort in Chandauli, UP.
Your role is to assist him with:
1. Daily resort operations, staff management, and task planning.
2. Drafting professional replies to vendors, OTAs (MakeMyTrip, Bookingjini, Cleartrip), and guests.
3. Reviewing statutory compliance reminders (GST, Advance Tax) and billing logs.
Tone: Concise, professional, direct, and respectful. Use English or Hindi based on his prompt.
"""

GUEST_SYSTEM_PROMPT = """
You are the official 24/7 AI Concierge for Rajdari Resort, located near Chandraprabha Wildlife Sanctuary & Rajdari-Devdari Waterfalls in Chandauli, UP (near Varanasi).
Property details:
- Accommodations: Eco Deluxe Cottages and Luxury Premium Cottages.
- Amenities: Outdoor swimming pool, hot tub, multi-cuisine restaurant, free Wi-Fi, lush garden trails, pet-friendly.
- Timings: Check-in: 12:00 PM | Check-out: 11:00 AM.
- Reception phone: +91 79920 54770. Website: https://www.rajdariresort.com/
- Distance from Varanasi: Approx. 65 km (2-hour scenic drive via Chakia).
Tone: Warm, polite, hospitable, and concise (under 120 words per response). Match the guest's language (English, Hindi, or Hinglish).
If the guest wants to book, collect their dates, guest count, and cottage preference, and provide the reception contact.
"""

@app.get("/")
async def root():
    return {"status": "Rajdari Resort AI Bot is running"}

@app.get("/webhook")
async def verify_webhook(request: Request):
    """Handles the Meta WhatsApp webhook verification handshake."""
    params = dict(request.query_params)
    mode = params.get("hub.mode")
    token = params.get("hub.verify_token")
    challenge = params.get("hub.challenge")

    if mode == "subscribe" and token == VERIFY_TOKEN:
        return Response(content=challenge, media_type="text/plain")
    return Response(content="Verification failed", status_code=403)

@app.post("/webhook")
async def handle_whatsapp_message(request: Request):
    """Receives incoming messages, selects the right persona, and replies."""
    body = await request.json()

    try:
        entry = body.get("entry", [])[0]
        changes = entry.get("changes", [])[0]
        value = changes.get("value", {})
        messages = value.get("messages", [])

        if not messages:
            return {"status": "no_messages"}

        message = messages[0]
        sender_phone = message.get("from")
        message_text = message.get("text", {}).get("body", "").strip()

        if not message_text:
            return {"status": "non_text"}

        # 1. Determine whether sender is Owner or Guest
        if sender_phone == OWNER_PHONE:
            system_instruction = OWNER_SYSTEM_PROMPT
        else:
            system_instruction = GUEST_SYSTEM_PROMPT

        # 2. Generate response from Gemini
        ai_response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=message_text,
            config={"system_instruction": system_instruction}
        )
        reply_text = ai_response.text.strip()

        # 3. Send reply via Meta WhatsApp Cloud API
        send_url = f"https://graph.facebook.com/v20.0/{PHONE_NUMBER_ID}/messages"
        headers = {
            "Authorization": f"Bearer {META_ACCESS_TOKEN}",
            "Content-Type": "application/json"
        }
        payload = {
            "messaging_product": "whatsapp",
            "to": sender_phone,
            "type": "text",
            "text": {"body": reply_text}
        }
        requests.post(send_url, json=payload, headers=headers)

    except Exception as e:
        print(f"Error handling webhook: {e}")

    return {"status": "success"}
