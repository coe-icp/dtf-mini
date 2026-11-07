import sqlite3
import os

DB_PATH = os.environ.get("DB_PATH", os.path.join(os.path.dirname(__file__), "database.db"))


def get_db():
    # check_same_thread=False لازم است چون FastAPI اندپوینت‌ها را در thread‌های مختلف اجرا می‌کند
    conn = sqlite3.connect(DB_PATH, timeout=10, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    db_dir = os.path.dirname(DB_PATH)
    if db_dir:
        os.makedirs(db_dir, exist_ok=True)

    print(f"[DTF] Database path: {DB_PATH}", flush=True)

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
            referred_by INTEGER,
            created_at TIMESTAMP
        )
    ''')

    # مهاجرت: اگر جدول قدیمی است و ستون created_at ندارد، اضافه کن
    cursor.execute("PRAGMA table_info(users)")
    columns = [row["name"] for row in cursor.fetchall()]
    if "created_at" not in columns:
        cursor.execute("ALTER TABLE users ADD COLUMN created_at TIMESTAMP")

    cursor.execute("CREATE INDEX IF NOT EXISTS idx_users_referred_by ON users(referred_by)")

    # جدول تراکنش‌ها و رسیدهای الماس
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS deposits (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            txid TEXT UNIQUE,
            status TEXT DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
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

    cursor.execute('''
        INSERT OR IGNORE INTO global_stats (id, total_bronze_issued, total_gold_issued, total_diamond_issued)
        VALUES (1, 0, 0, 0)
    ''')

    conn.commit()
    conn.close()
