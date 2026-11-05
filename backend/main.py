@app.post("/api/init")
def init_user(data: UserRegister):
    conn = database.get_db()
    cursor = conn.cursor()
    
    # بررسی اینکه آیا کاربر قبلاً ثبت‌نام کرده است یا خیر
    cursor.execute("SELECT * FROM users WHERE user_id = ?", (data.user_id,))
    user = cursor.fetchone()
    
    if not user:
        # ثبت کاربر جدید با احتساب معرف (در صورت وجود)
        cursor.execute("""
            INSERT INTO users (user_id, username, bronze_points, gold_points, diamond_points, deposit_status, referred_by) 
            VALUES (?, ?, 1, 0, 0, 'none', ?)
        """, (data.user_id, data.username, data.referrer_id))
        
        # افزایش آمار کل برنز شبکه
        cursor.execute("UPDATE global_stats SET total_bronze_issued = total_bronze_issued + 1 WHERE id = 1")
        
        # اعطای امتیاز طلا به معرف
        if data.referrer_id and data.referrer_id != data.user_id:
            # بررسی اینکه آیا معرف واقعاً در دیتابیس وجود دارد
            cursor.execute("SELECT user_id FROM users WHERE user_id = ?", (data.referrer_id,))
            referrer_exists = cursor.fetchone()
            
            if referrer_exists:
                # اضافه کردن ۱ امتیاز طلا به معرف
                cursor.execute("UPDATE users SET gold_points = gold_points + 1 WHERE user_id = ?", (data.referrer_id,))
                # آپدیت آمار کلی طلای شبکه
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
