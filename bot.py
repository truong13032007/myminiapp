import asyncio
import ccxt.async_support as ccxt
from flask import Flask, jsonify
from flask_cors import CORS  # PHẢI CÓ DÒNG NÀY
from threading import Thread
import requests
import time

app = Flask(__name__)
CORS(app)  # PHẢI CÓ DÒNG NÀY ĐỂ SỬA LỖI "ĐANG CHỜ API"

# Cấu hình của bạn
TELEGRAM_TOKEN = "8732938098:AAGrT0VC6B1mCMKPzdthChMUfGr2dv8tuZ0"
TELEGRAM_CHAT_ID = "6317501489"
SYMBOLS = ['BTC/USDT', 'ETH/USDT', 'SOL/USDT', 'PAXG/USDT']

latest_signals = {}

def send_tele(msg):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": msg, "parse_mode": "Markdown"}, timeout=5)
    except: pass

async def analyze(symbol, exchange):
    try:
        ohlcv = await exchange.fetch_ohlcv(symbol, timeframe='1h', limit=50)
        closes = [x[4] for x in ohlcv]
        # RSI đơn giản
        avg_gain = sum([max(0, closes[i] - closes[i-1]) for i in range(1, 15)]) / 14
        avg_loss = sum([max(0, closes[i-1] - closes[i]) for i in range(1, 15)]) / 14
        rs = avg_gain / avg_loss if avg_loss != 0 else 0
        rsi = round(100 - (100 / (1 + rs)), 2)
        
        signal = "WAIT"
        if rsi <= 30: signal = "LONG"
        elif rsi >= 70: signal = "SHORT"
        
        return {"symbol": symbol, "price": closes[-1], "rsi": rsi, "signal": signal}
    except: return None

async def worker():
    ex = ccxt.binance({'enableRateLimit': True})
    while True:
        tasks = [analyze(s, ex) for s in SYMBOLS]
        results = await asyncio.gather(*tasks)
        for r in results:
            if r: 
                if r['signal'] != "WAIT" and latest_signals.get(r['symbol'], {}).get('signal') != r['signal']:
                    send_tele(f"🚨 *{r['signal']} SIGNAL*: {r['symbol']}\nGiá: `{r['price']}` | RSI: `{r['rsi']}`")
                latest_signals[r['symbol']] = r
        await asyncio.sleep(20)

@app.route('/api/signals')
def get_signals():
    # Thêm header thủ công để chắc chắn không bị chặn
    response = jsonify(list(latest_signals.values()))
    return response

@app.route('/')
def home(): return "API IS LIVE", 200

if __name__ == "__main__":
    Thread(target=lambda: app.run(host='0.0.0.0', port=5000)).start()
    asyncio.run(worker())
