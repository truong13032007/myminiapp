import asyncio
import requests
import ccxt.async_support as ccxt
from flask import Flask
from threading import Thread
import time

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

KEYBOARD = {
    "keyboard": [
        [{"text": "BTC ₿"}, {"text": "ETH Ξ"}],
        [{"text": "SOL ☀️"}, {"text": "VÀNG 🏆"}]
    ],
    "resize_keyboard": True
}

def send_photo(caption, symbol):
    # Lấy mã Coin bỏ dấu gạch chéo (ví dụ: BTCUSDT)
    clean_symbol = symbol.replace("/", "")
    # Link ảnh Snapshot trực tiếp từ TradingView (Dùng sàn OKX để tránh lỗi IP)
    photo_url = f"https://s3.tradingview.com/snapshots/c/{clean_symbol}.png"
    
    # Một số cặp tiền đặc biệt cần link khác, đây là link dự phòng chất lượng cao
    # Chúng ta sẽ gửi tin nhắn kèm link ảnh, Telegram sẽ tự hiển thị ảnh cực đẹp
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    
    # Để Telegram tự hiển thị ảnh (Preview), ta gửi link ảnh kèm nội dung
    text_content = f"{caption}\n\n[📊 Xem biểu đồ trực quan]({photo_url})"
    
    payload = {
        "chat_id": CHAT_ID,
        "text": text_content,
        "parse_mode": "Markdown",
        "reply_markup": KEYBOARD,
        "disable_web_page_preview": False # Quan trọng: Phải để False để hiện ảnh
    }
    try:
        requests.post(url, json=payload, timeout=10)
    except:
        pass

async def get_data_and_reply(name, symbol):
    # Dùng OKX để không bị lỗi 451 Restricted Location trên Render
    ex = ccxt.okx() 
    try:
        ohlcv = await ex.fetch_ohlcv(symbol, timeframe='1h', limit=50)
        closes = [x[4] for x in ohlcv]
        
        # Tính RSI
        diff = [closes[i] - closes[i-1] for i in range(1, len(closes))]
        gain = sum([d for d in diff[-14:] if d > 0]) / 14
        loss = sum([-d for d in diff[-14:] if d < 0]) / 14
        rs = gain / abs(loss) if loss != 0 else 0
        rsi = round(100 - (100 / (1 + rs)), 2)
        
        signal = "⚪ ĐANG CHỜ"
        arrow = "⌛"
        if rsi <= 35: 
            signal = "🟢 *LONG (MUA)*"
            arrow = "⬆️ MUA NGAY"
        elif rsi >= 65:
            signal = "🔴 *SHORT (BÁN)*"
            arrow = "⬇️ BÁN NGAY"

        caption = (f"🔔 *TÍN HIỆU {name}*\n"
                   f"━━━━━━━━━━━━━━━\n"
                   f"💰 Giá: `{closes[-1]}`\n"
                   f"📊 RSI: `{rsi}`\n"
                   f"👉 Lệnh: {signal}\n"
                   f"🎯 Chỉ báo: {arrow}\n"
                   f"━━━━━━━━━━━━━━━\n"
                   f"⏰ Khung: 1 Giờ (Data OKX)")
        
        send_photo(caption, symbol)
    except Exception as e:
        requests.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage", 
                      json={"chat_id": CHAT_ID, "text": f"Lỗi: {str(e)}"})
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
                                      json={"chat_id": CHAT_ID, "text": "🚀 Bot đã fix lỗi ảnh! Bấm nút để lấy kèo:", "reply_markup": KEYBOARD})
                    elif cmd in SYMBOLS:
                        await get_data_and_reply(cmd, SYMBOLS[cmd])
        except: pass
        await asyncio.sleep(1)

@app.route('/')
def home(): return "Bot Fix Invalid Key Active", 200

if __name__ == "__main__":
    Thread(target=lambda: app.run(host='0.0.0.0', port=10000)).start()
    asyncio.run(main_bot())
