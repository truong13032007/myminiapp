import asyncio
import ccxt.async_support as ccxt
import pandas_ta as ta
import pandas as pd
from flask import Flask, jsonify
from flask_cors import CORS
from threading import Thread

app = Flask(__name__)
CORS(app)

# Token của bạn đã được nạp vào đây
API_TOKEN = "8732938098:AAGrT0VC6B1mCMKPzdthChMUfGr2dv8tuZ0"

SYMBOLS = ['BTC/USDT', 'ETH/USDT', 'SOL/USDT', 'BNB/USDT', 'XRP/USDT', 'ADA/USDT', 'AVAX/USDT', 'DOT/USDT']
latest_signals = {}

async def analyze(symbol, exchange):
    try:
        ohlcv = await exchange.fetch_ohlcv(symbol, timeframe='1h', limit=100)
        df = pd.DataFrame(ohlcv, columns=['ts', 'o', 'h', 'l', 'c', 'v'])
        df['RSI'] = ta.rsi(df['c'], length=14)
        df['EMA200'] = ta.ema(df['c'], length=200)
        last = df.iloc[-1]
        
        signal = "WAIT"
        if last['RSI'] < 30: signal = "LONG"
        elif last['RSI'] > 70: signal = "SHORT"
        
        return {"symbol": symbol, "price": last['c'], "rsi": round(last['RSI'], 1), "signal": signal}
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
