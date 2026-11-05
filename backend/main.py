import os
from typing import Optional
from fastapi import FastAPI, HTTPException, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel
from . import database

# اول متغیر app تعریف می‌شود
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
    referrer_id: Optional[int] = None

class WalletUpdate(BaseModel):
    user_id: int
    wallet: str

class DiamondDeposit(BaseModel):
    user_id: int
    txid: str

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
            referrer_exists = cursor.fetchone()
            
            if referrer_exists:
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
    cursor.execute("""
        UPDATE users 
        SET deposit_status = CASE WHEN deposit_status != 'approved' THEN 'pending' ELSE deposit_status END,
            evm_wallet = COALESCE(evm_wallet, ?) 
        WHERE user_id = ?
    """, (data.txid, data.user_id))
    conn.commit()
    conn.close()
    return {"status": "pending"}

@app.get("/admin", response_class=HTMLResponse)
def admin_panel():
    conn = database.get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE deposit_status = 'pending'")
    pending_users = cursor.fetchall()
    conn.close()

    rows = ""
    for u in pending_users:
        rows += f"""
        <tr style="border-bottom: 1px solid #333;">
            <td style="padding: 10px;">{u['user_id']}</td>
            <td style="padding: 10px;">{u['username']}</td>
            <td style="padding: 10px; font-family: monospace;">{u['evm_wallet']}</td>
            <td style="padding: 10px;">
                <form action="/admin/approve" method="POST" style="display:inline;">
                    <input type="hidden" name="user_id" value="{u['user_id']}">
                    <button type="submit" style="background: #10B981; color: white; border: none; padding: 6px 12px; border-radius: 6px; cursor: pointer; font-weight: bold;">تایید و اعطای الماس ✅</button>
                </form>
            </td>
        </tr>
        """

    html = f"""
    <!DOCTYPE html>
    <html lang="fa" dir="rtl">
    <head>
        <meta charset="UTF-8">
        <title>پنل مدیریت DTF</title>
        <style>
            body {{ background: #090d16; color: #fff; font-family: Tahoma, sans-serif; padding: 20px; }}
            h2 {{ color: #38bdf8; }}
            table {{ width: 100%; border-collapse: collapse; margin-top: 20px; background: #111827; border-radius: 8px; overflow: hidden; }}
            th {{ background: #1f2937; padding: 12px; text-align: right; font-size: 14px; }}
        </style>
    </head>
    <body>
        <h2>💎 پنل مدیریت و تایید واریزی‌های الماس</h2>
        <p>کاربرانی که درخواست واریز ثبت کرده‌اند و منتظر تایید هستند:</p>
        <table>
            <tr>
                <th>شناسه کاربری (ID)</th>
                <th>نام کاربری</th>
                <th>آدرس کیف پول / هش تراکنش</th>
                <th>عملیات</th>
            </tr>
            {rows if rows else '<tr><td colspan="4" style="text-align:center; padding: 20px; color: #888;">هیچ درخواست در انتظاری وجود ندارد.</td></tr>'}
        </table>
    </body>
    </html>
    """
    return html

@app.post("/admin/approve")
def admin_approve(user_id: int = Form(...)):
    conn = database.get_db()
    cursor = conn.cursor()
    
    cursor.execute("SELECT diamond_points, deposit_status FROM users WHERE user_id = ?", (user_id,))
    u = cursor.fetchone()
    
    if u and u['deposit_status'] != 'approved':
        cursor.execute("UPDATE users SET deposit_status = 'approved', diamond_points = diamond_points + 1 WHERE user_id = ?", (user_id,))
        cursor.execute("UPDATE global_stats SET total_diamond_issued = total_diamond_issued + 1 WHERE id = 1")
        conn.commit()
        
    conn.close()
    return HTMLResponse(content="<script>alert('با موفقیت تایید شد!'); window.location.href='/admin';</script>")
