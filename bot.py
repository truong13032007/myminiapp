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

# --- HÀM TÍNH TOÁN CHỈ BÁO ---
def get_indicators(closes):
    if len(closes) < 30: return 50, 0, 0, 0
    
    # 1. RSI 14
    diff = [closes[i] - closes[i-1] for i in range(1, len(closes))]
    gain = sum([d for d in diff[-14:] if d > 0]) / 14
    loss = sum([-d for d in diff[-14:] if d < 0]) / 14
    rsi = round(100 - (100 / (1 + (gain/abs(loss)))), 2) if loss != 0 else 100
    
    # 2. Bollinger Bands (20)
    sma20 = sum(closes[-20:]) / 20
    std_dev = (sum((x - sma20) ** 2 for x in closes[-20:]) / 20) ** 0.5
    upper = sma20 + (std_dev * 2)
    lower = sma20 - (std_dev * 2)
    
    # 3. MA200 (Xu hướng dài hạn)
    # Vì fetch 50 nến nên chỉ lấy MA30 làm đại diện cho xu hướng ngắn hạn
    ma_trend = sum(closes[-30:]) / 30
    
    return rsi, upper, lower, ma_trend

async def get_data(name, sym):
    ex = ccxt.okx({'timeout': 7000})
    try:
        ohlcv = await ex.fetch_ohlcv(sym, timeframe='1h', limit=50)
        closes = [x[4] for x in ohlcv]
        curr = closes[-1]
        rsi, upper, lower, ma_trend = get_indicators(closes)
        
        # LOGIC LỌC LỆNH GẮT GAO
        signal = ""
        # Long khi RSI thấp + Giá thủng dải dưới BB
        if rsi <= 30 and curr < lower:
            signal = f"\n🔥 **TÍN HIỆU MUA (LONG)**\n📍 **ENTRY: {curr}**"
        # Short khi RSI cao + Giá vượt dải trên BB
        elif rsi >= 70 and curr > upper:
            signal = f"\n💥 **TÍN HIỆU BÁN (SHORT)**\n📍 **ENTRY: {curr}**"
        
        trend_msg = "📈 TĂNG" if curr > ma_trend else "📉 GIẢM"
        
        msg = (f"📊 *{name}*\n"
               f"━━━━━━━━━━━━━━━\n"
               f"💰 Price: `{curr}`\n"
               f"📈 RSI: `{rsi}`\n"
               f"🌐 BB: `{round(lower,2)}` - `{round(upper,2)}`\n"
               f"🔍 Trend: *{trend_msg}*\n"
               f"━━━━━━━━━━━━━━━{signal}")
        return msg, curr, (True if signal else False)
    except:
        return None, None, False
    finally:
        await ex.close()

# --- VÒNG LẶP XỬ LÝ ---
async def main_loop():
    offset = 0
    last_scan = 0
    last_alerts = {s: 0 for s in SYMBOLS}
    
    while True:
        try:
            # 1. Check nút bấm
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
                            json={"chat_id": CHAT_ID, "text": "Bot Đa Chỉ Báo đã sẵn sàng!", "reply_markup": KEYBOARD})

            # 2. Tự động quét kèo (Mỗi 5 phút)
            if time.time() - last_scan > 300:
                for name, sym in SYMBOLS.items():
                    msg, curr, has_sig = await get_data(name, sym)
                    if has_sig and last_alerts[name] != curr:
                        requests.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage", 
                            json={"chat_id": CHAT_ID, "text": "🔔 *KÈO CHUẨN ĐÃ LỌC*\n" + msg, "parse_mode": "Markdown"})
                        last_alerts[name] = curr
                last_scan = time.time()
        except:
            await asyncio.sleep(5)
        await asyncio.sleep(0.2)

@app.route('/')
def home(): return "Bot Multi-Indicator Active", 200

if __name__ == "__main__":
    Thread(target=lambda: app.run(host='0.0.0.0', port=10000)).start()
    asyncio.run(main_loop())
