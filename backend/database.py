import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "database.db")

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    cursor = conn.cursor()
    
    # جدول کاربران
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            bronze_points INTEGER DEFAULT 1,
            gold_points INTEGER DEFAULT 0,
            diamond_points INTEGER DEFAULT 0,
            evm_wallet TEXT,
            deposit_status TEXT DEFAULT 'none',
            referred_by INTEGER
        )
    ''')
    
    # جدول آمار کل شبکه
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS global_stats (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            total_bronze_issued INTEGER DEFAULT 0,
            total_gold_issued INTEGER DEFAULT 0,
            total_diamond_issued INTEGER DEFAULT 0
        )
    ''')
    
    # مقداردهی اولیه آمار کل شبکه اگر وجود نداشته باشد
    cursor.execute('''
        INSERT OR IGNORE INTO global_stats (id, total_bronze_issued, total_gold_issued, total_diamond_issued)
        VALUES (1, 0, 0, 0)
    ''')
    
    conn.commit()
    conn.close()
