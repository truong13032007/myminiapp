import asyncio
import ccxt.async_support as ccxt
from flask import Flask, jsonify
from flask_cors import CORS
from threading import Thread
import requests
import time

app = Flask(__name__)
CORS(app)

# CẤU HÌNH
TELEGRAM_TOKEN = "8732938098:AAGrT0VC6B1mCMKPzdthChMUfGr2dv8tuZ0"
TELEGRAM_CHAT_ID = "6317501489"
SYMBOLS = ['BTC/USDT', 'ETH/USDT', 'SOL/USDT', 'BNB/USDT', 'PAXG/USDT', 'XRP/USDT', 'DOGE/USDT', 'PEPE/USDT']

latest_signals = {}
last_sent_signals = {}

def send_telegram(message):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "Markdown"}, timeout=5)
    except: pass

def calculate_rsi(prices, period=14):
    if len(prices) < period + 1: return 50
    deltas = [prices[i] - prices[i-1] for i in range(1, len(prices))]
    up = sum(d for d in deltas[:period] if d > 0) / period
    down = sum(-d for d in deltas[:period] if d < 0) / period
    for d in deltas[period:]:
        up = (up * (period - 1) + (d if d > 0 else 0)) / period
        down = (down * (period - 1) + (-d if d < 0 else 0)) / period
    return 100 - (100 / (1 + (up/down))) if down != 0 else 100

async def analyze(symbol, exchange):
    try:
        ohlcv = await exchange.fetch_ohlcv(symbol, timeframe='1h', limit=50)
        closes = [x[4] for x in ohlcv]
        rsi = round(calculate_rsi(closes), 2)
        price = closes[-1]
        
        signal = "WAIT"
        if rsi <= 30: signal = "LONG"
        elif rsi >= 70: signal = "SHORT"
        
        data = {"symbol": symbol, "price": price, "rsi": rsi, "signal": signal, "time": time.time()}
        
        if signal != "WAIT" and last_sent_signals.get(symbol) != signal:
            name = "VÀNG (Gold)" if symbol == "PAXG/USDT" else symbol
            send_telegram(f"🚀 *{signal} SIGNAL: {name}*\n💰 Giá: `{price}` | RSI: `{rsi}`")
            last_sent_signals[symbol] = signal
        elif 40 < rsi < 60:
            last_sent_signals[symbol] = "WAIT"
        return data
    except: return None

async def worker():
    ex = ccxt.binance({'enableRateLimit': True})
    while True:
        tasks = [analyze(s, ex) for s in SYMBOLS]
        results = await asyncio.gather(*tasks)
        for r in results:
            if r: latest_signals[r['symbol']] = r
        await asyncio.sleep(15)

@app.route('/api/signals')
def get_signals():
    return jsonify(list(latest_signals.values()))

@app.route('/')
def home(): return "OK", 200

if __name__ == "__main__":
    Thread(target=lambda: app.run(host='0.0.0.0', port=5000)).start()
    asyncio.run(worker())
