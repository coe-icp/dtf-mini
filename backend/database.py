import sqlite3

def init_db():
    conn = sqlite3.connect('dtf_miniapp.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            evm_wallet TEXT,
            bronze_points INTEGER DEFAULT 1,
            gold_points INTEGER DEFAULT 0,
            diamond_points INTEGER DEFAULT 0,
            deposit_status TEXT DEFAULT 'none',
            referred_by INTEGER
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS global_stats (
            id INTEGER PRIMARY KEY,
            total_bronze_issued INTEGER DEFAULT 0,
            total_gold_issued INTEGER DEFAULT 0,
            total_diamond_issued INTEGER DEFAULT 0
        )
    ''')
    cursor.execute('SELECT COUNT(*) FROM global_stats')
    if cursor.fetchone()[0] == 0:
        cursor.execute('INSERT INTO global_stats (id, total_bronze_issued, total_gold_issued, total_diamond_issued) VALUES (1, 0, 0, 0)')
    
    conn.commit()
    conn.close()

def get_db():
    conn = sqlite3.connect('dtf_miniapp.db')
    conn.row_factory = sqlite3.Row
    return conn
