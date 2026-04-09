import os
import time
import pymssql
from dotenv import load_dotenv

load_dotenv()

DB_SERVER = os.getenv("DB_SERVER")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_NAME = os.getenv("DB_NAME")

def test_db_wakeup():
    print("=== MENGUJI WAKTU BANGUN AZURE SQL DATABASE ===")
    print(f"Menghubungi Server: {DB_SERVER}")
    print("Mulai menghitung waktu...\n")
    
    start_time = time.time()
    attempt = 1
    
    while True:
        elapsed_time = time.time() - start_time
        
        try:
            print(f"[{elapsed_time:.1f} detik] Percobaan {attempt}: Mengetuk pintu database...")
            
            conn = pymssql.connect(
                server=DB_SERVER, 
                user=DB_USER, 
                password=DB_PASSWORD, 
                database=DB_NAME,
                timeout=5,
                login_timeout=5
            )
            
            cursor = conn.cursor()
            cursor.execute("SELECT 1")
            cursor.fetchone()
            conn.close()
            
            finish_time = time.time()
            total_time = finish_time - start_time
            
            print("\n✅ KONEKSI BERHASIL!")
            print(f"Database sudah terbangun dan merespon.")
            print(f"⏱️ TOTAL WAKTU BANGUN: {total_time:.2f} detik")
            break
            
        except Exception as e:
            error_msg = str(e).split('\\n')[0].strip()
            print(f"   -> Gagal (Masih tidur). Info: {error_msg}")
            
            if elapsed_time > 180:
                print("\n❌ WAKTU HABIS! Database tidak bangun setelah 3 menit.")
                print("Pastikan Firewall Azure sudah terbuka untuk IP Anda dan kredensial .env benar.")
                break
            
            time.sleep(3)
            attempt += 1

if __name__ == "__main__":
    if not DB_SERVER:
        print("❌ Error: File .env tidak ditemukan atau variabel DB_SERVER kosong.")
    else:
        test_db_wakeup()