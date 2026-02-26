import asyncio
import requests
import ccxt.async_support as ccxt
from flask import Flask, request
from threading import Thread

# --- CẤU HÌNH ---
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
    "keyboard": [[{"text": "BTC ₿"}, {"text": "ETH Ξ"}], [{"text": "SOL ☀️"}, {"text": "VÀNG 🏆"}]],
    "resize_keyboard": True
}

def send_msg(text):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    requests.post(url, json={"chat_id": CHAT_ID, "text": text, "parse_mode": "Markdown", "reply_markup": KEYBOARD})

def send_photo_url(caption, photo_url):
    url = f"https://api.telegram.org/bot{TOKEN}/sendPhoto"
    payload = {
        "chat_id": CHAT_ID,
        "photo": photo_url,
        "caption": caption,
        "parse_mode": "Markdown",
        "reply_markup": KEYBOARD
    }
    requests.post(url, json=payload)

async def get_signal_and_send(name, symbol):
    ex = ccxt.binance()
    try:
        # Lấy dữ liệu nhanh
        ohlcv = await ex.fetch_ohlcv(symbol, timeframe='1h', limit=50)
        closes = [x[4] for x in ohlcv]
        
        # Tính RSI
        diff = [closes[i] - closes[i-1] for i in range(1, len(closes))]
        up = sum([d for d in diff[-14:] if d > 0]) / 14
        down = sum([-d for d in diff[-14:] if d < 0]) / 14
        rsi = round(100 - (100 / (1 + (up/abs(down)))), 2) if down != 0 else 100
        
        # Xác định tín hiệu
        sig_text = "⚪ ĐANG CHỜ"
        icon = ""
        if rsi <= 35: # Nới lỏng vùng báo để dễ thấy mũi tên
            sig_text = "🟢 MUA (LONG)"
            icon = "buy"
        elif rsi >= 65:
            sig_text = "🔴 BÁN (SHORT)"
            icon = "sell"

        # LẤY ẢNH TỪ SERVER BIỂU ĐỒ (SIÊU NHANH)
        # Sử dụng mã symbol chuẩn cho URL ảnh
        tv_sym = symbol.replace("/", "").upper()
        # Tạo link ảnh biểu đồ chuyên nghiệp (đã có sẵn nến và RSI)
        photo_url = f"https://s3.tradingview.com/snapshots/s/sRInIeW6.png" # Link snapshot gốc
        # Lưu ý: Vì snapshot cần ID cụ thể, ta dùng link thay thế cực nhanh:
        photo_url = f"https://api.screenshotmachine.com/?key=bc8945&url=https://www.tradingview.com/chart/?symbol=BINANCE:{tv_sym}&dimension=1024x768"

        caption = (f"💎 *{name}* ({symbol})\n"
                   f"💰 Giá: `{closes[-1]}`\n"
                   f"📊 RSI: `{rsi}`\n"
                   f"⚡ Tín hiệu: *{sig_text}*\n"
                   f"━━━━━━━━━━━━━━━\n"
                   f"{'🚀 ĐẶT LỆNH LONG NGAY' if icon == 'buy' else ('📉 ĐẶT LỆNH SHORT NGAY' if icon == 'sell' else '👉 Theo dõi thêm')}")
        
        send_photo_url(caption, photo_url)
    except Exception as e:
        send_msg(f"Lỗi: {e}")
    finally:
        await ex.close()

async def worker():
    offset = 0
    while True:
        try:
            url = f"https://api.telegram.org/bot{TOKEN}/getUpdates?offset={offset}&timeout=10"
            res = requests.get(url, timeout=10).json()
            for update in res.get("result", []):
                offset = update["update_id"] + 1
                if "message" in update and "text" in update["message"]:
                    text = update["message"]["text"]
                    if text in SYMBOLS:
                        # Gửi xác nhận tức thì
                        requests.post(f"https://api.telegram.org/bot{TOKEN}/sendChatAction", json={"chat_id": CHAT_ID, "action": "upload_photo"})
                        await get_signal_and_send(text, SYMBOLS[text])
                    elif text == "/start":
                        send_msg("👋 Bot đã Online! Chọn Coin để xem kèo có mũi tên:")
        except: pass
        await asyncio.sleep(1)

@app.route('/')
def home(): return "Bot Running", 200

if __name__ == "__main__":
    Thread(target=lambda: app.run(host='0.0.0.0', port=10000)).start()
    asyncio.run(worker())
