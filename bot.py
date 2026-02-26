import asyncio
import ccxt.async_support as ccxt
from flask import Flask, jsonify
from flask_cors import CORS  # Thư viện xử lý lỗi chặn truy cập
from threading import Thread
import requests

app = Flask(__name__)
CORS(app) # Dòng này sẽ sửa lỗi "Đang kết nối..." không load được

TELEGRAM_TOKEN = "8732938098:AAGrT0VC6B1mCMKPzdthChMUfGr2dv8tuZ0"
TELEGRAM_CHAT_ID = "6317501489"
# Chỉ giữ lại những mã Hot nhất để quét cực nhanh
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
        # Tính RSI đơn giản
        deltas = [closes[i] - closes[i-1] for i in range(1, len(closes))]
        up = sum(d for d in deltas if d > 0) / 14
        down = sum(-d for d in deltas if d < 0) / 14
        rsi = round(100 - (100 / (1 + (up/down))), 2) if down != 0 else 100
        
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
                # Nếu có tín hiệu mới thì báo Tele luôn
                if r['signal'] != "WAIT" and latest_signals.get(r['symbol'], {}).get('signal') != r['signal']:
                    send_tele(f"🚨 *{r['signal']}*: {r['symbol']}\nGiá: {r['price']}")
                latest_signals[r['symbol']] = r
        await asyncio.sleep(15)

@app.route('/api/signals')
def get_signals(): return jsonify(list(latest_signals.values()))

@app.route('/')
def home(): return "SERVER LIVE", 200

if __name__ == "__main__":
    Thread(target=lambda: app.run(host='0.0.0.0', port=5000)).start()
    asyncio.run(worker())
