import os
from openai import AzureOpenAI
from dotenv import load_dotenv

load_dotenv()

client = AzureOpenAI(
    azure_endpoint=os.getenv("OPENAI_ENDPOINT"),
    api_key=os.getenv("OPENAI_API_KEY"),
    api_version="2024-02-01-preview"
)
deployment_name = os.getenv("OPENAI_DEPLOYMENT_NAME")

SYSTEM_PROMPT = """
Anda adalah asisten virtual cerdas untuk sebuah toko retail yang menggunakan sistem kasir canggih.
Tugas Anda adalah melayani pelanggan yang menghubungi via WhatsApp dengan ramah, sopan, dan profesional.

Informasi Penting Toko:
- Jam Buka: Senin - Sabtu (08:00 - 20:00), Minggu (Tutup).
- Lokasi: Jalan Merdeka No. 123, Jakarta.

Aturan Membalas:
1. Berikan jawaban yang singkat, padat, dan ramah (gunakan emoji secukupnya).
2. Jika pelanggan bertanya hal di luar konteks toko, tolak dengan sopan dan kembalikan topik ke layanan toko.
3. Anda belum terhubung ke database stok barang saat ini. Jika ditanya soal stok, katakan bahwa Anda akan segera dilengkapi dengan fitur tersebut.
"""

def get_ai_response(user_text: str, sender_number: str) -> str:
    """Mengirim pesan pengguna ke Azure OpenAI dan mengembalikan teks balasannya."""
    
    try:
        response = client.chat.completions.create(
            model=deployment_name,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_text}
            ],
            max_tokens=150,    
            temperature=0.7    
        )
        
        ai_reply = response.choices[0].message.content
        return ai_reply
        
    except Exception as e:
        print(f"Error pada Azure OpenAI: {e}")
        return "Mohon maaf kak, sistem asisten kami sedang beristirahat sejenak. Silakan hubungi kami beberapa saat lagi ya. 🙏"