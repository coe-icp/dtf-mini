const tg = window.Telegram.WebApp;
tg.expand();

const user = tg.initDataUnsafe?.user || { id: 777888999, first_name: "کاربر تستی", username: "test_user" };
document.getElementById('username-badge').innerText = user.first_name;

const urlParams = new URLSearchParams(window.location.search);
let referrerId = urlParams.get('start') || null;

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

        if (data.user.evm_wallet) {
            document.getElementById('wallet-input').value = data.user.evm_wallet;
            document.getElementById('wallet-input').disabled = true;
            document.getElementById('btn-bronze').classList.remove('hidden');
            document.getElementById('btn-bronze').href = "https://t.me/boronzDTF";
        }

        if (data.user.gold_points > 0) {
            document.getElementById('btn-gold').classList.remove('hidden');
            document.getElementById('btn-gold').href = "https://t.me/talaDTF";
        }

        if (data.user.deposit_status === 'approved') {
            document.getElementById('btn-diamond').classList.remove('hidden');
            document.getElementById('btn-diamond').href = "https://t.me/almasDTF";
            document.getElementById('deposit-status-text').innerText = "وضعیت: تایید شده ✅";
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
    const refLink = `https://t.me/your_bot_username/app?start=${user.id}`;
    navigator.clipboard.writeText(refLink);
    alert("لینک دعوت شما کپی شد!");
}

initApp();
