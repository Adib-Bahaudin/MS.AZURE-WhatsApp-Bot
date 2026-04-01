import os
import requests
from dotenv import load_dotenv

load_dotenv()
INFOBIP_BASE_URL = os.getenv("INFOBIP_BASE_URL")
INFOBIP_API_KEY = os.getenv("INFOBIP_API_KEY")

# --- PENGATURAN ---
# Ganti dengan nomor WhatsApp HP Anda sendiri (Gunakan kode negara, misal: 628123456789)
DESTINATION_NUMBER = "62822XXXXXX" 
# Nomor bot Infobip Anda (sesuai dengan yang ada di app.py)
SENDER_NUMBER = "447XXXXXXXX"

def test_send_message():
    url = f"{INFOBIP_BASE_URL}/whatsapp/1/message/text"
    
    headers = {
        "Authorization": f"App {INFOBIP_API_KEY}",
        "Content-Type": "application/json",
        "Accept": "application/json"
    }
    
    payload = {
        "from": SENDER_NUMBER,
        "to": DESTINATION_NUMBER,
        "content": {
            "text": "Halo! Ini adalah pesan percobaan (TESTING) langsung ke API Infobip menggunakan Python."
        }
    }
    
    print("Mengirim pesan ke Infobip...")
    try:
        response = requests.post(url, json=payload, headers=headers)
        
        print(f"Status Code: {response.status_code}")
        print(f"Response Body: {response.text}")
        
        if response.status_code == 200:
            print("✅ BERHASIL! Konfigurasi Infobip Anda sudah benar dan pesan telah dikirim.")
        else:
            print("❌ GAGAL! Periksa kembali URL, API Key, atau nomor tujuan Anda.")
            
    except Exception as e:
        print(f"Error koneksi sistem: {e}")

if __name__ == "__main__":
    test_send_message()