import os
from datetime import datetime, timedelta, timezone
from openai import AzureOpenAI
from dotenv import load_dotenv

load_dotenv()

client = AzureOpenAI(
    api_version="2024-12-01-preview",
    azure_endpoint=os.getenv("OPENAI_ENDPOINT"),
    api_key=os.getenv("OPENAI_API_KEY"),
)

WIB = timezone(timedelta(hours=7))

user_database = {}

# ==========================================
# FUNGSI: MENGATUR STATUS AI (ON/OFF)
# ==========================================
def toggle_ai(sender_number: str, turn_off: bool):
    now = datetime.now(WIB)
    if sender_number not in user_database:
        user_database[sender_number] = {
            "last_seen": None,
            "blocked_until": None,
            "spam_count": 0,
            "spam_timer": now,
            "is_ai_off": turn_off,
            "ai_off_timestamp": now if turn_off else None 
        }
    else:
        user_database[sender_number]["is_ai_off"] = turn_off
        user_database[sender_number]["ai_off_timestamp"] = now if turn_off else None


def get_ai_response(user_text: str, sender_number: str) -> str:
    now = datetime.now(WIB)
    
    if sender_number not in user_database:
        user_database[sender_number] = {
            "last_seen": None,
            "blocked_until": None,
            "spam_count": 0,
            "spam_timer": now,
            "is_ai_off": False,
            "ai_off_timestamp": None
        }
    
    user = user_database[sender_number]

    # ==========================================
    # FILTER 0: CEK AI MATI & AUTO-WAKEUP 12 JAM
    # ==========================================
    if user.get("is_ai_off", False):
        off_time = user.get("ai_off_timestamp")
        if off_time and (now - off_time) > timedelta(hours=12):
            user["is_ai_off"] = False
            user["ai_off_timestamp"] = None
            print(f"🔄 [Sistem] AI otomatis dihidupkan kembali untuk {sender_number} karena sudah > 12 jam.")
        else:
            return "SILENT_IGNORE"

    # ==========================================
    # FILTER 1: CEK APAKAH SEDANG DIBLOKIR / DI-HANDOVER
    # ==========================================
    if user["blocked_until"] and now < user["blocked_until"]:
        return "SILENT_IGNORE"

    # ==========================================
    # FILTER 2: ANTI-SPAM (Rate Limiting)
    # ==========================================
    if now > user["spam_timer"]:
        user["spam_count"] = 1
        user["spam_timer"] = now + timedelta(minutes=1)
    else:
        user["spam_count"] += 1
        if user["spam_count"] > 4:
            user["blocked_until"] = now + timedelta(minutes=15)
            return "Sistem mendeteksi terlalu banyak pesan. Fitur asisten otomatis dijeda sementara. 🙏"

    # ==========================================
    # FILTER 3: DETEKSI STATUS JAM OPERASIONAL
    # ==========================================
    current_hour = now.hour
    is_closed = current_hour < 7 or current_hour >= 19
    current_time_str = now.strftime('%H:%M WIB')

    # ==========================================
    # FILTER 4: LOGIKA PELANGGAN BARU
    # ==========================================
    is_new_customer = False
    if user["last_seen"] is None:
        is_new_customer = True
    elif (now - user["last_seen"]).days >= 14:
        is_new_customer = True

    user["last_seen"] = now

    # ==========================================
    # FILTER 5: MERAKIT INSTRUKSI (PROMPT) KE AI
    # ==========================================
    base_prompt = (
        "Anda adalah Artificial Intelligence (AI) asisten dari toko 'Barokah Copy & Printing' yang ramah, hangat, dan cerdas. "
        "Jawablah dengan singkat dan tidak bertele-tele. "
        "ATURAN FORMAT JAWABAN KAMU: Kamu WAJIB menggunakan spasi antar paragraf (baris kosong/enter ganda) untuk memisahkan sapaan, informasi utama, dan penutup agar pesan rapi dan mudah dibaca di layar HP. "
        "ATURAN LINK: DILARANG KERAS menggunakan format markdown untuk tautan (seperti [teks](url)). Tuliskan URL secara mentah/polos saja.\n"
    )
    
    if is_new_customer:
        base_prompt += "PENGGUNA INI PELANGGAN BARU. Awali pesanmu dengan memperkenalkan diri secara singkat bahwa namamu adalah 'Whitehat' dalam satu paragraf tersendiri.\n"

    base_prompt += (
        "INFORMASI LAYANAN TOKO: Jika pelanggan bertanya tentang layanan, apa yang dijual, atau apa yang bisa dilakukan di toko, beritahu bahwa toko melayani: "
        "Foto Copy, Print Copy, Foto copy dan print copy bolak balik, Print Warna, Print bolak balik, Cetak Foto, Copy Warna, Laminating dokumen, Press dokumen, Scan dokumen, Jilid, dan Menjual Aneka ATK. "
        "Kamu bisa menyebutkan layanan ini dalam bentuk poin-poin yang rapi jika diminta.\n"
    )

    base_prompt += (
        "ATURAN LOKASI: Jika pelanggan menanyakan alamat, lokasi, atau meminta 'shareloc', "
        "kamu WAJIB memberikan tautan ini: https://share.google/AOwTPRhnMygxfk60S "
        "Ingat, tuliskan URL mentahnya saja, JANGAN gunakan tanda kurung siku atau format markdown. "
        "Setelah itu, sarankan juga mereka untuk mencari 'Barokah Copy & Printing' di aplikasi Google Maps. "
        "Jika user tidak menanyakan alamat atau lokasi kamu dilarang memberikan informasi tentang lokasi baik berupa link atau saran pencarian.\n"
    )

    if is_closed:
        base_prompt += (
            f"STATUS TOKO: TUTUP. Saat ini jam menunjukkan pukul {current_time_str}. (Jam buka: 07:00 - 19:00 WIB). "
            "TUGASMU: Beritahu pelanggan dengan sangat ramah bahwa toko sedang tutup. "
            "Sesuaikan sapaanmu dengan waktu. "
            "TOLAK permintaan cek harga/stok atau belanja dengan halus, dan persilakan mereka menghubungi kembali pada jam buka. "
            "Pastikan informasi toko tutup dipisah ke dalam paragraf yang berbeda.\n"
        )
    else:
        base_prompt += (
            f"STATUS TOKO: BUKA. Saat ini jam menunjukkan pukul {current_time_str}. "
            "PENTING: Jika pengguna menanyakan hal di luar konteks belanja atau sapaan wajar, tolaklah menjawab dengan halus.\n"
            "ATURAN KHUSUS: Karena database toko belum terhubung, kamu TIDAK BISA mengecek stok atau harga. "
            "Oleh karena itu, jika niat pelanggan adalah menanyakan HARGA, STOK BARANG, atau INGIN MEMESAN, "
            "kamu WAJIB membalas pesan HANYA dengan satu kode rahasia ini: ESKALASI_ADMIN. "
            "Jangan tambahkan kata apa pun selain ESKALASI_ADMIN."
        )

    # ==========================================
    # EKSEKUSI KE AZURE OPENAI & POST-PROCESSING
    # ==========================================
    try:
        response = client.chat.completions.create(
            messages=[
                {"role": "system", "content": base_prompt},
                {"role": "user", "content": user_text}
            ],
            model=os.getenv("OPENAI_DEPLOYMENT_NAME"),
            max_tokens=250,
            temperature=0.6
        )
        
        ai_reply = response.choices[0].message.content.strip()

        if "ESKALASI_ADMIN" in ai_reply:
            user["blocked_until"] = now + timedelta(hours=1)
            return "Terkait info produk, stok, atau harga, Admin Toko kami akan membalas pesan kakak secara manual sesaat lagi ya. Mohon ditunggu... 👨‍💻\n*(Asisten AI dijeda 1 jam)*"

        return ai_reply

    except Exception as e:
        print(f"❌ Error pada Azure OpenAI: {e}")
        return "Mohon maaf kak, sistem asisten kami sedang gangguan sesaat. 🙏"