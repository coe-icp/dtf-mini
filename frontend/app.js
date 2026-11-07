const tg = window.Telegram.WebApp;
tg.ready();
tg.expand();

const API_URL = "https://dtf-mini-production.up.railway.app";
const REF_BASE_LINK = "https://t.me/dotoflow_bot/app?startapp=";

// ---------- پاپ‌آپ سلب مسئولیت ----------
function toggleAccept() {
    const checkbox = document.getElementById('accept-checkbox');
    const acceptBtn = document.getElementById('accept-btn');

    if (checkbox.checked) {
        acceptBtn.disabled = false;
        acceptBtn.classList.remove('bg-slate-800', 'text-slate-500', 'cursor-not-allowed');
        acceptBtn.classList.add('bg-amber-500', 'hover:bg-amber-400', 'text-slate-950', 'cursor-pointer');
    } else {
        acceptBtn.disabled = true;
        acceptBtn.classList.remove('bg-amber-500', 'hover:bg-amber-400', 'text-slate-950', 'cursor-pointer');
        acceptBtn.classList.add('bg-slate-800', 'text-slate-500', 'cursor-not-allowed');
    }
}

function closeDisclaimer() {
    const checkbox = document.getElementById('accept-checkbox');
    if (!checkbox.checked) return;
    document.getElementById('disclaimer-modal').style.display = 'none';
}

// ---------- اطلاعات کاربر ----------
// خارج از تلگرام (فقط برای تست در مرورگر) کاربر تستی استفاده می‌شود
const user = tg.initDataUnsafe?.user || { id: 777888999, first_name: "کاربر تستی", username: "test_user" };
document.getElementById('username-badge').innerText = user.first_name;

const initData = tg.initData || null;
const referrerId = tg.initDataUnsafe?.start_param || null;

// ---------- ارتباط با سرور ----------
async function api(path, payload) {
    const res = await fetch(`${API_URL}${path}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            init_data: initData,
            user_id: user.id,
            ...payload
        })
    });

    let data = null;
    try { data = await res.json(); } catch (e) { /* پاسخ JSON نبود */ }

    if (!res.ok) {
        const msg = (data && typeof data.detail === 'string') ? data.detail : "خطا در ارتباط با سرور";
        const err = new Error(msg);
        err.status = res.status;
        throw err;
    }
    return data;
}

function render(data) {
    document.getElementById('my-bronze').innerText = data.user.bronze_points;
    document.getElementById('my-gold').innerText = data.user.gold_points;
    document.getElementById('my-diamond').innerText = data.user.diamond_points;

    document.getElementById('global-bronze').innerText = data.global_stats.total_bronze;
    document.getElementById('global-gold').innerText = data.global_stats.total_gold;
    document.getElementById('global-diamond').innerText = data.global_stats.total_diamond;

    document.getElementById('ref-count').innerText = data.referral_count;

    // دکمه ادمین فقط برای ادمین
    if (data.is_admin) {
        document.getElementById('admin-box').classList.remove('hidden');
    }

    // کانال برنز (با ثبت کیف پول)
    if (data.user.evm_wallet) {
        document.getElementById('wallet-input').value = data.user.evm_wallet;
        document.getElementById('wallet-input').disabled = true;
        document.getElementById('save-wallet-btn').disabled = true;
        document.getElementById('save-wallet-btn').classList.add('opacity-50', 'cursor-not-allowed');
        document.getElementById('btn-bronze').classList.remove('hidden');
        document.getElementById('btn-bronze').href = "https://t.me/boronzDTF";
    }

    // کانال طلا (حداقل ۱ امتیاز طلا)
    if (data.user.gold_points > 0) {
        document.getElementById('btn-gold').classList.remove('hidden');
        document.getElementById('btn-gold').href = "https://t.me/talaDTF";
    }

    // کانال الماس و وضعیت واریز
    const statusEl = document.getElementById('deposit-status-text');
    if (data.user.deposit_status === 'approved' || data.user.diamond_points > 0) {
        document.getElementById('btn-diamond').classList.remove('hidden');
        document.getElementById('btn-diamond').href = "https://t.me/almasDTF";
        statusEl.innerText = "وضعیت: تایید شده ✅ (دسترسی به کانال الماس فعال شد)";
        statusEl.className = "text-[11px] text-center text-emerald-400 mt-1";
    } else if (data.user.deposit_status === 'pending') {
        statusEl.innerText = "وضعیت: در انتظار بررسی ادمین ⏳";
        statusEl.className = "text-[11px] text-center text-amber-400 mt-1";
    } else {
        statusEl.innerText = "";
    }
}

async function initApp() {
    try {
        const data = await api('/api/init', {
            username: user.username || user.first_name,
            referrer_id: referrerId && /^\d+$/.test(referrerId) ? parseInt(referrerId, 10) : null
        });
        render(data);
    } catch (err) {
        console.error("خطا در ارتباط با سرور:", err);
        if (err.status === 401) {
            alert(err.message);
        }
    }
}

// ---------- کیف پول ----------
async function saveWallet() {
    const wallet = document.getElementById('wallet-input').value.trim();
    if (!/^0x[a-fA-F0-9]{40}$/.test(wallet)) {
        alert("لطفا یک آدرس معتبر EVM وارد کنید (با 0x شروع شود و ۴۲ کاراکتر باشد).");
        return;
    }

    try {
        await api('/api/wallet', { wallet: wallet });
        alert("کیف پول با موفقیت ثبت شد!");
        await initApp();
    } catch (err) {
        alert(err.message);
    }
}

// ---------- واریز الماس ----------
async function submitDiamond() {
    const txid = document.getElementById('txid-input').value.trim();
    if (!/^0x[a-fA-F0-9]{64}$/.test(txid)) {
        alert("هش تراکنش معتبر نیست. باید با 0x شروع شود و ۶۶ کاراکتر باشد.");
        return;
    }

    try {
        await api('/api/deposit-diamond', { txid: txid });
        alert("رسید شما با موفقیت ثبت شد و پس از بررسی ادمین تایید خواهد شد.");
        document.getElementById('txid-input').value = "";
        await initApp();
    } catch (err) {
        alert(err.message);
    }
}

// ---------- کپی ----------
function copyText(text) {
    if (navigator.clipboard && navigator.clipboard.writeText) {
        return navigator.clipboard.writeText(text).catch(() => fallbackCopy(text));
    }
    fallbackCopy(text);
    return Promise.resolve();
}

function fallbackCopy(text) {
    const ta = document.createElement('textarea');
    ta.value = text;
    ta.style.position = 'fixed';
    ta.style.opacity = '0';
    document.body.appendChild(ta);
    ta.select();
    try { document.execCommand('copy'); } catch (e) { /* ignore */ }
    document.body.removeChild(ta);
}

async function copyRefLink() {
    await copyText(`${REF_BASE_LINK}${user.id}`);
    alert("لینک دعوت شما کپی شد!");
}

async function copyWalletAddress() {
    const address = document.getElementById('wallet-address-text').innerText.trim();
    await copyText(address);
    alert("آدرس کیف پول مقصد کپی شد!");
}

// ---------- پنل ادمین (در مرورگر بیرونی باز می‌شود تا دانلود و لاگین درست کار کند) ----------
function openAdmin() {
    const url = `${API_URL}/admin`;
    if (tg.openLink) {
        tg.openLink(url);
    } else {
        window.open(url, '_blank');
    }
}

// ---------- شروع ----------
initApp();

// وقتی کاربر به مینی‌اپ برمی‌گردد، امتیازها بروز شوند (مثلاً بعد از دعوت موفق)
document.addEventListener('visibilitychange', () => {
    if (document.visibilityState === 'visible') initApp();
});
