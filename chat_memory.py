import sys
import sqlite3
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

DB_NAME = "chat_history.db"

def init_chat_db():
    """Membuat tabel history jika belum ada."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sender_number TEXT,
            role TEXT,
            message TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()

def save_chat_message(sender_number: str, role: str, message: str):
    """Menyimpan satu baris pesan ke memori SQLite."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO history (sender_number, role, message) VALUES (?, ?, ?)",
        (sender_number, role, message)
    )
    conn.commit()
    conn.close()

def get_recent_chat_history(sender_number: str, limit: int = 10) -> list:
    """Mengambil riwayat percakapan terakhir (default: 10 pesan terakhir)."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
        SELECT role, message FROM history 
        WHERE sender_number = ? 
        ORDER BY timestamp DESC LIMIT ?
    ''', (sender_number, limit))
    rows = cursor.fetchall()
    conn.close()
    
    history = [{"role": row[0], "content": row[1]} for row in reversed(rows)]
    return history

def cleanup_old_history(days: int = 3):
    """Menghapus baris chat yang usianya sudah lebih dari X hari dari sekarang."""
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute(f"DELETE FROM history WHERE timestamp <= datetime('now', '-{days} days')")
        deleted_rows = cursor.rowcount
        conn.commit()
        conn.close()
        
        if deleted_rows > 0:
            logger.info(f"🧹 Membersihkan {deleted_rows} pesan lama (> {days} hari) dari memori AI.")
    except Exception as e:
        logger.info(f"❌ Error saat membersihkan history lama: {e}")