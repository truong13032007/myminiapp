import asyncio
import requests
import pandas as pd
import mplfinance as mpf
import os
from flask import Flask
from threading import Thread
import time
import ccxt.async_support as ccxt

# --- CẤU HÌNH ---
TOKEN = "8732938098:AAGrT0VC6B1mCMKPzdthChMUfGr2dv8tuZ0"
CHAT_ID = "6317501489"

# Map tên nút bấm với mã symbol (dùng cho cả CCXT và tên file ảnh)
SYMBOLS = {
    "BTC ₿": "BTC/USDT",
    "ETH Ξ": "ETH/USDT",
    "SOL ☀️": "SOL/USDT",
    "VÀNG 🏆": "PAXG/USDT"
}

app = Flask(__name__)

KEYBOARD = {
    "keyboard": [[{"text": "BTC ₿"}, {"text": "ETH Ξ"}], [{"text": "SOL ☀️"}, {"text": "VÀNG 🏆"}]],
    "resize_keyboard": True
}

# --- HÀM GỬI ẢNH KÈM THÔNG BÁO ---
def send_photo_with_caption(caption, photo_path):
    url = f"https://api.telegram.org/bot{TOKEN}/sendPhoto"
    try:
        with open(photo_path, 'rb') as f:
            requests.post(url, data={"chat_id": CHAT_ID, "caption": caption, "parse_mode": "Markdown", "reply_markup": KEYBOARD}, files={'photo': f}, timeout=20)
        if os.path.exists(photo_path): os.remove(photo_path) # Xóa ảnh sau khi gửi
    except Exception as e:
        print(f"Lỗi gửi ảnh: {e}")

# --- HÀM VẼ BIỂU ĐỒ (Dùng lại mplfinance) ---
def draw_chart_with_signal(symbol_ccxt, ohlcv_data, rsi, signal):
    df = pd.DataFrame(ohlcv_data, columns=['time', 'open', 'high', 'low', 'close', 'volume'])
    df['time'] = pd.to_datetime(df['time'], unit='ms')
    df.set_index('time', inplace=True)
    
    add_plots = []
    if signal == "LONG":
        add_plots.append(mpf.make_addplot(df['low'] * 0.99, type='scatter', marker='^', markersize=150, color='green'))
    elif signal == "SHORT":
        add_plots.append(mpf.make_addplot(df['high'] * 1.01, type='scatter', marker='v', markersize=150, color='red'))

    file_path = f"chart_{symbol_ccxt.replace('/', '')}.png"
    mpf.plot(df, type='candle', style='charles', addplot=add_plots, 
             title=f"{symbol_ccxt} (RSI: {rsi:.2f})", savefig=file_path, tight_layout=True)
    return file_path

# --- HÀM XỬ LÝ LỆNH BẤM NÚT ---
async def handle_buttons():
    offset = 0
    ex = ccxt.binance({'enableRateLimit': True}) # Khởi tạo exchange một lần
    while True:
        try:
            url = f"https://api.telegram.org/bot{TOKEN}/getUpdates?offset={offset}&timeout=5"
            res = requests.get(url).json()
            for update in res.get("result", []):
                offset = update["update_id"] + 1
                if "message" in update and "text" in update["message"]:
                    text = update["message"]["text"]
                    if text in SYMBOLS: # Người dùng bấm nút coin
                        symbol_ccxt = SYMBOLS[text]
                        # Gửi tin nhắn "Đang xử lý..." trước
                        requests.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage", json={"chat_id": CHAT_ID, "text": f"Đang tải biểu đồ {text}...", "reply_markup": KEYBOARD})
                        
                        # --- Thực hiện tính toán và vẽ ảnh ---
                        ohlcv = await ex.fetch_ohlcv(symbol_ccxt, timeframe='1h', limit=50)
                        closes = [x[4] for x in ohlcv]
                        
                        diff = [closes[i] - closes[i-1] for i in range(1, len(closes))]
                        up = sum([d for d in diff[-14:] if d > 0]) / 14
                        down = sum([-d for d in diff[-14:] if d < 0]) / 14
                        rsi = 100 - (100 / (1 + (up / abs(down)))) if down != 0 else 100
                        
                        signal = "LONG" if rsi <= 30 else ("SHORT" if rsi >= 70 else "WAIT")
                        
                        img_path = draw_chart_with_signal(symbol_ccxt, ohlcv, rsi, signal)
                        caption = f"📊 *BIỂU ĐỒ {text}*\n💰 Giá: `{closes[-1]}`\n📈 RSI: `{rsi:.2f}`\n⚡ Tín hiệu: *{signal}*"
                        send_photo_with_caption(caption, img_path)
                    elif text == "/start":
                        requests.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage", 
                                      json={"chat_id": CHAT_ID, "text": "Bấm nút để xem biểu đồ và tín hiệu:", "reply_markup": KEYBOARD})
        except Exception as e:
            print(f"Lỗi xử lý nút: {e}")
        await asyncio.sleep(0.5)

@app.route('/')
def home(): return "Bot Active", 200

if __name__ == "__main__":
    # Chạy Flask server trong luồng riêng
    Thread(target=lambda: app.run(host='0.0.0.0', port=10000)).start()
    # Chạy vòng lặp xử lý nút bấm
    asyncio.run(handle_buttons())
