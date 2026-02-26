import asyncio
import ccxt.async_support as ccxt
from flask import Flask, jsonify
from flask_cors import CORS
from threading import Thread
import requests
import time

app = Flask(__name__)
CORS(app) # Cho phép index.html kết nối

# Cấu hình Telegram của bạn
TOKEN = "8732938098:AAGrT0VC6B1mCMKPzdthChMUfGr2dv8tuZ0"
CHAT_ID = "6317501489"
# Danh sách coin hot rút gọn để tránh quá tải
SYMBOLS = ['BTC/USDT', 'ETH/USDT', 'SOL/USDT', 'PAXG/USDT', 'BNB/USDT', 'DOGE/USDT']

data_store = {}

def alert_tele(msg):
    try:
        url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
        requests.post(url, json={"chat_id": CHAT_ID, "text": msg, "parse_mode": "Markdown"}, timeout=5)
    except: pass

async def get_signal(symbol, ex):
    try:
        ohlcv = await ex.fetch_ohlcv(symbol, timeframe='1h', limit=30)
        closes = [x[4] for x in ohlcv]
        # RSI 14 đơn giản
        diff = [closes[i] - closes[i-1] for i in range(1, len(closes))]
        gain = sum([d for d in diff[-14:] if d > 0]) / 14
        loss = sum([-d for d in diff[-14:] if d < 0]) / 14
        rs = gain / loss if loss != 0 else 0
        rsi = round(100 - (100 / (1 + rs)), 2)
        
        signal = "WAIT"
        if rsi <= 30: signal = "LONG"
        elif rsi >= 70: signal = "SHORT"
        
        res = {"symbol": symbol, "price": closes[-1], "rsi": rsi, "signal": signal}
        
        # Báo Telegram nếu có kèo mới
        old_sig = data_store.get(symbol, {}).get('signal', 'WAIT')
        if signal != "WAIT" and signal != old_sig:
            alert_tele(f"🔥 *{signal} SIGNAL*: {symbol}\n💰 Giá: `{closes[-1]}`\n📊 RSI: `{rsi}`")
            
        return res
    except: return None

async def main_loop():
    ex = ccxt.binance()
    while True:
        tasks = [get_signal(s, ex) for s in SYMBOLS]
        results = await asyncio.gather(*tasks)
        for r in results:
            if r: data_store[r['symbol']] = r
        await asyncio.sleep(20)

@app.route('/api/signals')
def api():
    return jsonify(list(data_store.values()))

@app.route('/')
def home():
    return "BOT IS RUNNING", 200

if __name__ == "__main__":
    # Chạy quét coin trong một luồng riêng
    t = Thread(target=lambda: asyncio.run(main_loop()))
    t.start()
    # Chạy Web Server
    app.run(host='0.0.0.0', port=5000)
