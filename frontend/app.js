const tg = window.Telegram.WebApp;
tg.expand();

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

const user = tg.initDataUnsafe?.user || { id: 777888999, first_name: "کاربر تستی", username: "test_user" };
document.getElementById('username-badge').innerText = user.first_name;

let referrerId = tg.initDataUnsafe?.start_param || null;
const API_URL = "https://dtf-mini-production.up.railway.app"; 

async function initApp() {
    try {
        const response = await fetch(`${API_URL}/api/init`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                user_id: user.id,
                username: user.username || user.first_name,
                referrer_id: referrerId ? parseInt(referrerId) : null
            })
        });
        const data = await response.json();
        
        document.getElementById('my-bronze').innerText = data.user.bronze_points;
        document.getElementById('my-gold').innerText = data.user.gold_points;
        document.getElementById('my-diamond').innerText = data.user.diamond_points;

        document.getElementById('global-bronze').innerText = data.global_stats.total_bronze;
        document.getElementById('global-gold').innerText = data.global_stats.total_gold;
        document.getElementById('global-diamond').innerText = data.global_stats.total_diamond;

        // دکمه کانال برنز (با ثبت کیف پول)
        if (data.user.evm_wallet) {
            document.getElementById('wallet-input').value = data.user.evm_wallet;
            document.getElementById('wallet-input').disabled = true;
            document.getElementById('btn-bronze').classList.remove('hidden');
            document.getElementById('btn-bronze').href = "https://t.me/boronzDTF";
        }

        // دکمه کانال طلا (با داشتن حداقل ۱ امتیاز طلا از رفرال)
        if (data.user.gold_points > 0) {
            document.getElementById('btn-gold').classList.remove('hidden');
            document.getElementById('btn-gold').href = "https://t.me/talaDTF";
        }

        // دکمه کانال الماس (پس از تایید ادمین و دریافت امتیاز الماس)
        if (data.user.deposit_status === 'approved' || data.user.diamond_points > 0) {
            document.getElementById('btn-diamond').classList.remove('hidden');
            document.getElementById('btn-diamond').href = "https://t.me/almasDTF";
            document.getElementById('deposit-status-text').innerText = "وضعیت: تایید شده ✅ (دسترسی به کانال الماس فعال شد)";
            document.getElementById('deposit-status-text').className = "text-[11px] text-center text-emerald-400 mt-1";
        } else if (data.user.deposit_status === 'pending') {
            document.getElementById('deposit-status-text').innerText = "وضعیت: در انتظار بررسی ادمین ⏳";
            document.getElementById('deposit-status-text').className = "text-[11px] text-center text-amber-400 mt-1";
        }

    } catch (err) {
        console.error("خطا در ارتباط با سرور:", err);
    }
}

async function saveWallet() {
    const wallet = document.getElementById('wallet-input').value.trim();
    if (!wallet.startsWith("0x") || wallet.length < 40) {
        alert("لطفا یک آدرس معتبر EVM وارد کنید.");
        return;
    }
    
    await fetch(`${API_URL}/api/wallet`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ user_id: user.id, wallet: wallet })
    });
    
    alert("کیف پول با موفقیت ثبت شد!");
    location.reload();
}

async function submitDiamond() {
    const txid = document.getElementById('txid-input').value.trim();
    if (!txid) {
        alert("لطفا کد تراکنش را وارد کنید.");
        return;
    }

    await fetch(`${API_URL}/api/deposit-diamond`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ user_id: user.id, txid: txid })
    });

    alert("رسید شما با موفقیت ثبت شد و پس از بررسی ادمین تایید خواهد شد.");
    location.reload();
}

function copyRefLink() {
    const refLink = `https://t.me/dotoflow_bot/app?startapp=${user.id}`;
    navigator.clipboard.writeText(refLink);
    alert("لینک دعوت شما کپی شد!");
}

function copyWalletAddress() {
    const address = document.getElementById('wallet-address-text').innerText.trim();
    navigator.clipboard.writeText(address);
    alert("آدرس کیف پول مقصد کپی شد!");
}

initApp();
