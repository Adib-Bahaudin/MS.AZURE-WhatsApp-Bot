import os
import requests
from fastapi import FastAPI, Request, BackgroundTasks
from dotenv import load_dotenv

load_dotenv()
from bot_logic import get_ai_response 

EVOLUTION_API_URL = os.getenv("EVOLUTION_API_URL")
EVOLUTION_API_KEY = os.getenv("EVOLUTION_API_KEY")
EVOLUTION_INSTANCE_NAME = os.getenv("EVOLUTION_INSTANCE_NAME")

app = FastAPI(title="WhatsApp POS Bot (Evolution API)")

def send_whatsapp_message(to_number: str, message_text: str):
    """Mengirim balasan via Evolution API."""
    url = f"{EVOLUTION_API_URL}/message/sendText/{EVOLUTION_INSTANCE_NAME}"
    
    headers = {
        "apikey": EVOLUTION_API_KEY,
        "Content-Type": "application/json"
    }
    
    payload = {
        "number": to_number,
        "text": message_text
    }
    
    try:
        response = requests.post(url, json=payload, headers=headers)
        response.raise_for_status()
        print(f"✅ Pesan terkirim ke {to_number}")
    except requests.exceptions.RequestException as e:
        print(f"❌ Gagal mengirim pesan: {response.text if 'response' in locals() else e}")

@app.post("/webhook")
async def receive_message(request: Request, background_tasks: BackgroundTasks):
    """Menerima Webhook dari Evolution API."""
    try:
        payload = await request.json()
        
        event_type = payload.get("event")
        
        if event_type == "messages.upsert":
            data = payload.get("data", {})
            message_info = data.get("message", {})
            key_info = data.get("key", {})
            
            if key_info.get("fromMe") == True:
                return {"status": "ignored", "reason": "fromMe"}
            
            remote_jid = key_info.get("remoteJid", "")
            
            if "@g.us" in remote_jid:
                return {"status": "ignored", "reason": "group_message"}
                
            sender_number = remote_jid.split("@")[0]
            
            media_types = [
                "audioMessage", "imageMessage", "videoMessage", 
                "stickerMessage", "documentMessage", "locationMessage",
                "contactMessage", "reactionMessage"
            ]
            
            if any(media in message_info for media in media_types):
                print(f"⏩ Mengabaikan pesan non-teks dari {sender_number}")
                return {"status": "ignored", "reason": "media_message"}

            incoming_text = ""
            if "conversation" in message_info:
                incoming_text = message_info["conversation"]
            elif "extendedTextMessage" in message_info:
                incoming_text = message_info["extendedTextMessage"].get("text", "")
                
            if incoming_text:
                print(f"📥 Pesan masuk dari {sender_number}: {incoming_text}")
                
                ai_reply = get_ai_response(incoming_text, sender_number)
                
                if ai_reply != "SILENT_IGNORE":
                    background_tasks.add_task(send_whatsapp_message, sender_number, ai_reply)
                else:
                    print(f"🤫 Bot diam (Nomor {sender_number} sedang dalam masa jeda admin/spam)")
                
        return {"status": "success"}
        
    except Exception as e:
        print(f"❌ Error membaca webhook: {e}")
        return {"status": "error"}