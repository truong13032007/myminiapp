import asyncio
import ccxt.async_support as ccxt
from flask import Flask, jsonify
from flask_cors import CORS
from threading import Thread

app = Flask(__name__)
CORS(app)

# Token của bạn
API_TOKEN = "8732938098:AAGrT0VC6B1mCMKPzdthChMUfGr2dv8tuZ0"
SYMBOLS = ['BTC/USDT', 'ETH/USDT', 'SOL/USDT', 'BNB/USDT', 'XRP/USDT', 'ADA/USDT']
latest_signals = {}

# Hàm tính RSI "siêu nhẹ" - Không gây lỗi Render
def calculate_rsi(prices, period=14):
    if len(prices) < period + 1: return 50
    deltas = [prices[i] - prices[i-1] for i in range(1, len(prices))]
    seed = deltas[:period]
    up = sum(d for d in seed if d > 0) / period
    down = sum(-d for d in seed if d < 0) / period
    for d in deltas[period:]:
        up = (up * (period - 1) + (d if d > 0 else 0)) / period
        down = (down * (period - 1) + (-d if d < 0 else 0)) / period
    if down == 0: return 100
    rs = up / down
    return 100 - (100 / (1 + rs))

async def analyze(symbol, exchange):
    try:
        # Lấy ít dữ liệu nến hơn để máy chủ chạy nhanh hơn
        ohlcv = await exchange.fetch_ohlcv(symbol, timeframe='1h', limit=50)
        closes = [x[4] for x in ohlcv]
        rsi = calculate_rsi(closes)
        price = closes[-1]
        
        signal = "WAIT"
        if rsi < 35: signal = "LONG"
        elif rsi > 65: signal = "SHORT"
        
        return {"symbol": symbol, "price": price, "rsi": round(rsi, 1), "signal": signal}
    except: return None

async def loop():
    ex = ccxt.binance()
    while True:
        tasks = [analyze(s, ex) for s in SYMBOLS]
        res = await asyncio.gather(*tasks)
        for r in res:
            if r: latest_signals[r['symbol']] = r
        await asyncio.sleep(30)

@app.route('/api/signals')
def get_signals(): return jsonify(list(latest_signals.values()))

@app.route('/')
def home(): return "Bot is live and running!", 200

if __name__ == "__main__":
    # Khởi chạy Flask API
    Thread(target=lambda: app.run(host='0.0.0.0', port=5000)).start()
    # Khởi chạy vòng lặp soi coin
    asyncio.run(loop())
