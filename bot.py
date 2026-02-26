import asyncio
import ccxt.async_support as ccxt
import requests
import pandas as pd
import mplfinance as mpf
import os
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
last_signals = {}

# Hàm gửi ảnh kèm Menu bàn phím (ReplyKeyboardMarkup)
def send_tele_report(caption, photo_path=None):
    url_text = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    url_photo = f"https://api.telegram.org/bot{TOKEN}/sendPhoto"
    
    # Tạo Menu bàn phím cố định
    keyboard = {
        "keyboard": [
            [{"text": "BTC ₿"}, {"text": "ETH Ξ"}],
            [{"text": "SOL ☀️"}, {"text": "VÀNG 🏆"}]
        ],
        "resize_keyboard": True,
        "one_time_keyboard": False
    }

    try:
        if photo_path and os.path.exists(photo_path):
            with open(photo_path, 'rb') as photo:
                payload = {"chat_id": CHAT_ID, "caption": caption, "parse_mode": "Markdown", "reply_markup": keyboard}
                requests.post(url_photo, data=payload, files={'photo': photo}, timeout=10)
            os.remove(photo_path)
        else:
            payload = {"chat_id": CHAT_ID, "text": caption, "parse_mode": "Markdown", "reply_markup": keyboard}
            requests.post(url_text, json=payload, timeout=5)
    except Exception as e:
        print(f"Lỗi gửi tin: {e}")

def draw_chart(symbol, ohlcv, rsi, signal):
    df = pd.DataFrame(ohlcv, columns=['time', 'open', 'high', 'low', 'close', 'volume'])
    df['time'] = pd.to_datetime(df['time'], unit='ms')
    df.set_index('time', inplace=True)
    
    add_plots = []
    if signal == "LONG":
        add_plots.append(mpf.make_addplot(df['low'] * 0.99, type='scatter', marker='^', markersize=150, color='green'))
    elif signal == "SHORT":
        add_plots.append(mpf.make_addplot(df['high'] * 1.01, type='scatter', marker='v', markersize=150, color='red'))

    path = f"report.png"
    mpf.plot(df, type='candle', style='charles', addplot=add_plots, 
             title=f"{symbol} (RSI: {rsi})", savefig=path, tight_layout=True)
    return path

async def get_single_report(symbol):
    ex = ccxt.binance()
    try:
        ohlcv = await ex.fetch_ohlcv(symbol, timeframe='1h', limit=50)
        closes = [x[4] for x in ohlcv]
        diff = [closes[i] - closes[i-1] for i in range(1, len(closes))]
        up = sum([d for d in diff[-14:] if d > 0]) / 14
        down = sum([-d for d in diff[-14:] if d < 0]) / 14
        rsi = round(100 - (100 / (1 + (up/abs(down)))), 2) if down != 0 else 100
        
        signal = "WAIT"
        if rsi <= 30: signal = "LONG"
        elif rsi >= 70: signal = "SHORT"
        
        path = draw_chart(symbol, ohlcv, rsi, signal)
        txt = f"📊 *BÁO CÁO NHANH: {symbol}*\n💰 Giá: `{closes[-1]}`\n📈 RSI: `{rsi}`\n⚡ Tín hiệu: `{signal}`"
        send_tele_report(txt, path)
    finally:
        await ex.close()

# Quét tự động (Background task)
async def scan():
    ex = ccxt.binance({'enableRateLimit': True})
    while True:
        for name, s in SYMBOLS.items():
            try:
                ohlcv = await ex.fetch_ohlcv(s, timeframe='1h', limit=50)
                closes = [x[4] for x in ohlcv]
                diff = [closes[i] - closes[i-1] for i in range(1, len(closes))]
                up = sum([d for d in diff[-14:] if d > 0]) / 14
                down = sum([-d for d in diff[-14:] if d < 0]) / 14
                rsi = round(100 - (100 / (1 + (up/abs(down)))), 2) if down != 0 else 100
                
                signal = "WAIT"
                if rsi <= 30: signal = "LONG"
                elif rsi >= 70: signal = "SHORT"
                
                if signal != "WAIT" and last_signals.get(s) != signal:
                    path = draw_chart(s, ohlcv, rsi, signal)
                    txt = f"🚨 *CẢNH BÁO TÍN HIỆU {signal}*\n💎 Cặp: `{s}`\n📊 RSI: `{rsi}`"
                    send_tele_report(txt, path)
                    last_signals[s] = signal
                elif 40 < rsi < 60:
                    last_signals[s] = "WAIT"
            except: continue
        await asyncio.sleep(60)

# Nhận tin nhắn từ người dùng để hiện Menu
@app.route('/webhook', methods=['POST'])
def webhook():
    data = request.get_json()
    if "message" in data:
        text = data["message"].get("text")
        if text in SYMBOLS:
            asyncio.run(get_single_report(SYMBOLS[text]))
        else:
            send_tele_report("👋 Chào mừng! Hãy chọn coin muốn kiểm tra từ menu bên dưới:")
    return "OK", 200

@app.route('/')
def home(): return "Bot Live", 200

if __name__ == "__main__":
    Thread(target=lambda: app.run(host='0.0.0.0', port=10000)).start()
    asyncio.run(scan())
