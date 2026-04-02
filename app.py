import os
import requests
from fastapi import FastAPI, Request, BackgroundTasks, Response
from dotenv import load_dotenv

load_dotenv()
from bot_logic import get_ai_response 

META_ACCESS_TOKEN = os.getenv("META_ACCESS_TOKEN")
META_PHONE_NUMBER_ID = os.getenv("META_PHONE_NUMBER_ID")
META_VERIFY_TOKEN = os.getenv("META_VERIFY_TOKEN")

app = FastAPI(title="WhatsApp POS Bot (Meta)")

def send_whatsapp_message(to_number: str, message_text: str):
    """Mengirim balasan via Meta WhatsApp Cloud API."""
    url = f"https://graph.facebook.com/v18.0/{META_PHONE_NUMBER_ID}/messages"
    
    headers = {
        "Authorization": f"Bearer {META_ACCESS_TOKEN}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "messaging_product": "whatsapp",
        "to": to_number,
        "type": "text",
        "text": {"body": message_text}
    }
    
    try:
        response = requests.post(url, json=payload, headers=headers)
        response.raise_for_status()
        print(f"Pesan terkirim ke {to_number}")
        print(message_text)
    except requests.exceptions.RequestException as e:
        print(f"Gagal mengirim: {response.text if 'response' in locals() else e}")

@app.get("/webhook")
def verify_webhook(request: Request):
    """Meta akan menembak endpoint ini saat Anda mengklik 'Verify and Save'."""
    mode = request.query_params.get("hub.mode")
    token = request.query_params.get("hub.verify_token")
    challenge = request.query_params.get("hub.challenge")

    if mode == "subscribe" and token == META_VERIFY_TOKEN:
        print("Webhook Meta Berhasil Diverifikasi!")
        return Response(content=challenge, media_type="text/plain")
    
    return {"error": "Invalid token"}

@app.post("/webhook")
async def receive_message(request: Request, background_tasks: BackgroundTasks):
    """Menerima JSON super bersarang (nested) dari Meta."""
    try:
        payload = await request.json()
        
        if payload.get("object") == "whatsapp_business_account":
            entry = payload.get("entry", [])[0]
            changes = entry.get("changes", [])[0]
            value = changes.get("value", {})
            
            if "messages" in value:
                message = value["messages"][0]
                sender_number = message["from"]
                incoming_text = message.get("text", {}).get("body", "")
                
                print(f"Pesan masuk dari {sender_number}: {incoming_text}")
                
                ai_reply = get_ai_response(incoming_text, sender_number)
                
                background_tasks.add_task(send_whatsapp_message, sender_number, ai_reply)
            
            elif "statuses" in value:
                status_info = value["statuses"][0]
                status_type = status_info.get("status")
                if status_type == "failed":
                    errors = status_info.get("errors", [{}])[0]
                    print(f"❌ PESAN GAGAL DIKIRIM! Alasan: {errors.get('title')} (Kode: {errors.get('code')})")
                else:
                    print(f"Status Pengiriman: {status_type}")
                
        return {"status": "success"}
    except Exception as e:
        print(f"Error membaca webhook: {e}")
        return {"status": "error"}