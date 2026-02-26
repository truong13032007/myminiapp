import asyncio
import requests
import ccxt.async_support as ccxt
from flask import Flask
from threading import Thread

# --- CẤU HÌNH BOT ---
TOKEN = "8732938098:AAGrT0VC6B1mCMKPzdthChMUfGr2dv8tuZ0"
CHAT_ID = "6317501489"
SYMBOLS = {
    "BTC ₿": "BTC/USDT",
    "ETH Ξ": "ETH/USDT",
    "SOL ☀️": "SOL/USDT",
    "VÀNG 🏆": "PAXG/USDT"
}

app = Flask(__name__)

# Menu bàn phím
KEYBOARD = {
    "keyboard": [
        [{"text": "BTC ₿"}, {"text": "ETH Ξ"}],
        [{"text": "SOL ☀️"}, {"text": "VÀNG 🏆"}]
    ],
    "resize_keyboard": True
}

async def get_data_and_reply(name, symbol):
    # Dùng sàn OKX để tránh lỗi 451 (Restricted Location) trên Render
    ex = ccxt.okx() 
    try:
        ohlcv = await ex.fetch_ohlcv(symbol, timeframe='1h', limit=50)
        closes = [x[4] for x in ohlcv]
        current_price = closes[-1]
        
        # Tính RSI 14
        diff = [closes[i] - closes[i-1] for i in range(1, len(closes))]
        gain = sum([d for d in diff[-14:] if d > 0]) / 14
        loss = sum([-d for d in diff[-14:] if d < 0]) / 14
        rsi = round(100 - (100 / (1 + (gain/abs(loss)))), 2) if loss != 0 else 100
        
        # Xác định trạng thái dựa trên RSI
        if rsi <= 35:
            status = "LONG"
        elif rsi >= 65:
            status = "SHORT"
        else:
            status = "THEO DÕI"

        # Link ảnh Snapshot từ TradingView
        clean_sym = symbol.replace("/", "")
        photo_url = f"https://s3.tradingview.com/snapshots/c/{clean_sym}.png"

        # Nội dung tin nhắn tối giản (Không mũi tên)
        caption = (
            f"📊 *TÍN HIỆU: {name}*\n"
            f"━━━━━━━━━━━━━━━\n"
            f"📍 ENTRY: `{current_price}`\n"
            f"📈 RSI: `{rsi}`\n"
            f"🔍 TRẠNG THÁI: {status}\n"
            f"━━━━━━━━━━━━━━━\n"
            f"⏰ Khung: 1H | [Xem ảnh biểu đồ]({photo_url})"
        )
        
        requests.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage", json={
            "chat_id": CHAT_ID,
            "text": caption,
            "parse_mode": "Markdown",
            "reply_markup": KEYBOARD,
            "disable_web_page_preview": False
        })
        
    except Exception as e:
        print(f"Lỗi: {e}")
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
                        requests.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage", json={
                            "chat_id": CHAT_ID, "text": "Bot sẵn sàng!", "reply_markup": KEYBOARD
                        })
                    elif cmd in SYMBOLS:
                        await get_data_and_reply(cmd, SYMBOLS[cmd])
        except: pass
        await asyncio.sleep(1)

@app.route('/')
def home(): return "Bot Minimalism Active", 200

if __name__ == "__main__":
    Thread(target=lambda: app.run(host='0.0.0.0', port=10000)).start()
    asyncio.run(main_bot())
