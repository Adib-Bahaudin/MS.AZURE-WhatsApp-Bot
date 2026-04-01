import os
import requests
from fastapi import FastAPI, Request, BackgroundTasks
from dotenv import load_dotenv

load_dotenv()
INFOBIP_BASE_URL = os.getenv("INFOBIP_BASE_URL")
INFOBIP_API_KEY = os.getenv("INFOBIP_API_KEY")

from bot_logic import get_ai_response 

app = FastAPI(title="WhatsApp POS Bot")

def send_whatsapp_message(to_number: str, message_text: str):
    """Mengirim pesan teks ke pengguna via Infobip WhatsApp API."""
    
    url = f"{INFOBIP_BASE_URL}/whatsapp/1/message/text"
    
    headers = {
        "Authorization": f"App {INFOBIP_API_KEY}",
        "Content-Type": "application/json",
        "Accept": "application/json"
    }
    
    payload = {
        "from": "447860088970", 
        "to": to_number,
        "content": {
            "text": message_text
        }
    }
    
    try:
        response = requests.post(url, json=payload, headers=headers)
        response.raise_for_status() 
        print(f"Pesan berhasil dikirim ke {to_number}")
    except requests.exceptions.RequestException as e:
        print(f"Gagal mengirim pesan: {e}")

@app.post("/webhook")
async def receive_whatsapp_message(request: Request, background_tasks: BackgroundTasks):
    """Menerima pesan JSON yang dilempar oleh Infobip."""
    
    try:
        payload = await request.json()
        
        if "results" in payload:
            for message in payload["results"]:
                sender_number = message.get("from")
                incoming_text = message.get("message", {}).get("text", "")
                
                print(f"Pesan masuk dari {sender_number}: {incoming_text}")
                
                ai_reply = get_ai_response(incoming_text, sender_number)
                
                #ai_reply = f"Halo! Anda mengirim: {incoming_text}. Otak AI sedang dirakit."
                
                background_tasks.add_task(send_whatsapp_message, sender_number, ai_reply)
                
        return {"status": "success"}
        
    except Exception as e:
        print(f"Error memproses webhook: {e}")
        return {"status": "error", "message": str(e)}

@app.get("/")
def health_check():
    return {"status": "Server Bot WhatsApp Aktif!"}