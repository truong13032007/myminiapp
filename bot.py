import asyncio
import requests
import ccxt.async_support as ccxt
from flask import Flask
from threading import Thread
import time

# --- CẤU HÌNH ---
TOKEN = "8732938098:AAGrT0VC6B1mCMKPzdthChMUfGr2dv8tuZ0"
CHAT_ID = "6317501489"
SYMBOLS = {
    "BTC ₿": "BTC/USDT", "ETH Ξ": "ETH/USDT",
    "SOL ☀️": "SOL/USDT", "VÀNG 🏆": "PAXG/USDT"
}

app = Flask(__name__)
KEYBOARD = {"keyboard": [[{"text": "BTC ₿"}, {"text": "ETH Ξ"}], [{"text": "SOL ☀️"}, {"text": "VÀNG 🏆"}]], "resize_keyboard": True}

# --- HÀM TÍNH TOÁN KỸ THUẬT THUẦN (CHỐNG LỖI) ---
def calculate_indicators(closes):
    # RSI 14
    deltas = [closes[i] - closes[i-1] for i in range(1, len(closes))]
    gains = [d if d > 0 else 0 for d in deltas[-14:]]
    losses = [-d if d < 0 else 0 for d in deltas[-14:]]
    avg_gain = sum(gains) / 14
    avg_loss = sum(losses) / 14
    rsi = 100 - (100 / (1 + (avg_gain / avg_loss))) if avg_loss != 0 else 100

    # SMA 20 & Bollinger Bands
    sma20 = sum(closes[-20:]) / 20
    variance = sum((x - sma20) ** 2 for x in closes[-20:]) / 20
    std_dev = variance ** 0.5
    upper, lower = sma20 + (std_dev * 2), sma20 - (std_dev * 2)

    # EMA 200 (Ước tính nhanh)
    ema200 = sum(closes[-200:]) / 200 if len(closes) >= 200 else sum(closes) / len(closes)

    return round(rsi, 2), round(upper, 2), round(lower, 2), round(ema200, 2)

async def get_market_signal(name, sym, is_auto=False):
    ex = ccxt.okx({'timeout': 5000})
    try:
        ohlcv = await ex.fetch_ohlcv(sym, timeframe='1h', limit=250)
        closes = [x[4] for x in ohlcv]
        curr = closes[-1]
        rsi, upper, lower, ema200 = calculate_indicators(closes)

        # LOGIC ĐA TẦNG
        verdict = "CHỜ TÍN HIỆU"
        score = 0
        
        if rsi < 32 and curr <= lower:
            score = 70
            if curr > ema200: score += 20 # Thuận xu hướng tăng
            verdict = "LONG (MUA)"
        elif rsi > 68 and curr >= upper:
            score = 70
            if curr < ema200: score += 20 # Thuận xu hướng giảm
            verdict = "SHORT (BÁN)"

        if is_auto and score < 90: return # Chỉ tự động báo kèo cực thơm

        sl = round(curr * (0.985 if "LONG" in verdict else 1.015), 2)
        tp = round(curr * (1.03 if "LONG" in verdict else 0.97), 2)

        msg = (f"🛡 *CHIẾN THUẬT ĐA TẦNG: {name}*\n"
               f"━━━━━━━━━━━━━━━\n"
               f"💰 Giá: `{curr}` | RSI: `{rsi}`\n"
               f"📊 Xu hướng: `{'TĂNG' if curr > ema200 else 'GIẢM'}`\n"
               f"💠 BB: `{lower} - {upper}`\n"
               f"━━━━━━━━━━━━━━━\n"
               f"📢 **LỆNH: {verdict}**\n"
               f"🎯 TP: `{tp}` | 🛑 SL: `{sl}`\n"
               f"⭐ Độ tin cậy: `{score}%`")
        
        requests.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage", 
                      json={"chat_id": CHAT_ID, "text": msg, "parse_mode": "Markdown", "reply_markup": KEYBOARD})
    except Exception as e:
        print(f"Lỗi fetch: {e}")
    finally:
        await ex.close()

# --- LUỒNG XỬ LÝ CHÍNH ---
async def main_worker():
    offset = 0
    last_scan = 0
    while True:
        try:
            url = f"https://api.telegram.org/bot{TOKEN}/getUpdates?offset={offset}&timeout=10"
            res = requests.get(url, timeout=15).json()
            for update in res.get("result", []):
                offset = update["update_id"] + 1
                if "message" in update and "text" in update["message"]:
                    text = update["message"]["text"]
                    if text in SYMBOLS:
                        await get_market_signal(text, SYMBOLS[text])
                    elif text == "/start":
                        requests.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage", 
                                      json={"chat_id": CHAT_ID, "text": "✅ Hệ thống Trading Logic đã kết nối!", "reply_markup": KEYBOARD})

            if time.time() - last_scan > 600:
                for name, sym in SYMBOLS.items():
                    await get_market_signal(name, sym, is_auto=True)
                last_scan = time.time()
        except:
            await asyncio.sleep(5)
        await asyncio.sleep(0.5)

@app.route('/')
def home(): return "Bot is Running", 200

if __name__ == "__main__":
    Thread(target=lambda: app.run(host='0.0.0.0', port=10000)).start()
    asyncio.run(main_worker())
