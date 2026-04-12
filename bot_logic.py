import sys
import psycopg2
from psycopg2 import errors
import os
import time
import logging
from datetime import datetime, timedelta, timezone
from openai import AzureOpenAI
from dotenv import load_dotenv

load_dotenv()

from chat_memory import save_chat_message, get_recent_chat_history

try:
    db_pool = psycopg2.pool.SimpleConnectionPool(
        1, 10, os.getenv("DATABASE_URL")
    )
    if db_pool:
        logger.info("✅ Connection pool ke Supabase berhasil dibuat.")
except Exception as e:
    logger.error(f"❌ Gagal membuat connection pool: {e}")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

client = AzureOpenAI(
    api_version="2024-12-01-preview",
    azure_endpoint=os.getenv("OPENAI_ENDPOINT"),
    api_key=os.getenv("OPENAI_API_KEY"),
)

WIB = timezone(timedelta(hours=7))

global_settings = {
    "is_temporary_closed": False,
    "reopen_info": None
}

def set_global_closed(status: bool, reopen_info: str = None):
    """Mengatur status tutup sementara secara global beserta info kapan buka kembali"""
    global_settings["is_temporary_closed"] = status
    global_settings["reopen_info"] = reopen_info if status else None

DB_SERVER = os.getenv("DB_SERVER")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_NAME = os.getenv("DB_NAME")

def get_db_connection():
    return db_pool.getconn()

def ensure_db_ready(max_retries=15, wait_time=2) -> bool:
    """Mengecek akses database saat startup."""
    for attempt in range(1, max_retries + 1):
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT 1")
            cursor.fetchone()
            cursor.close()
            conn.close()
            
            init_db()
            return True
            
        except Exception as e:
            logger.warning(f"⏳ DB belum siap (Percobaan {attempt}/{max_retries}). Menunggu...")
            time.sleep(wait_time)
            
    return False

def init_db():
    """Inisialisasi tabel di PostgreSQL secara aman."""
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                sender_number VARCHAR(50) PRIMARY KEY,
                last_seen VARCHAR(50),
                blocked_until VARCHAR(50),
                spam_count INT DEFAULT 0,
                spam_timer VARCHAR(50),
                is_ai_off INT DEFAULT 0,
                ai_off_timestamp VARCHAR(50),
                is_excluded INT DEFAULT 0
            );
        ''')
        conn.commit()
        cursor.close()
        logger.info("📑 Struktur tabel 'users' diverifikasi.")
    except Exception as e:
        logger.error(f"❌ Gagal inisialisasi tabel: {e}")
        if conn:
            conn.rollback()
    finally:
        if conn:
            db_pool.putconn(conn)

def get_user(sender_number: str) -> dict:
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE sender_number=%s", (sender_number,))
        row = cursor.fetchone()
        conn.close()
    except errors.UndefinedTable:
        logger.info("🔧 Tabel belum ada di Supabase. Membuat tabel otomatis (Auto-heal)...")
        conn.rollback()
        init_db() 
        return get_user(sender_number)
    except Exception as e:
        raise e
    
    if row is None:
        return None
    
    return {
        "last_seen": datetime.fromisoformat(row[1]) if row[1] else None,
        "blocked_until": datetime.fromisoformat(row[2]) if row[2] else None,
        "spam_count": row[3],
        "spam_timer": datetime.fromisoformat(row[4]) if row[4] else None,
        "is_ai_off": bool(row[5]),
        "ai_off_timestamp": datetime.fromisoformat(row[6]) if row[6] else None,
        "is_excluded": bool(row[7])
    }

def save_user(sender_number: str, user: dict):
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        last_seen_str = user["last_seen"].isoformat() if user.get("last_seen") else None
        blocked_until_str = user["blocked_until"].isoformat() if user.get("blocked_until") else None
        spam_timer_str = user["spam_timer"].isoformat() if user.get("spam_timer") else None
        ai_off_timestamp_str = user["ai_off_timestamp"].isoformat() if user.get("ai_off_timestamp") else None
        
        p_spam = user.get("spam_count", 0)
        p_ai_off = 1 if user.get("is_ai_off") else 0
        p_excluded = 1 if user.get("is_excluded") else 0

        query = '''
            INSERT INTO users (sender_number, last_seen, blocked_until, spam_count, spam_timer, is_ai_off, ai_off_timestamp, is_excluded) 
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (sender_number) 
            DO UPDATE SET 
                last_seen = EXCLUDED.last_seen,
                blocked_until = EXCLUDED.blocked_until,
                spam_count = EXCLUDED.spam_count,
                spam_timer = EXCLUDED.spam_timer,
                is_ai_off = EXCLUDED.is_ai_off,
                ai_off_timestamp = EXCLUDED.ai_off_timestamp,
                is_excluded = EXCLUDED.is_excluded;
        '''
        
        cursor.execute(query, (
            sender_number, last_seen_str, blocked_until_str, p_spam, spam_timer_str, p_ai_off, ai_off_timestamp_str, p_excluded
        ))
        
        conn.commit()
        cursor.close()
    except Exception as e:
        if conn:
            conn.rollback()
        logger.error(f"❌ Error saat save_user untuk {sender_number}: {e}")
    finally:
        if conn:
            db_pool.putconn(conn)

def set_permanent_exclude(sender_number: str, status: bool):
    """Mengatur pengecualian AI secara permanen untuk nomor tertentu"""
    now = datetime.now(WIB)
    user = get_user(sender_number)
    if user is None:
        user = {
            "last_seen": None,
            "blocked_until": None,
            "spam_count": 0,
            "spam_timer": now - timedelta(minutes=1),
            "is_ai_off": False,
            "ai_off_timestamp": None,
            "is_excluded": status
        }
    else:
        user["is_excluded"] = status
    save_user(sender_number, user)

def toggle_ai(sender_number: str, turn_off: bool):
    now = datetime.now(WIB)
    user = get_user(sender_number)
    if user is None:
        user = {
            "last_seen": None,
            "blocked_until": None,
            "spam_count": 0,
            "spam_timer": now - timedelta(minutes=1),
            "is_ai_off": turn_off,
            "ai_off_timestamp": now if turn_off else None,
            "is_excluded": False
        }
    else:
        user["is_ai_off"] = turn_off
        user["ai_off_timestamp"] = now if turn_off else None
    save_user(sender_number, user)


def get_ai_response(user_text: str, sender_number: str) -> str:
    now = datetime.now(WIB)
    
    user = get_user(sender_number)
    if user is None:
        user = {
            "last_seen": None,
            "blocked_until": None,
            "spam_count": 0,
            "spam_timer": now - timedelta(minutes=1),
            "is_ai_off": False,
            "ai_off_timestamp": None,
            "is_excluded": False
        }

    if user.get("is_excluded", False):
        save_user(sender_number, user)
        return "SILENT_IGNORE"

    save_chat_message(sender_number, "user", user_text)

    if user_text == "client_dokument":
        return "SILENT_IGNORE"

    # ==========================================
    # FILTER 0: CEK AI MATI & AUTO-WAKEUP 12 JAM
    # ==========================================
    if user.get("is_ai_off", False):
        off_time = user.get("ai_off_timestamp")
        if off_time and (now - off_time) > timedelta(hours=12):
            user["is_ai_off"] = False
            user["ai_off_timestamp"] = None
            logger.info(f"🔄 [Sistem] AI otomatis dihidupkan kembali untuk {sender_number} karena sudah > 12 jam.")
        else:
            save_user(sender_number, user)
            return "SILENT_IGNORE"

    # ==========================================
    # FILTER 1: CEK APAKAH SEDANG DIBLOKIR / DI-HANDOVER
    # ==========================================
    if user["blocked_until"] and now < user["blocked_until"]:
        save_user(sender_number, user)
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
            user["blocked_until"] = now + timedelta(minutes=59)
            save_user(sender_number, user)
            return "Sistem mendeteksi terlalu banyak pesan. Fitur asisten otomatis dijeda sementara. 🙏"

    # ==========================================
    # FILTER 3: DETEKSI STATUS JAM OPERASIONAL
    # ==========================================
    current_hour = now.hour
    is_closed = current_hour < 7 or current_hour >= 19
    current_time_str = now.strftime('%H:%M WIB')

    open_time = now.replace(hour=7, minute=0, second=0, microsecond=0)
    close_time = now.replace(hour=19, minute=0, second=0, microsecond=0)

    if is_closed:
        if current_hour >= 19:
            next_open = open_time + timedelta(days=1)
        else:
            next_open = open_time
        delta = next_open - now
    else:
        delta = close_time - now
        
    hours, remainder = divmod(delta.seconds, 3600)
    minutes, _ = divmod(remainder, 60)

    sisa_waktu_str = ""
    if hours > 0 and minutes > 0:
        sisa_waktu_str = f"{hours} jam {minutes} menit"
    elif hours > 0:
        sisa_waktu_str = f"{hours} jam"
    else:
        sisa_waktu_str = f"{minutes} menit"

    # ==========================================
    # FILTER 4: LOGIKA PELANGGAN BARU
    # ==========================================
    is_new_customer = False
    if user["last_seen"] is None:
        is_new_customer = True
    elif (now - user["last_seen"]).days >= 7:
        is_new_customer = True

    user["last_seen"] = now

    # ==========================================
    # FILTER 5: MERAKIT INSTRUKSI (PROMPT) KE AI
    # ==========================================
    base_prompt = ("")

    if global_settings["is_temporary_closed"]:
        current_time_str = now.strftime('%H:%M WIB')
        reopen_info = global_settings["reopen_info"]
        info_tambahan = ""

        if reopen_info:
            info_tambahan = f"Toko akan buka kembali: {reopen_info}."
        else:
            info_tambahan = "Admin sedang keluar sebentar ada urusan mendesak."

        base_prompt = (
            "Anda adalah Artificial Intelligence (AI) asisten dari toko 'Barokah Copy & Printing' yang ramah, hangat, dan cerdas. "
            f"INFORMASI PENTING: Saat ini jam {current_time_str}. Toko sedang TUTUP SEMENTARA. {info_tambahan} "
            "TUGAS ANDA: Beritahu pelanggan dengan bahasa yang sangat ramah, hangat, dan sopan bahwa admin sedang tidak di tempat. "
            "Minta mereka menunggu sebentar atau menghubungi lagi nanti. Jangan menerima pesanan atau cek harga sekarang. "
            "ATURAN FORMAT: Gunakan spasi antar paragraf agar rapi. "
        )
    else:
        base_prompt = (
            "Anda adalah Artificial Intelligence (AI) asisten dari toko 'Barokah Copy & Printing' yang ramah, hangat, dan cerdas. "
            "Anda saat ini sedang merespon customer melalui saluran whatsapp resmi toko. "
            "Jawablah dengan singkat dan tidak bertele-tele. "
            "ATURAN FORMAT JAWABAN KAMU: Kamu WAJIB menggunakan spasi antar paragraf (baris kosong/enter ganda) untuk memisahkan sapaan, informasi utama, dan penutup agar pesan rapi dan mudah dibaca di layar HP. "
            "ATURAN LINK: DILARANG KERAS menggunakan format markdown untuk tautan (seperti [teks](url)). Tuliskan URL secara mentah/polos saja.\n"
            "ARURAN DOKUMEN: client_dokument adalah dokumen yang dikirimkan oleh customer. admin_dokument adalah dokumen dari admin. \n"
        )

        base_prompt += (
            "INFORMASI LAYANAN TOKO: Jika pelanggan bertanya tentang layanan, apa yang dijual, atau apa yang bisa dilakukan di toko, beritahu bahwa toko melayani: "
            "Foto Copy, Print Copy, Foto copy dan print copy bolak balik, Print Warna, Print bolak balik, Cetak Foto, Copy Warna, Laminating dokumen, Press dokumen, Scan dokumen, Jilid, dan Menjual Aneka ATK. "
            "Kamu bisa menyebutkan layanan ini dalam bentuk poin-poin yang rapi jika diminta.\n"
            "jika customer ingin melakukan cetak foto atau print tetapi belum mengirimkan file kamu bisa memberitahu customer untuk mengirimkan file terlebih dahulu, agar bisa diproses oleh admin. "
            "jika customer sudah mengirimkan file maka kamu bisa memberitahu customer untuk menunggu, katakan bahwa sebentar lagi pesanan akan dikerjakan. "
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
                f"INFORMASI WAKTU: Toko akan BUKA kembali dalam {sisa_waktu_str} lagi. "
                "TUGASMU: Beritahu pelanggan dengan sangat ramah bahwa toko sedang tutup. "
                "Jika pelanggan bertanya kapan toko buka setelah jam 6 pagi, gunakan informasi sisa waktu tersebut untuk menjawab secara natural (contoh: 'sekitar 30 menit lagi ya kak'). "
                "TOLAK permintaan cek harga/stok atau belanja dengan halus, dan persilakan mereka menghubungi kembali pada jam buka. "
                "Pastikan informasi toko tutup dipisah ke dalam paragraf yang berbeda.\n"
            )
        else:
            base_prompt += (
                f"STATUS TOKO: BUKA. Saat ini jam menunjukkan pukul {current_time_str}. "
                f"INFORMASI WAKTU: Toko akan TUTUP dalam {sisa_waktu_str} lagi (Jam operasional berakhir pukul 19:00 WIB). "
                "Jika pelanggan bertanya sampai jam berapa toko buka, kamu bisa memberikan estimasi sisa waktu tersebut secara natural agar mereka segera bersiap. "
                "PENTING: Jika pengguna menanyakan hal di luar konteks belanja atau sapaan wajar, tolaklah menjawab dengan halus.\n"
                "ATURAN KHUSUS: Karena database toko belum terhubung, kamu TIDAK BISA mengecek stok atau harga. "
                "Oleh karena itu, jika niat pelanggan adalah menanyakan HARGA, STOK BARANG, atau INGIN MEMESAN, "
                "kamu WAJIB membalas pesan HANYA dengan satu kode rahasia ini: ESKALASI_ADMIN. "
                "Jangan tambahkan kata apa pun selain ESKALASI_ADMIN."
            )

    if is_new_customer:
        base_prompt += "PENGGUNA INI PELANGGAN BARU. Awali pesanmu dengan memperkenalkan diri secara singkat bahwa namamu adalah 'Whitehat' dalam satu paragraf tersendiri.\n"
    else:
        base_prompt+= "kamu tidak perlu menyapa terlebih dahulu, langsung berikan jawaban sesuai dengan apa yang dibutuhkan oleh customer dengan ramah, ceria, dan cerdas.\n"
    
    base_prompt += (
        "Diakhir baris Jawaban Kamu kamu wajib menambahkan footer, gunakan baris sendiri dibawah kalimat penutup kamu. " 
        "ATURAN FOOTER: Kamu WAJIB menyertakan informasi kepada customer bahwa untuk mematikan fitur AI Respon cukup ketik /matikan_ai, sampaikan dengan singkat dan ceria.\n"
        "ATURAN SPAM: jika kamu mendeteksi customer melakukan spam kamu wajib membalas dengan kode rahasia ini: SPAM_DETECT. Jangan tambahkan kata apapun selain SPAM_DETECT. "
        "JANGAN deteksi spam jika customer mengirimkan banyak dokumen. "
    )

    # ==========================================
    # EKSEKUSI KE AZURE OPENAI & POST-PROCESSING
    # ==========================================
    try:

        chat_history = get_recent_chat_history(sender_number, limit=10)

        messages = [{"role": "system", "content": base_prompt}]
        messages.extend(chat_history)

        response = client.chat.completions.create(
            messages=messages,
            model=os.getenv("OPENAI_DEPLOYMENT_NAME"),
            max_tokens=250,
            temperature=0.6
        )
        
        ai_reply = response.choices[0].message.content.strip()

        if "ESKALASI_ADMIN" in ai_reply:
            user["blocked_until"] = now + timedelta(hours=1)
            save_user(sender_number, user)
            eskalasi_msg = "Terkait info produk, stok, atau harga, Admin Toko kami akan membalas pesan kakak secara manual sesaat lagi ya. Mohon ditunggu... 👨‍💻\n*(Asisten AI dijeda 1 jam)*"
            
            save_chat_message(sender_number, "assistant", eskalasi_msg)
            return eskalasi_msg

        save_user(sender_number, user)
        
        save_chat_message(sender_number, "assistant", ai_reply)
        
        return ai_reply

    except Exception as e:
        logger.info(f"❌ Error pada Azure OpenAI: {e}")
        save_user(sender_number, user)
        return "Mohon maaf kak, sistem asisten kami sedang gangguan sesaat. 🙏"