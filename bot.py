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
SYMBOLS = ['BTC/USDT', 'ETH/USDT', 'SOL/USDT', 'PAXG/USDT']

app = Flask(__name__)
last_signals = {}

def send_tele_photo(caption, photo_path):
    # Menu nút bấm để chọn nhanh các cặp coin
    keyboard = {
        "inline_keyboard": [
            [{"text": "₿ BTC", "callback_data": "BTC/USDT"}, {"text": "Ξ ETH", "callback_data": "ETH/USDT"}],
            [{"text": "☀️ SOL", "callback_data": "SOL/USDT"}, {"text": "🏆 VÀNG (PAXG)", "callback_data": "PAXG/USDT"}]
        ]
    }
    url = f"https://api.telegram.org/bot{TOKEN}/sendPhoto"
    try:
        with open(photo_path, 'rb') as photo:
            payload = {
                "chat_id": CHAT_ID,
                "caption": caption,
                "parse_mode": "Markdown",
                "reply_markup": keyboard
            }
            requests.post(url, data=payload, files={'photo': photo}, timeout=10)
    except Exception as e:
        print(f"Lỗi gửi ảnh: {e}")

def draw_chart(symbol, ohlcv, rsi, signal):
    df = pd.DataFrame(ohlcv, columns=['time', 'open', 'high', 'low', 'close', 'volume'])
    df['time'] = pd.to_datetime(df['time'], unit='ms')
    df.set_index('time', inplace=True)
    
    # Thiết lập mũi tên tín hiệu
    add_plots = []
    if signal == "LONG":
        add_plots.append(mpf.make_addplot(df['low'] * 0.99, type='scatter', marker='^', markersize=100, color='green'))
    elif signal == "SHORT":
        add_plots.append(mpf.make_addplot(df['high'] * 1.01, type='scatter', marker='v', markersize=100, color='red'))

    path = "signal_chart.png"
    mpf.plot(df, type='candle', style='charles', addplot=add_plots, 
             title=f"\n{symbol} - RSI: {rsi}", savefig=path)
    return path

async def scan():
    ex = ccxt.binance({'enableRateLimit': True})
    while True:
        for s in SYMBOLS:
            try:
                ohlcv = await ex.fetch_ohlcv(s, timeframe='1h', limit=50)
                closes = [x[4] for x in ohlcv]
                
                # Tính RSI
                diff = [closes[i] - closes[i-1] for i in range(1, len(closes))]
                up = sum([d for d in diff[-14:] if d > 0]) / 14
                down = sum([-d for d in diff[-14:] if d < 0]) / 14
                rsi = round(100 - (100 / (1 + (up/abs(down)))), 2) if down != 0 else 100
                
                signal = "WAIT"
                if rsi <= 30: signal = "LONG"
                elif rsi >= 70: signal = "SHORT"
                
                if signal != "WAIT" and last_signals.get(s) != signal:
                    img = draw_chart(s, ohlcv, rsi, signal)
                    txt = f"🚨 *TÍN HIỆU {signal}*\n💎 Cặp: `{s}`\n📊 RSI: `{rsi}`\n💰 Giá: `{closes[-1]}`"
                    send_tele_photo(txt, img)
                    last_signals[s] = signal
                elif 40 < rsi < 60:
                    last_signals[s] = "WAIT"
            except: continue
        await asyncio.sleep(60)

@app.route('/')
def home():
    return "Bot Telegram is running. Index.html deleted.", 200

if __name__ == "__main__":
    # Chạy Web Server để Render không tắt Bot
    Thread(target=lambda: app.run(host='0.0.0.0', port=10000)).start()
    asyncio.run(scan())
