import asyncio
import ccxt.async_support as ccxt
import requests
import pandas as pd
import mplfinance as mpf
import os
from flask import Flask
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
    "keyboard": [
        [{"text": "BTC ₿"}, {"text": "ETH Ξ"}],
        [{"text": "SOL ☀️"}, {"text": "VÀNG 🏆"}]
    ],
    "resize_keyboard": True
}

def send_msg(text):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    requests.post(url, json={"chat_id": CHAT_ID, "text": text, "parse_mode": "Markdown", "reply_markup": KEYBOARD})

def send_photo(caption, path):
    url = f"https://api.telegram.org/bot{TOKEN}/sendPhoto"
    with open(path, 'rb') as f:
        requests.post(url, data={"chat_id": CHAT_ID, "caption": caption, "parse_mode": "Markdown", "reply_markup": KEYBOARD}, files={'photo': f})
    if os.path.exists(path): os.remove(path)

def draw(symbol, ohlcv, rsi, signal):
    df = pd.DataFrame(ohlcv, columns=['time', 'open', 'high', 'low', 'close', 'volume'])
    df['time'] = pd.to_datetime(df['time'], unit='ms')
    df.set_index('time', inplace=True)
    add_p = []
    if signal == "LONG": add_p.append(mpf.make_addplot(df['low']*0.99, type='scatter', marker='^', markersize=100, color='green'))
    if signal == "SHORT": add_p.append(mpf.make_addplot(df['high']*1.01, type='scatter', marker='v', markersize=100, color='red'))
    path = "chart.png"
    mpf.plot(df, type='candle', style='charles', addplot=add_p, title=f"{symbol} RSI:{rsi}", savefig=path)
    return path

async def handle_input():
    offset = 0
    ex = ccxt.binance()
    send_msg("🚀 Bot đã sẵn sàng! Hãy chọn coin từ Menu bên dưới:")
    
    while True:
        try:
            # Kiểm tra tin nhắn mới
            url = f"https://api.telegram.org/bot{TOKEN}/getUpdates?offset={offset}&timeout=10"
            res = requests.get(url).json()
            
            for update in res.get("result", []):
                offset = update["update_id"] + 1
                msg = update.get("message", {}).get("text", "")
                
                if msg == "/start":
                    send_msg("📊 Chào mừng bạn! Bấm nút để xem tín hiệu:")
                elif msg in SYMBOLS:
                    s = SYMBOLS[msg]
                    ohlcv = await ex.fetch_ohlcv(s, timeframe='1h', limit=40)
                    closes = [x[4] for x in ohlcv]
                    # RSI 14
                    diff = [closes[i] - closes[i-1] for i in range(1, len(closes))]
                    up = sum([d for d in diff[-14:] if d > 0]) / 14
                    down = sum([-d for d in diff[-14:] if d < 0]) / 14
                    rsi = round(100 - (100 / (1 + (up/abs(down)))), 2) if down != 0 else 100
                    
                    sig = "LONG" if rsi <= 30 else ("SHORT" if rsi >= 70 else "WAIT")
                    img = draw(s, ohlcv, rsi, sig)
                    send_photo(f"✅ *{msg}*\n💰 Giá: `{closes[-1]}`\n📊 RSI: `{rsi}`\n⚡ Tín hiệu: `{sig}`", img)
        except: pass
        await asyncio.sleep(1)

@app.route('/')
def home(): return "Bot Active", 200

if __name__ == "__main__":
    Thread(target=lambda: app.run(host='0.0.0.0', port=10000)).start()
    asyncio.run(handle_input())
