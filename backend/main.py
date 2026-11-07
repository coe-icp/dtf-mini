import os
import io
import csv
import re
import hmac
import json
import time
import html
import hashlib
import secrets
import logging
import sqlite3
from typing import Optional
from urllib.parse import parse_qsl

from fastapi import FastAPI, HTTPException, Form, Depends, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, HTMLResponse, StreamingResponse, RedirectResponse
from pydantic import BaseModel
from . import database

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("dtf")

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

database.init_db()

security = HTTPBasic()

ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD")
BOT_TOKEN = os.environ.get("BOT_TOKEN")
INIT_DATA_MAX_AGE = 24 * 60 * 60  # اعتبار initData: ۲۴ ساعت

try:
    ADMIN_TELEGRAM_ID = int(os.environ.get("ADMIN_TELEGRAM_ID", ""))
except ValueError:
    ADMIN_TELEGRAM_ID = None

if not BOT_TOKEN:
    logger.warning("BOT_TOKEN تنظیم نشده! احراز هویت تلگرام غیرفعال است و هر کسی می‌تواند هویت جعلی بفرستد.")
if not ADMIN_PASSWORD:
    logger.warning("ADMIN_PASSWORD تنظیم نشده! پنل ادمین تا زمان تنظیم آن غیرفعال است.")

WALLET_RE = re.compile(r"^0x[a-fA-F0-9]{40}$")
TXID_RE = re.compile(r"^0x[a-fA-F0-9]{64}$")


# ---------------------------------------------------------------- Dependencies

def get_conn():
    conn = database.get_db()
    try:
        yield conn
    finally:
        conn.close()


def verify_admin(credentials: HTTPBasicCredentials = Depends(security)):
    if not ADMIN_PASSWORD:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="ADMIN_PASSWORD روی سرور تنظیم نشده است",
        )
    ok_user = secrets.compare_digest(credentials.username.encode("utf-8"), ADMIN_USERNAME.encode("utf-8"))
    ok_pass = secrets.compare_digest(credentials.password.encode("utf-8"), ADMIN_PASSWORD.encode("utf-8"))
    if not (ok_user and ok_pass):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="نام کاربری یا رمز عبور اشتباه است",
            headers={"WWW-Authenticate": "Basic"},
        )
    return credentials.username


# ---------------------------------------------------------------- Telegram auth

def validate_init_data(init_data: str) -> dict:
    """اعتبارسنجی امضای initData تلگرام با توکن ربات."""
    unauthorized = HTTPException(status_code=401, detail="احراز هویت تلگرام نامعتبر است. مینی‌اپ را ببندید و دوباره باز کنید.")
    try:
        pairs = dict(parse_qsl(init_data, keep_blank_values=True))
    except Exception:
        raise unauthorized

    received_hash = pairs.pop("hash", None)
    if not received_hash:
        raise unauthorized

    data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(pairs.items()))
    secret_key = hmac.new(b"WebAppData", BOT_TOKEN.encode("utf-8"), hashlib.sha256).digest()
    calculated = hmac.new(secret_key, data_check_string.encode("utf-8"), hashlib.sha256).hexdigest()

    if not hmac.compare_digest(calculated, received_hash):
        raise unauthorized

    try:
        auth_date = int(pairs.get("auth_date", "0"))
    except ValueError:
        raise unauthorized
    if time.time() - auth_date > INIT_DATA_MAX_AGE:
        raise unauthorized

    try:
        user = json.loads(pairs["user"])
        int(user["id"])
    except Exception:
        raise unauthorized

    return {"user": user, "start_param": pairs.get("start_param")}


def parse_referrer(value) -> Optional[int]:
    if value is None:
        return None
    value = str(value).strip()
    if re.fullmatch(r"\d{1,15}", value):
        return int(value)
    return None


def resolve_identity(init_data, user_id, username, referrer_id):
    """برمی‌گرداند: (user_id, username, referrer_id)"""
    if BOT_TOKEN:
        if not init_data:
            raise HTTPException(status_code=401, detail="این مینی‌اپ باید از داخل تلگرام باز شود.")
        verified = validate_init_data(init_data)
        u = verified["user"]
        uid = int(u["id"])
        uname = u.get("username") or u.get("first_name") or ""
        ref = parse_referrer(verified["start_param"])
        return uid, uname, ref

    # حالت ناامن (فقط تا زمانی که BOT_TOKEN تنظیم نشده)
    if user_id is None:
        raise HTTPException(status_code=400, detail="user_id ارسال نشده است")
    return user_id, username or "", referrer_id


# ---------------------------------------------------------------- Models

class UserRegister(BaseModel):
    init_data: Optional[str] = None
    user_id: Optional[int] = None
    username: Optional[str] = None
    referrer_id: Optional[int] = None


class WalletUpdate(BaseModel):
    init_data: Optional[str] = None
    user_id: Optional[int] = None
    wallet: str


class DiamondDeposit(BaseModel):
    init_data: Optional[str] = None
    user_id: Optional[int] = None
    txid: str


# ---------------------------------------------------------------- Static

frontend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../frontend"))
if os.path.exists(frontend_path):
    app.mount("/static", StaticFiles(directory=frontend_path), name="static")


@app.get("/")
async def serve_home():
    index_file = os.path.join(frontend_path, "index.html")
    if os.path.exists(index_file):
        return FileResponse(index_file)
    return {"status": "DTF Mini App Backend is running"}


# ---------------------------------------------------------------- API

@app.post("/api/init")
def init_user(data: UserRegister, conn: sqlite3.Connection = Depends(get_conn)):
    uid, uname, ref = resolve_identity(data.init_data, data.user_id, data.username, data.referrer_id)
    cursor = conn.cursor()

    # معرف باید وجود داشته باشد و خود کاربر نباشد
    valid_ref = None
    if ref and ref != uid:
        cursor.execute("SELECT 1 FROM users WHERE user_id = ?", (ref,))
        if cursor.fetchone():
            valid_ref = ref

    # درج اتمیک: اگر کاربر قبلاً بوده، هیچ ردیفی اضافه نمی‌شود (rowcount = 0)
    cursor.execute("""
        INSERT OR IGNORE INTO users
            (user_id, username, bronze_points, gold_points, diamond_points, deposit_status, referred_by, created_at)
        VALUES (?, ?, 1, 0, 0, 'none', ?, CURRENT_TIMESTAMP)
    """, (uid, uname, valid_ref))
    created = cursor.rowcount == 1

    if created:
        cursor.execute("UPDATE global_stats SET total_bronze_issued = total_bronze_issued + 1 WHERE id = 1")
        if valid_ref:
            cursor.execute("UPDATE users SET gold_points = gold_points + 1 WHERE user_id = ?", (valid_ref,))
            cursor.execute("UPDATE global_stats SET total_gold_issued = total_gold_issued + 1 WHERE id = 1")
        logger.info("NEW USER uid=%s raw_ref=%s valid_ref=%s gold_given=%s", uid, ref, valid_ref, bool(valid_ref))
    else:
        if uname:
            cursor.execute("UPDATE users SET username = ? WHERE user_id = ? AND username IS NOT ?", (uname, uid, uname))
        logger.info("EXISTING USER uid=%s raw_ref=%s (no reward)", uid, ref)

    conn.commit()

    cursor.execute("SELECT * FROM users WHERE user_id = ?", (uid,))
    user = cursor.fetchone()
    cursor.execute("SELECT * FROM global_stats WHERE id = 1")
    stats = cursor.fetchone()
    cursor.execute("SELECT COUNT(*) AS c FROM users WHERE referred_by = ? AND user_id != ?", (uid, uid))
    referral_count = cursor.fetchone()["c"]

    return {
        "user": dict(user),
        "referral_count": referral_count,
        "is_admin": ADMIN_TELEGRAM_ID is not None and uid == ADMIN_TELEGRAM_ID,
        "global_stats": {
            "total_bronze": stats["total_bronze_issued"],
            "total_gold": stats["total_gold_issued"],
            "total_diamond": stats["total_diamond_issued"],
        },
    }


@app.post("/api/wallet")
def update_wallet(data: WalletUpdate, conn: sqlite3.Connection = Depends(get_conn)):
    uid, _, _ = resolve_identity(data.init_data, data.user_id, None, None)
    wallet = data.wallet.strip()
    if not WALLET_RE.match(wallet):
        raise HTTPException(status_code=400, detail="آدرس کیف پول EVM معتبر نیست (باید با 0x شروع شود و ۴۰ کاراکتر هگز باشد).")

    cursor = conn.cursor()
    cursor.execute("SELECT evm_wallet FROM users WHERE user_id = ?", (uid,))
    row = cursor.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="کاربر یافت نشد")
    if row["evm_wallet"]:
        raise HTTPException(status_code=409, detail="کیف پول قبلاً ثبت شده و قابل تغییر نیست.")

    cursor.execute("UPDATE users SET evm_wallet = ? WHERE user_id = ?", (wallet, uid))
    conn.commit()
    return {"status": "success"}


@app.post("/api/deposit-diamond")
def deposit_diamond(data: DiamondDeposit, conn: sqlite3.Connection = Depends(get_conn)):
    uid, _, _ = resolve_identity(data.init_data, data.user_id, None, None)
    txid = data.txid.strip()
    if not TXID_RE.match(txid):
        raise HTTPException(status_code=400, detail="هش تراکنش معتبر نیست (باید با 0x شروع شود و ۶۴ کاراکتر هگز باشد).")

    cursor = conn.cursor()
    cursor.execute("SELECT deposit_status FROM users WHERE user_id = ?", (uid,))
    row = cursor.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="کاربر یافت نشد")
    if row["deposit_status"] in ("pending", "approved"):
        raise HTTPException(status_code=409, detail="شما قبلاً یک رسید ثبت کرده‌اید.")

    try:
        cursor.execute("INSERT INTO deposits (user_id, txid, status) VALUES (?, ?, 'pending')", (uid, txid))
        cursor.execute("UPDATE users SET deposit_status = 'pending' WHERE user_id = ?", (uid,))
        conn.commit()
    except sqlite3.IntegrityError:
        conn.rollback()
        raise HTTPException(status_code=409, detail="این هش تراکنش قبلاً ثبت شده است.")

    return {"status": "pending"}


# ---------------------------------------------------------------- Admin

ADMIN_CSS = """
    body { background: #090d16; color: #f8fafc; font-family: Tahoma, sans-serif; padding: 20px; }
    h2, h3 { color: #38bdf8; }
    .section { background: #111827; padding: 20px; border-radius: 12px; margin-bottom: 30px; border: 1px solid #1f2937; }
    table { width: 100%; border-collapse: collapse; margin-top: 10px; background: #0b0f19; border-radius: 8px; overflow: hidden; }
    th { background: #1f2937; padding: 12px; text-align: right; font-size: 13px; color: #38bdf8; }
    .btn { color: white; padding: 10px 16px; text-decoration: none; border-radius: 8px; font-weight: bold; display: inline-block; border: none; cursor: pointer; font-size: 14px; font-family: inherit; }
    .btn-excel { background: #059669; }
    .btn-excel:hover { background: #047857; }
    .btn-sync { background: #7c3aed; }
    .btn-sync:hover { background: #6d28d9; }
    .banner { background: #064e3b; color: #6ee7b7; padding: 12px 16px; border-radius: 8px; margin-bottom: 16px; }
"""

USERS_QUERY = """
    SELECT u.user_id, u.username, u.evm_wallet, u.bronze_points, u.gold_points, u.diamond_points,
           u.deposit_status, u.referred_by, u.created_at,
           (SELECT COUNT(*) FROM users r WHERE r.referred_by = u.user_id AND r.user_id != u.user_id) AS ref_count,
           (SELECT d.txid FROM deposits d WHERE d.user_id = u.user_id ORDER BY d.id DESC LIMIT 1) AS txid
    FROM users u
    ORDER BY u.created_at IS NULL, u.created_at, u.user_id
"""


@app.get("/admin", response_class=HTMLResponse)
def admin_panel(
    synced: Optional[int] = None,
    username: str = Depends(verify_admin),
    conn: sqlite3.Connection = Depends(get_conn),
):
    cursor = conn.cursor()

    cursor.execute("""
        SELECT deposits.id, deposits.user_id, users.username, users.evm_wallet, deposits.txid
        FROM deposits
        JOIN users ON deposits.user_id = users.user_id
        WHERE deposits.status = 'pending'
    """)
    pending_deposits = cursor.fetchall()

    cursor.execute(USERS_QUERY)
    all_users = cursor.fetchall()
    total_users_count = len(all_users)

    pending_rows = ""
    for d in pending_deposits:
        pending_rows += f"""
        <tr style="border-bottom: 1px solid #1f2937;">
            <td style="padding: 12px; color: #e2e8f0;">{d['user_id']}</td>
            <td style="padding: 12px; color: #e2e8f0;">{html.escape(d['username'] or 'بدون نام')}</td>
            <td style="padding: 12px; font-family: monospace; color: #cbd5e1;">{html.escape(d['evm_wallet'] or 'ثبت نشده')}</td>
            <td style="padding: 12px; font-family: monospace; color: #38bdf8;">{html.escape(d['txid'] or '')}</td>
            <td style="padding: 12px;">
                <form action="/admin/approve" method="POST" style="display:inline;">
                    <input type="hidden" name="deposit_id" value="{int(d['id'])}">
                    <button type="submit" style="background: #10B981; color: white; border: none; padding: 6px 12px; border-radius: 6px; cursor: pointer; font-weight: bold;">تایید و اعطای الماس ✅</button>
                </form>
            </td>
        </tr>
        """
    if not pending_rows:
        pending_rows = '<tr><td colspan="5" style="text-align:center; padding: 20px; color: #94a3b8;">هیچ درخواست در انتظاری وجود ندارد.</td></tr>'

    users_rows = ""
    for u in all_users:
        wallet_display = html.escape(u['evm_wallet']) if u['evm_wallet'] else '<span style="color:#ef4444;">ثبت نشده</span>'
        users_rows += f"""
        <tr style="border-bottom: 1px solid #1f2937;">
            <td style="padding: 10px; color: #e2e8f0;">{u['user_id']}</td>
            <td style="padding: 10px; color: #e2e8f0;">{html.escape(u['username'] or 'بدون نام')}</td>
            <td style="padding: 10px; font-family: monospace; font-size: 11px; color: #cbd5e1;">{wallet_display}</td>
            <td style="padding: 10px; text-align: center; color: #fb923c; font-weight: bold;">{u['bronze_points']}</td>
            <td style="padding: 10px; text-align: center; color: #fbbf24; font-weight: bold;">{u['gold_points']}</td>
            <td style="padding: 10px; text-align: center; color: #38bdf8; font-weight: bold;">{u['diamond_points']}</td>
            <td style="padding: 10px; text-align: center; color: #e2e8f0;">{html.escape(u['deposit_status'] or '')}</td>
            <td style="padding: 10px; text-align: center; color: #a78bfa;">{u['ref_count']}</td>
            <td style="padding: 10px; text-align: center; font-size: 11px; color: #94a3b8;">{u['referred_by'] or 'ندارد'}</td>
        </tr>
        """
    if not users_rows:
        users_rows = '<tr><td colspan="9" style="text-align:center; padding: 20px; color: #94a3b8;">هنوز کاربری ثبت‌نام نکرده است.</td></tr>'

    banner = ""
    if synced is not None:
        banner = f'<div class="banner">همگام‌سازی انجام شد. مجموع طلای اضافه‌شده: {synced}</div>'

    html_content = f"""
    <!DOCTYPE html>
    <html lang="fa" dir="rtl">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>پنل مدیریت DTF</title>
        <style>{ADMIN_CSS}</style>
    </head>
    <body>
        <h2>💎 پنل مدیریت پلتفرم DTF</h2>
        {banner}
        <p style="color: #94a3b8;">تعداد کل کاربران ثبت‌شده: <strong style="color: #f8fafc;">{total_users_count}</strong> نفر</p>

        <div style="display:flex; gap:12px; flex-wrap:wrap; margin-bottom: 20px;">
            <a href="/admin/export-excel" class="btn btn-excel">📊 دانلود خروجی کاربران (CSV - قابل باز شدن در اکسل)</a>
            <form action="/admin/sync-gold" method="POST" onsubmit="return confirm('طلای کاربرانی که کمتر از تعداد دعوت‌های واقعی‌شان دارند افزایش می‌یابد (هیچ‌وقت کم نمی‌شود). ادامه می‌دهید؟');">
                <button type="submit" class="btn btn-sync">🔄 همگام‌سازی طلای رفرال</button>
            </form>
        </div>

        <div class="section">
            <h3 style="color: #f59e0b; margin-top: 0;">⏳ درخواست‌های واریز الماس در انتظار تایید</h3>
            <table>
                <tr>
                    <th>شناسه کاربری (ID)</th>
                    <th>نام کاربری</th>
                    <th>کیف پول ثبت شده</th>
                    <th>هش تراکنش (TXID)</th>
                    <th>عملیات</th>
                </tr>
                {pending_rows}
            </table>
        </div>

        <div class="section">
            <h3 style="color: #38bdf8; margin-top: 0;">👥 لیست کامل کاربران و امتیازات به تفکیک (جهت محاسبات ایردراپ)</h3>
            <table>
                <tr>
                    <th>ID</th>
                    <th>نام کاربری</th>
                    <th>کیف پول EVM</th>
                    <th style="text-align: center;">برنز</th>
                    <th style="text-align: center;">طلا</th>
                    <th style="text-align: center;">الماس</th>
                    <th style="text-align: center;">وضعیت واریز</th>
                    <th style="text-align: center;">دعوت‌های موفق</th>
                    <th style="text-align: center;">معرف (Referrer)</th>
                </tr>
                {users_rows}
            </table>
        </div>
    </body>
    </html>
    """
    return html_content


@app.post("/admin/approve")
def admin_approve(
    deposit_id: int = Form(...),
    username: str = Depends(verify_admin),
    conn: sqlite3.Connection = Depends(get_conn),
):
    cursor = conn.cursor()
    cursor.execute("SELECT user_id, status FROM deposits WHERE id = ?", (deposit_id,))
    dep = cursor.fetchone()

    if dep and dep["status"] == "pending":
        cursor.execute("UPDATE deposits SET status = 'approved' WHERE id = ?", (deposit_id,))
        cursor.execute(
            "UPDATE users SET deposit_status = 'approved', diamond_points = diamond_points + 1 WHERE user_id = ?",
            (dep["user_id"],),
        )
        cursor.execute("UPDATE global_stats SET total_diamond_issued = total_diamond_issued + 1 WHERE id = 1")
        conn.commit()

    return RedirectResponse(url="/admin", status_code=303)


@app.post("/admin/sync-gold")
def admin_sync_gold(username: str = Depends(verify_admin), conn: sqlite3.Connection = Depends(get_conn)):
    """طلای هر کاربر را حداقل برابر تعداد دعوت‌های واقعی‌اش می‌کند (هیچ‌وقت کم نمی‌کند)."""
    cursor = conn.cursor()
    cursor.execute("""
        SELECT u.user_id, u.gold_points,
               (SELECT COUNT(*) FROM users r WHERE r.referred_by = u.user_id AND r.user_id != u.user_id) AS expected
        FROM users u
    """)
    added_total = 0
    for row in cursor.fetchall():
        if row["expected"] > row["gold_points"]:
            diff = row["expected"] - row["gold_points"]
            cursor.execute("UPDATE users SET gold_points = ? WHERE user_id = ?", (row["expected"], row["user_id"]))
            added_total += diff

    if added_total:
        cursor.execute("UPDATE global_stats SET total_gold_issued = total_gold_issued + ? WHERE id = 1", (added_total,))
    conn.commit()
    logger.info("SYNC GOLD added_total=%s", added_total)
    return RedirectResponse(url=f"/admin?synced={added_total}", status_code=303)


def csv_safe(value) -> str:
    """جلوگیری از تزریق فرمول در اکسل."""
    s = "" if value is None else str(value)
    if s.startswith(("=", "+", "-", "@", "\t", "\r")):
        return "'" + s
    return s


@app.get("/admin/export-excel")
def export_excel(username: str = Depends(verify_admin), conn: sqlite3.Connection = Depends(get_conn)):
    cursor = conn.cursor()
    cursor.execute(USERS_QUERY)
    users = cursor.fetchall()

    output = io.StringIO()
    writer = csv.writer(output)

    writer.writerow([
        'User ID', 'Username', 'EVM Wallet', 'Bronze Points', 'Gold Points', 'Diamond Points',
        'Deposit Status', 'Deposit TXID', 'Successful Referrals', 'Referred By', 'Created At',
    ])

    for u in users:
        writer.writerow([
            u['user_id'],
            csv_safe(u['username']),
            csv_safe(u['evm_wallet']),
            u['bronze_points'],
            u['gold_points'],
            u['diamond_points'],
            csv_safe(u['deposit_status']),
            csv_safe(u['txid']),
            u['ref_count'],
            u['referred_by'] if u['referred_by'] else '',
            csv_safe(u['created_at']),
        ])

    data = output.getvalue().encode('utf-8-sig')
    return StreamingResponse(
        io.BytesIO(data),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": "attachment; filename=dtf_users_airdrop_data.csv"},
    )
