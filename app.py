import os
import time
import requests
from fastapi import FastAPI, Request, BackgroundTasks
from dotenv import load_dotenv

load_dotenv()
from bot_logic import get_ai_response, toggle_ai, set_global_closed, set_permanent_exclude, ensure_db_ready

EVOLUTION_API_URL = os.getenv("EVOLUTION_API_URL")
EVOLUTION_API_KEY = os.getenv("EVOLUTION_API_KEY")
EVOLUTION_INSTANCE_NAME = os.getenv("EVOLUTION_INSTANCE_NAME")

app = FastAPI(title="WhatsApp POS Bot (Evolution API)")

latest_messages = {}

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

def process_and_send_reply(incoming_text: str, sender_number: str, message_timestamp: float):
    """Memproses AI di latar belakang dengan sistem prioritas pesan terbaru."""
    try:
        
        ensure_db_ready() 
        
        if latest_messages.get(sender_number) != message_timestamp:
            print(f"⏩ Batal proses AI: Ada pesan yang lebih baru dari {sender_number}.")
            return

        ai_reply = get_ai_response(incoming_text, sender_number)
        
        if latest_messages.get(sender_number) != message_timestamp:
            print(f"⏩ Batal balas: {sender_number} mengirim pesan baru saat AI sedang mengetik.")
            return

        if ai_reply != "SILENT_IGNORE":
            send_whatsapp_message(sender_number, ai_reply)
        else:
            print(f"🤫 Bot diam (Nomor {sender_number} sedang jeda admin/spam/AI off)")
            
    except Exception as e:
        print(f"❌ Error memproses AI: {e}")

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
            
            remote_jid = key_info.get("remoteJid", "")
            if "@g.us" in remote_jid:
                return {"status": "ignored", "reason": "group_message"}
                
            sender_number = remote_jid.split("@")[0]
            
            incoming_text = ""
            if "conversation" in message_info:
                incoming_text = message_info["conversation"]
            elif "extendedTextMessage" in message_info:
                incoming_text = message_info["extendedTextMessage"].get("text", "")

            command = incoming_text.strip().lower()

            if command == "/matikan_ai":
                toggle_ai(sender_number, turn_off=True)
                print(f"🛑 AI DIMATIKAN secara manual untuk {sender_number}")
                background_tasks.add_task(send_whatsapp_message, sender_number, "*(Sistem: AI telah dimatikan untuk chat ini)*")
                return {"status": "success", "reason": "ai_disabled_manually"}

            if key_info.get("fromMe") == True:
                if command == "/hidupkan_ai":
                    toggle_ai(sender_number, turn_off=False)
                    print(f"✅ AI DIHIDUPKAN secara manual untuk {sender_number}")
                    background_tasks.add_task(send_whatsapp_message, sender_number, "*(Sistem: AI telah dihidupkan untuk chat ini)*")
                    return {"status": "success", "reason": "ai_enabled_manually"}

                elif command.startswith("/tutup_sementara"):
                    parts = incoming_text.strip().split(" ", 1)
                    
                    if len(parts) > 1:
                        reopen_info = parts[1].strip()
                        set_global_closed(True, reopen_info)
                        pesan_balasan = f"*(Sistem: Status Toko diset TUTUP SEMENTARA. AI akan memberitahu pelanggan bahwa toko buka kembali: {reopen_info})*"
                    else:
                        set_global_closed(True)
                        pesan_balasan = "*(Sistem: Status Toko diset TUTUP SEMENTARA secara global. AI akan merespon alasan admin keluar tanpa estimasi waktu)*"
                        
                    background_tasks.add_task(send_whatsapp_message, sender_number, pesan_balasan)
                    return {"status": "success"}
                
                elif command == "/buka_kembali":
                    set_global_closed(False)
                    background_tasks.add_task(send_whatsapp_message, sender_number, "*(Sistem: Toko telah DIBUKA KEMBALI. AI kembali ke mode normal)*")
                    return {"status": "success"}

                elif command == "/kecualikan_ai":
                    set_permanent_exclude(sender_number, True)
                    background_tasks.add_task(send_whatsapp_message, sender_number, "*(Sistem: Chat ini telah DIKECUALIKAN dari AI selamanya)*")
                    return {"status": "success"}
                
                elif command == "/tambahkan_ai":
                    set_permanent_exclude(sender_number, False)
                    background_tasks.add_task(send_whatsapp_message, sender_number, "*(Sistem: Chat ini telah DITAMBAHKAN kembali ke daftar AI)*")
                    return {"status": "success"}
                
                return {"status": "ignored", "reason": "fromMe"}
            
            media_types = [
                "audioMessage", "imageMessage", "videoMessage", 
                "stickerMessage", "documentMessage", "locationMessage",
                "contactMessage", "reactionMessage"
            ]
            
            if any(media in message_info for media in media_types):
                print(f"⏩ Mengabaikan pesan non-teks dari {sender_number}")
                return {"status": "ignored", "reason": "media_message"}

            if incoming_text:
                print(f"📥 Pesan masuk dari {sender_number}: {incoming_text}")
                
                current_time = time.time()
                
                latest_messages[sender_number] = current_time
                
                background_tasks.add_task(process_and_send_reply, incoming_text, sender_number, current_time)
                
        return {"status": "success"}
        
    except Exception as e:
        import traceback
        print(f"❌ Error membaca webhook: {traceback.format_exc()}")
        return {"status": "error", "pesan_error": str(e), "tipe_error": type(e).__name__}

@app.get("/")
async def root():
    """Endpoint untuk Health Check Azure"""
    return {"status": "online", "message": "WebApp Kasir AI Berjalan Sempurna!"}