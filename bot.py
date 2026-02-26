import asyncio
import requests
import ccxt.async_support as ccxt
from flask import Flask
from threading import Thread

# --- CẤU HÌNH BOT ---
TOKEN = "8732938098:AAGrT0VC6B1mCMKPzdthChMUfGr2dv8tuZ0"
CHAT_ID = "6317501489"
SYMBOLS = {
    "BTC ₿": "BTC/USDT", "ETH Ξ": "ETH/USDT",
    "SOL ☀️": "SOL/USDT", "VÀNG 🏆": "PAXG/USDT"
}

app = Flask(__name__)
KEYBOARD = {"keyboard": [[{"text": "BTC ₿"}, {"text": "ETH Ξ"}], [{"text": "SOL ☀️"}, {"text": "VÀNG 🏆"}]], "resize_keyboard": True}

def calculate_indicators(closes):
    # 1. Tính RSI
    diff = [closes[i] - closes[i-1] for i in range(1, len(closes))]
    gain = sum([d for d in diff[-14:] if d > 0]) / 14
    loss = sum([-d for d in diff[-14:] if d < 0]) / 14
    rsi = round(100 - (100 / (1 + (gain/abs(loss)))), 2) if loss != 0 else 100

    # 2. Tính Bollinger Bands (SMA 20)
    sma20 = sum(closes[-20:]) / 20
    variance = sum((x - sma20) ** 2 for x in closes[-20:]) / 20
    std_dev = variance ** 0.5
    upper_band = round(sma20 + (std_dev * 2), 2)
    lower_band = round(sma20 - (std_dev * 2), 2)

    # 3. Tính EMA cho MACD (đơn giản hóa)
    def ema(data, period):
        alpha = 2 / (period + 1)
        res = data[0]
        for price in data[1:]:
            res = (price * alpha) + (res * (1 - alpha))
        return res

    ema12 = ema(closes[-12:], 12)
    ema26 = ema(closes[-26:], 26)
    macd_line = ema12 - ema26
    
    return rsi, upper_band, lower_band, macd_line

async def get_data_and_reply(name, symbol):
    ex = ccxt.okx() 
    try:
        ohlcv = await ex.fetch_ohlcv(symbol, timeframe='1h', limit=50)
        closes = [x[4] for x in ohlcv]
        curr = closes[-1]
        
        rsi, upper, lower, macd = calculate_indicators(closes)
        
        # Logic phân tích đa chỉ báo
        analysis = "🔄 ĐANG QUAN SÁT"
        if rsi < 40 and curr <= lower:
            analysis = "🔥 TÍN HIỆU MUA MẠNH (RSI thấp + Chạm đáy BB)"
        elif rsi > 60 and curr >= upper:
            analysis = "⚠️ TÍN HIỆU BÁN MẠNH (RSI cao + Chạm đỉnh BB)"
        elif macd > 0:
            analysis = "📈 XU HƯỚNG TĂNG (MACD Dương)"
        elif macd < 0:
            analysis = "📉 XU HƯỚNG GIẢM (MACD Âm)"

        photo_url = f"https://s3.tradingview.com/snapshots/c/{symbol.replace('/', '')}.png"
        caption = (
            f"📊 *PHÂN TÍCH ĐA CHỈ BÁO: {name}*\n"
            f"━━━━━━━━━━━━━━━\n"
            f"📍 ENTRY: `{curr}`\n"
            f"📈 RSI: `{rsi}`\n"
            f"💠 BB: `{lower}` - `{upper}`\n"
            f"🌊 MACD: `{'Dương' if macd > 0 else 'Âm'}`\n"
            f"━━━━━━━━━━━━━━━\n"
            f"🔍 NHẬN ĐỊNH: *{analysis}*\n"
            f"⏰ Khung: 1H | [Xem biểu đồ]({photo_url})"
        )
        
        requests.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage", json={
            "chat_id": CHAT_ID, "text": caption, "parse_mode": "Markdown",
            "reply_markup": KEYBOARD, "disable_web_page_preview": False
        })
    except Exception as e: print(f"Lỗi: {e}")
    finally: await ex.close()

async def main_bot():
    offset = 0
    while True:
        try:
            url = f"https://api.telegram.org/bot{TOKEN}/getUpdates?offset={offset}&timeout=5"
            updates = requests.get(url).json()
            for update in updates.get("result", []):
                offset = update["update_id"] + 1
                if "message" in update and "text" in update["message"]:
                    cmd = update["message"]["text"]
                    if cmd == "/start":
                        requests.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage", json={"chat_id": CHAT_ID, "text": "Bot đa chỉ báo đã sẵn sàng!", "reply_markup": KEYBOARD})
                    elif cmd in SYMBOLS: await get_data_and_reply(cmd, SYMBOLS[cmd])
        except: pass
        await asyncio.sleep(1)

@app.route('/')
def home(): return "Bot Pro Indicators Active", 200

if __name__ == "__main__":
    Thread(target=lambda: app.run(host='0.0.0.0', port=10000)).start()
    asyncio.run(main_bot())
