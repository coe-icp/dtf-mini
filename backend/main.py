import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from . import database

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

database.init_db()

class UserRegister(BaseModel):
    user_id: int
    username: str
    referrer_id: int = None

class WalletUpdate(BaseModel):
    user_id: int
    wallet: str

class DiamondDeposit(BaseModel):
    user_id: int
    txid: str

# اتصال پوشه فرانت‌اند برای بارگذاری صحیح فایل‌ها
frontend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../frontend"))
if os.path.exists(frontend_path):
    app.mount("/static", StaticFiles(directory=frontend_path), name="static")

@app.get("/")
async def serve_home():
    index_file = os.path.join(frontend_path, "index.html")
    if os.path.exists(index_file):
        return FileResponse(index_file)
    return {"status": "DTF Mini App Backend is running"}

@app.post("/api/init")
def init_user(data: UserRegister):
    conn = database.get_db()
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM users WHERE user_id = ?", (data.user_id,))
    user = cursor.fetchone()
    
    if not user:
        cursor.execute("""
            INSERT INTO users (user_id, username, bronze_points, gold_points, diamond_points, deposit_status, referred_by) 
            VALUES (?, ?, 1, 0, 0, 'none', ?)
        """, (data.user_id, data.username, data.referrer_id))
        
        cursor.execute("UPDATE global_stats SET total_bronze_issued = total_bronze_issued + 1 WHERE id = 1")
        
        if data.referrer_id and data.referrer_id != data.user_id:
            cursor.execute("SELECT user_id FROM users WHERE user_id = ?", (data.referrer_id,))
            if cursor.fetchone():
                cursor.execute("UPDATE users SET gold_points = gold_points + 1 WHERE user_id = ?", (data.referrer_id,))
                cursor.execute("UPDATE global_stats SET total_gold_issued = total_gold_issued + 1 WHERE id = 1")
                
        conn.commit()
        cursor.execute("SELECT * FROM users WHERE user_id = ?", (data.user_id,))
        user = cursor.fetchone()

    cursor.execute("SELECT * FROM global_stats WHERE id = 1")
    stats = cursor.fetchone()
    conn.close()
    
    return {
        "user": dict(user),
        "global_stats": {
            "total_bronze": stats["total_bronze_issued"],
            "total_gold": stats["total_gold_issued"],
            "total_diamond": stats["total_diamond_issued"]
        }
    }

@app.post("/api/wallet")
def update_wallet(data: WalletUpdate):
    conn = database.get_db()
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET evm_wallet = ? WHERE user_id = ?", (data.wallet, data.user_id))
    conn.commit()
    conn.close()
    return {"status": "success"}

@app.post("/api/deposit-diamond")
def deposit_diamond(data: DiamondDeposit):
    conn = database.get_db()
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET deposit_status = 'pending' WHERE user_id = ?", (data.user_id,))
    conn.commit()
    conn.close()
    return {"status": "pending"}
