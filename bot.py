import asyncio
import requests
import ccxt.async_support as ccxt
from flask import Flask
from threading import Thread
import time

# --- CẤU HÌNH BOT ---
TOKEN = "8732938098:AAGrT0VC6B1mCMKPzdthChMUfGr2dv8tuZ0"
CHAT_ID = "6317501489"
# Đổi symbol sang định dạng của OKX (thường là COIN-USDT)
SYMBOLS = {
    "BTC ₿": "BTC/USDT",
    "ETH Ξ": "ETH/USDT",
    "SOL ☀️": "SOL/USDT",
    "VÀNG 🏆": "PAXG/USDT"
}

app = Flask(__name__)

KEYBOARD = {
    "keyboard": [
        [{"text": "BTC ₿"}, {"text": "ETH Ξ"}],
        [{"text": "SOL ☀️"}, {"text": "VÀNG 🏆"}]
    ],
    "resize_keyboard": True
}

def send_photo(caption, symbol):
    # Sử dụng TradingView để lấy ảnh biểu đồ
    tv_sym = symbol.replace("/", "")
    photo_url = f"https://api.screenshotmachine.com/?key=bc8945&url=https://www.tradingview.com/chart/?symbol=OKX:{tv_sym}&dimension=1024x768"
    
    url = f"https://api.telegram.org/bot{TOKEN}/sendPhoto"
    payload = {
        "chat_id": CHAT_ID,
        "photo": photo_url,
        "caption": caption,
        "parse_mode": "Markdown",
        "reply_markup": KEYBOARD
    }
    try:
        requests.post(url, json=payload, timeout=10)
    except:
        requests.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage", 
                      json={"chat_id": CHAT_ID, "text": caption, "parse_mode": "Markdown"})

async def get_data_and_reply(name, symbol):
    # DÙNG OKX THAY CHO BINANCE ĐỂ TRÁNH LỖI 451 TRÊN RENDER
    ex = ccxt.okx() 
    try:
        ohlcv = await ex.fetch_ohlcv(symbol, timeframe='1h', limit=50)
        closes = [x[4] for x in ohlcv]
        
        diff = [closes[i] - closes[i-1] for i in range(1, len(closes))]
        gain = sum([d for d in diff[-14:] if d > 0]) / 14
        loss = sum([-d for d in diff[-14:] if d < 0]) / 14
        rs = gain / abs(loss) if loss != 0 else 0
        rsi = round(100 - (100 / (1 + rs)), 2)
        
        signal = "⚪ ĐANG CHỜ"
        arrow = ""
        if rsi <= 35: 
            signal = "🟢 *LỆNH: LONG (MUA)*"
            arrow = "⬆️⬆️⬆️"
        elif rsi >= 65:
            signal = "🔴 *LỆNH: SHORT (BÁN)*"
            arrow = "⬇️⬇️⬇️"

        caption = (f"🔔 *TÍN HIỆU {name} (Data: OKX)*\n"
                   f"━━━━━━━━━━━━━━━\n"
                   f"💰 Giá: `{closes[-1]}`\n"
                   f"📊 RSI: `{rsi}`\n"
                   f"👉 Tín hiệu: {signal}\n"
                   f"🎯 {arrow}\n"
                   f"━━━━━━━━━━━━━━━\n"
                   f"⏰ Khung: 1 Giờ")
        
        send_photo(caption, symbol)
    except Exception as e:
        requests.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage", 
                      json={"chat_id": CHAT_ID, "text": f"Lỗi hệ thống: {str(e)}", "parse_mode": "Markdown"})
    finally:
        await ex.close()

async def main_bot():
    offset = 0
    while True:
        try:
            url = f"https://api.telegram.org/bot{TOKEN}/getUpdates?offset={offset}&timeout=5"
            updates = requests.get(url).json()
            for update in updates.get("result", []):
                offset = update["update_id"] + 1
                if "message" in update and "text" in update["message"]:
                    cmd = update["message"]["text"]
                    if cmd == "/start":
                        requests.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage", 
                                      json={"chat_id": CHAT_ID, "text": "🚀 Đã sửa lỗi kết nối sàn! Chọn coin để lấy kèo:", "reply_markup": KEYBOARD})
                    elif cmd in SYMBOLS:
                        requests.post(f"https://api.telegram.org/bot{TOKEN}/sendChatAction", json={"chat_id": CHAT_ID, "action": "upload_photo"})
                        await get_data_and_reply(cmd, SYMBOLS[cmd])
        except: pass
        await asyncio.sleep(1)

@app.route('/')
def home(): return "Bot Fix 451 Active", 200

if __name__ == "__main__":
    Thread(target=lambda: app.run(host='0.0.0.0', port=10000)).start()
    asyncio.run(main_bot())
