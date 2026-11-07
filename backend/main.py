import os
import io
import csv
from typing import Optional
from fastapi import FastAPI, HTTPException, Form, Depends, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, HTMLResponse, StreamingResponse
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

security = HTTPBasic()

# تنظیمات رمز عبور ادمین (می‌توانید تغییر دهید)
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "dtf_secure_password_2026"

def verify_admin(credentials: HTTPBasicCredentials = Depends(security)):
    correct_username = credentials.username == ADMIN_USERNAME
    correct_password = credentials.password == ADMIN_PASSWORD
    if not (correct_username and correct_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="نام کاربری یا رمز عبور اشتباه است",
            headers={"WWW-Authenticate": "Basic"},
        )
    return credentials.username

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
        # ثبت کاربر جدید
        cursor.execute("""
            INSERT INTO users (user_id, username, bronze_points, gold_points, diamond_points, deposit_status, referred_by) 
            VALUES (?, ?, 1, 0, 0, 'none', ?)
        """, (data.user_id, data.username, data.referrer_id))
        
        cursor.execute("UPDATE global_stats SET total_bronze_issued = total_bronze_issued + 1 WHERE id = 1")
        
        # اعطای امتیاز طلا به معرف در صورت وجود
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

# پنل مدیریت محافظت‌شده با نام کاربری و رمز عبور
@app.get("/admin", response_class=HTMLResponse)
def admin_panel(username: str = Depends(verify_admin)):
    conn = database.get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE deposit_status = 'pending'")
    pending_users = cursor.fetchall()
    
    cursor.execute("SELECT COUNT(*) as total FROM users")
    total_users_count = cursor.fetchone()['total']
    conn.close()

    rows = ""
    for u in pending_users:
        rows += f"""
        <tr style="border-bottom: 1px solid #333;">
            <td style="padding: 10px;">{u['user_id']}</td>
            <td style="padding: 10px;">{u['username']}</td>
            <td style="padding: 10px; font-family: monospace;">{u['evm_wallet'] or 'ثبت نشده'}</td>
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
            .btn-excel {{ background: #059669; color: white; padding: 10px 16px; text-decoration: none; border-radius: 8px; font-weight: bold; display: inline-block; margin-bottom: 20px; }}
            table {{ width: 100%; border-collapse: collapse; margin-top: 10px; background: #111827; border-radius: 8px; overflow: hidden; }}
            th {{ background: #1f2937; padding: 12px; text-align: right; font-size: 14px; }}
        </style>
    </head>
    <body>
        <h2>💎 پنل مدیریت پلتفرم DTF</h2>
        <p>تعداد کل کاربران ثبت‌شده: <strong>{total_users_count}</strong> نفر</p>
        
        <a href="/admin/export-excel" class="btn-excel">📊 دانلود خروجی اکسل (CSV) جهت محاسبات ایردراپ</a>

        <h3 style="color: #f59e0b; margin-top: 20px;">درخواست‌های واریز الماس در انتظار تایید:</h3>
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
def admin_approve(user_id: int = Form(...), username: str = Depends(verify_admin)):
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

@app.get("/admin/export-excel")
def export_excel(username: str = Depends(verify_admin)):
    conn = database.get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT user_id, username, evm_wallet, bronze_points, gold_points, diamond_points, deposit_status, referred_by FROM users")
    users = cursor.fetchall()
    conn.close()

    output = io.StringIO()
    writer = csv.writer(output)
    
    writer.writerow(['User ID', 'Username', 'EVM Wallet', 'Bronze Points', 'Gold Points', 'Diamond Points', 'Deposit Status', 'Referred By'])
    
    for u in users:
        writer.writerow([
            u['user_id'] or '',
            u['username'] or '',
            u['evm_wallet'] if u['evm_wallet'] else 'ثبت نشده',
            u['bronze_points'] or 0,
            u['gold_points'] or 0,
            u['diamond_points'] or 0,
            u['deposit_status'] or 'none',
            u['referred_by'] or 'ندارد'
        ])
    
    output.seek(0)
    return StreamingResponse(
        io.BytesIO(output.getvalue().encode('utf-8-sig')),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=dtf_users_airdrop_data.csv"}
    )
