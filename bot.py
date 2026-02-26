import asyncio
import ccxt.async_support as ccxt
from flask import Flask, jsonify
from flask_cors import CORS
from threading import Thread

app = Flask(__name__)
CORS(app)

API_TOKEN = "8732938098:AAGrT0VC6B1mCMKPzdthChMUfGr2dv8tuZ0"
SYMBOLS = ['BTC/USDT', 'ETH/USDT', 'SOL/USDT', 'BNB/USDT', 'XRP/USDT', 'ADA/USDT']
latest_signals = {}

# Hàm tính RSI thủ công để không bị lỗi Build
def calculate_rsi(prices, period=14):
    if len(prices) < period: return 50
    gains = []
    losses = []
    for i in range(1, len(prices)):
        diff = prices[i] - prices[i-1]
        gains.append(max(diff, 0))
        losses.append(max(-diff, 0))
    avg_gain = sum(gains[-period:]) / period
    avg_loss = sum(losses[-period:]) / period
    if avg_loss == 0: return 100
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))

async def analyze(symbol, exchange):
    try:
        ohlcv = await exchange.fetch_ohlcv(symbol, timeframe='1h', limit=50)
        closes = [x[4] for x in ohlcv]
        rsi = calculate_rsi(closes)
        price = closes[-1]
        
        signal = "WAIT"
        if rsi < 30: signal = "LONG"
        elif rsi > 70: signal = "SHORT"
        
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
def home(): return "Bot is live", 200

if __name__ == "__main__":
    Thread(target=lambda: app.run(host='0.0.0.0', port=5000)).start()
    asyncio.run(loop())
