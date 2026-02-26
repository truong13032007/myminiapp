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

# --- HÀM TÍNH TOÁN (KHÔNG AI - SIÊU NHANH) ---
def calculate_rsi(closes):
    if len(closes) < 15: return 50
    diff = [closes[i] - closes[i-1] for i in range(1, len(closes))]
    gain = sum([d for d in diff[-14:] if d > 0]) / 14
    loss = sum([-d for d in diff[-14:] if d < 0]) / 14
    return round(100 - (100 / (1 + (gain/abs(loss)))), 2) if loss != 0 else 100

async def get_data(name, sym):
    ex = ccxt.okx({'timeout': 5000}) # Chỉ đợi sàn 5s, không đợi lâu gây đơ
    try:
        ohlcv = await ex.fetch_ohlcv(sym, timeframe='1h', limit=50)
        curr = ohlcv[-1][4]
        rsi = calculate_rsi([x[4] for x in ohlcv])
        
        trend = "ĐI NGANG"
        if rsi > 55: trend = "TĂNG"
        elif rsi < 45: trend = "GIẢM"
        
        signal = ""
        if rsi <= 32: signal = f"\n🚨 **LỆNH: LONG**\n📍 **ENTRY: {curr}**"
        elif rsi >= 68: signal = f"\n🚨 **LỆNH: SHORT**\n📍 **ENTRY: {curr}**"
        
        msg = (f"📊 *{name}*\n"
               f"━━━━━━━━━━━━━━━\n"
               f"💰 Price: `{curr}`\n"
               f"📈 RSI: `{rsi}`\n"
               f"🔍 Xu hướng: *{trend}*\n"
               f"━━━━━━━━━━━━━━━{signal}")
        return msg, curr, (True if signal else False)
    except:
        return None, None, False
    finally:
        await ex.close()

# --- VÒNG LẶP CHÍNH (XỬ LÝ NÚT BẤM VÀ QUÉT) ---
async def main_loop():
    offset = 0
    last_scan = 0
    last_alerts = {s: 0 for s in SYMBOLS}
    
    while True:
        try:
            # 1. Kiểm tra tin nhắn/nút bấm (Timeout ngắn để không chặn luồng)
            url = f"https://api.telegram.org/bot{TOKEN}/getUpdates?offset={offset}&timeout=5"
            res = requests.get(url, timeout=10).json()
            
            for update in res.get("result", []):
                offset = update["update_id"] + 1
                if "message" in update and "text" in update["message"]:
                    cmd = update["message"]["text"]
                    if cmd in SYMBOLS:
                        msg, _, _ = await get_data(cmd, SYMBOLS[cmd])
                        if msg:
                            requests.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage", 
                                json={"chat_id": CHAT_ID, "text": msg, "parse_mode": "Markdown", "reply_markup": KEYBOARD})
                    elif cmd == "/start":
                        requests.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage", 
                            json={"chat_id": CHAT_ID, "text": "Bot đã fix lỗi đơ. Sẵn sàng!", "reply_markup": KEYBOARD})

            # 2. Tự động quét kèo mỗi 3 phút
            if time.time() - last_scan > 180:
                for name, sym in SYMBOLS.items():
                    msg, curr, has_sig = await get_data(name, sym)
                    if has_sig and last_alerts[name] != curr:
                        requests.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage", 
                            json={"chat_id": CHAT_ID, "text": "🔔 *BÁO KÈO TỰ ĐỘNG*\n" + msg, "parse_mode": "Markdown"})
                        last_alerts[name] = curr
                last_scan = time.time()

        except Exception as e:
            print(f"Lỗi: {e}")
            await asyncio.sleep(5) # Nếu lỗi mạng, nghỉ 5s rồi chạy tiếp
        
        await asyncio.sleep(0.1) # Nghỉ cực ngắn để CPU không quá tải

@app.route('/')
def home(): return "Bot Online", 200

if __name__ == "__main__":
    # Chạy Web Server để Render không tắt bot
    Thread(target=lambda: app.run(host='0.0.0.0', port=10000)).start()
    # Chạy vòng lặp bot
    asyncio.run(main_loop())
