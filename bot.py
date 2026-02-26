import asyncio
import ccxt.async_support as ccxt
from flask import Flask, jsonify
from flask_cors import CORS
from threading import Thread
import requests

app = Flask(__name__)
CORS(app)

# --- CẤU HÌNH ---
TELEGRAM_TOKEN = "8732938098:AAGrT0VC6B1mCMKPzdthChMUfGr2dv8tuZ0"
TELEGRAM_CHAT_ID = "6317501489" # Đã thay ID của bạn

# Danh sách Coin Hot + Vàng (PAXG)
SYMBOLS = [
    'BTC/USDT', 'ETH/USDT', 'SOL/USDT', 'BNB/USDT', 
    'PAXG/USDT', # Vàng
    'XRP/USDT', 'DOGE/USDT', 'PEPE/USDT', 'LINK/USDT'
]

latest_signals = {}
last_sent_signals = {} # Tránh spam tin nhắn

def send_telegram_message(message):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        payload = {
            "chat_id": TELEGRAM_CHAT_ID, 
            "text": message, 
            "parse_mode": "Markdown"
        }
        requests.post(url, json=payload, timeout=5)
    except Exception as e:
        print(f"Lỗi gửi Telegram: {e}")

def calculate_rsi(prices, period=14):
    if len(prices) < period + 1: return 50
    deltas = [prices[i] - prices[i-1] for i in range(1, len(prices))]
    up = sum(d for d in deltas[:period] if d > 0) / period
    down = sum(-d for d in deltas[:period] if d < 0) / period
    for d in deltas[period:]:
        up = (up * (period - 1) + (d if d > 0 else 0)) / period
        down = (down * (period - 1) + (-d if d < 0 else 0)) / period
    if down == 0: return 100
    rs = up / down
    return 100 - (100 / (1 + rs))

async def analyze(symbol, exchange):
    try:
        # Lấy dữ liệu nến 1h
        ohlcv = await exchange.fetch_ohlcv(symbol, timeframe='1h', limit=50)
        closes = [x[4] for x in ohlcv]
        rsi = calculate_rsi(closes)
        price = closes[-1]
        
        signal = "WAIT"
        if rsi <= 30: signal = "LONG"
        elif rsi >= 70: signal = "SHORT"
        
        data = {"symbol": symbol, "price": price, "rsi": round(rsi, 1), "signal": signal}
        
        # Xử lý gửi tin nhắn Telegram
        if signal != "WAIT":
            if last_sent_signals.get(symbol) != signal:
                emoji = "🟢 *MUA (LONG)*" if signal == "LONG" else "🔴 *BÁN (SHORT)*"
                action_icon = "🚀" if signal == "LONG" else "📉"
                
                name = "VÀNG (Gold)" if symbol == "PAXG/USDT" else symbol
                
                msg = (f"{action_icon} *TÍN HIỆU {signal} MỚI*\n"
                       f"━━━━━━━━━━━━━━━\n"
                       f"💎 Cặp tiền: `{name}`\n"
                       f"⚡ Hành động: {emoji}\n"
                       f"💰 Giá vào: `{price}`\n"
                       f"📊 RSI: `{round(rsi, 2)}` (H1)\n"
                       f"━━━━━━━━━━━━━━━\n"
                       f"🤖 *Bot Pro Signal System*")
                
                send_telegram_message(msg)
                last_sent_signals[symbol] = signal
        else:
            # Reset trạng thái khi RSI quay lại vùng an toàn (ví dụ từ 40-60)
            if 40 < rsi < 60:
                last_sent_signals[symbol] = "WAIT"
            
        return data
    except Exception as e:
        return None

async def loop():
    print("Bot đang khởi động và quét tín hiệu...")
    ex = ccxt.binance({'enableRateLimit': True})
    while True:
        tasks = [analyze(s, ex) for s in SYMBOLS]
        results = await asyncio.gather(*tasks)
        for r in results:
            if r: latest_signals[r['symbol']] = r
        # Nghỉ 20 giây mỗi chu kỳ quét
        await asyncio.sleep(20)

@app.route('/api/signals')
def get_signals():
    return jsonify(list(latest_signals.values()))

@app.route('/')
def home():
    return "Bot Telegram & Web API is Running!", 200

if __name__ == "__main__":
    # Chạy Web Server trong luồng riêng
    t = Thread(target=lambda: app.run(host='0.0.0.0', port=5000))
    t.start()
    # Chạy vòng lặp phân tích
    asyncio.run(loop())
