import asyncio
import requests
import ccxt.async_support as ccxt
from flask import Flask
from threading import Thread

# --- CẤU HÌNH ---
TOKEN = "8732938098:AAGrT0VC6B1mCMKPzdthChMUfGr2dv8tuZ0"
CHAT_ID = "6317501489"
SYMBOLS = {
    "BTC ₿": "BTC/USDT", "ETH Ξ": "ETH/USDT",
    "SOL ☀️": "SOL/USDT", "VÀNG 🏆": "PAXG/USDT"
}

app = Flask(__name__)
KEYBOARD = {"keyboard": [[{"text": "BTC ₿"}, {"text": "ETH Ξ"}], [{"text": "SOL ☀️"}, {"text": "VÀNG 🏆"}]], "resize_keyboard": True}

def calculate_indicators(closes):
    # RSI 14
    diff = [closes[i] - closes[i-1] for i in range(1, len(closes))]
    gain = sum([d for d in diff[-14:] if d > 0]) / 14
    loss = sum([-d for d in diff[-14:] if d < 0]) / 14
    rsi = round(100 - (100 / (1 + (gain/abs(loss)))), 2) if loss != 0 else 100
    return rsi

async def get_signal_message(name, sym):
    ex = ccxt.okx()
    try:
        ohlcv = await ex.fetch_ohlcv(sym, timeframe='1h', limit=50)
        closes = [x[4] for x in ohlcv]
        curr = closes[-1]
        rsi = calculate_indicators(closes)
        
        # 1. Xác định xu hướng dựa trên RSI và so sánh giá đóng cửa
        trend = "ĐI NGANG (Sway)"
        if rsi > 55: trend = "TĂNG (Up)"
        elif rsi < 45: trend = "GIẢM (Down)"
        
        # 2. Xác định tín hiệu vào lệnh (Entry)
        entry_text = ""
        signal_type = ""
        if rsi <= 32:
            signal_type = "🟢 LỆNH: LONG"
            entry_text = f"\n📍 **ENTRY: {curr}**"
        elif rsi >= 68:
            signal_type = "🔴 LỆNH: SHORT"
            entry_text = f"\n📍 **ENTRY: {curr}**"
        
        # 3. Gom nội dung tin nhắn
        msg = (f"📊 *THÔNG TIN: {name}*\n"
               f"━━━━━━━━━━━━━━━\n"
               f"💰 Price: `{curr}`\n"
               f"📈 RSI: `{rsi}`\n"
               f"🔍 Xu hướng: *{trend}*")
        
        if entry_text:
            msg = f"🚨 *CÓ TÍN HIỆU VÀO LỆNH*\n" + msg + f"\n{signal_type}{entry_text}"
            
        return msg, curr, (True if entry_text else False)
    except: return None, None, False
    finally: await ex.close()

# TỰ ĐỘNG THÔNG BÁO KHI CÓ TÍN HIỆU
async def auto_scanner():
    last_alerts = {s: 0 for s in SYMBOLS}
    while True:
        for name, sym in SYMBOLS.items():
            msg, curr, has_signal = await get_signal_message(name, sym)
            # Chỉ tự động nhắn khi thực sự có tín hiệu Long/Short
            if has_signal and last_alerts[name] != curr:
                requests.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage", 
                              json={"chat_id": CHAT_ID, "text": "🔔 *CẢNH BÁO TỰ ĐỘNG*\n" + msg, "parse_mode": "Markdown"})
                last_alerts[name] = curr
        await asyncio.sleep(60)

# PHẢN HỒI KHI ẤN NÚT (Luôn hiện Price + Xu hướng)
async def button_handler():
    offset = 0
    while True:
        try:
            url = f"https://api.telegram.org/bot{TOKEN}/getUpdates?offset={offset}&timeout=10"
            res = requests.get(url).json()
            for update in res.get("result", []):
                offset = update["update_id"] + 1
                if "message" in update and "text" in update["message"]:
                    text = update["message"]["text"]
                    if text in SYMBOLS:
                        msg, _, _ = await get_signal_message(text, SYMBOLS[text])
                        if msg:
                            requests.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage", 
                                          json={"chat_id": CHAT_ID, "text": msg, "parse_mode": "Markdown", "reply_markup": KEYBOARD})
                    elif text == "/start":
                        requests.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage", 
                                      json={"chat_id": CHAT_ID, "text": "Bot đã sẵn sàng!", "reply_markup": KEYBOARD})
        except: pass
        await asyncio.sleep(1)

@app.route('/')
def home(): return "Bot Active", 200

if __name__ == "__main__":
    Thread(target=lambda: app.run(host='0.0.0.0', port=10000)).start()
    loop = asyncio.get_event_loop()
    loop.create_task(auto_scanner())
    loop.create_task(button_handler())
    loop.run_forever()
