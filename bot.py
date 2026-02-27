import asyncio
import requests
import ccxt.async_support as ccxt
import google.generativeai as genai
import pandas as pd
from flask import Flask
from threading import Thread
import time

# --- CẤU HÌNH ---
TOKEN = "8732938098:AAGrT0VC6B1mCMKPzdthChMUfGr2dv8tuZ0"
CHAT_ID = "6317501489"
GEMINI_KEY = "AIzaSyBV0eYnFTBON0WS0QN7T-4ZXjYYwArmyR4"

genai.configure(api_key=GEMINI_KEY)
ai_model = genai.GenerativeModel('gemini-1.5-flash')

SYMBOLS = {"BTC ₿": "BTC/USDT", "ETH Ξ": "ETH/USDT", "SOL ☀️": "SOL/USDT", "VÀNG 🏆": "PAXG/USDT"}
app = Flask(__name__)
KEYBOARD = {"keyboard": [[{"text": "BTC ₿"}, {"text": "ETH Ξ"}], [{"text": "SOL ☀️"}, {"text": "VÀNG 🏆"}]], "resize_keyboard": True}

# --- TÍNH TOÁN KỸ THUẬT THUẦN (KHÔNG CẦN PANDAS_TA) ---
def get_indicators(df):
    # RSI
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    df['RSI'] = 100 - (100 / (1 + (gain / loss)))
    # Bollinger Bands
    df['MA20'] = df['close'].rolling(window=20).mean()
    df['STD'] = df['close'].rolling(window=20).std()
    df['Upper'] = df['MA20'] + (df['STD'] * 2)
    df['Lower'] = df['MA20'] - (df['STD'] * 2)
    return df.iloc[-1]

async def analyze_and_report(sym, name, is_auto=False):
    ex = ccxt.okx({'timeout': 10000})
    try:
        bars = await ex.fetch_ohlcv(sym, timeframe='1h', limit=50)
        df = pd.DataFrame(bars, columns=['ts', 'open', 'high', 'low', 'close', 'vol'])
        last = get_indicators(df)
        
        # Lọc kèo cho tự động: Chỉ báo khi RSI chạm ngưỡng
        if is_auto and not (last['RSI'] <= 30 or last['RSI'] >= 70):
            return
            
        prompt = f"Bạn là chuyên gia trade. {name} giá {last['close']}, RSI {round(last['RSI'],1)}, BB {round(last['Lower'],1)}-{round(last['Upper'],1)}. Phán đoán dứt khoát: LONG/SHORT/ĐỨNG NGOÀI + Entry/TP/SL. Trả lời tiếng Việt súc tích."
        response = await asyncio.to_thread(ai_model.generate_content, prompt)
        ai_msg = response.text.strip()

        msg = (f"{'🔔 BÁO KÈO' if is_auto else '🏛 PHÂN TÍCH'}: *{name}*\n"
               f"━━━━━━━━━━━━━━━\n"
               f"💰 Giá: `{last['close']}` | RSI: `{round(last['RSI'],1)}`\n"
               f"📝 *AI PHÁN ĐOÁN:* \n_{ai_msg}_\n")
        
        requests.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage", 
                      json={"chat_id": CHAT_ID, "text": msg, "parse_mode": "Markdown", "reply_markup": KEYBOARD})
    except: pass
    finally: await ex.close()

# --- LUỒNG CHÍNH ---
async def main_worker():
    offset = 0
    last_auto_scan = 0
    while True:
        try:
            # 1. Quét nút bấm
            url = f"https://api.telegram.org/bot{TOKEN}/getUpdates?offset={offset}&timeout=5"
            res = requests.get(url, timeout=10).json()
            for update in res.get("result", []):
                offset = update["update_id"] + 1
                if "message" in update and "text" in update["message"]:
                    text = update["message"]["text"]
                    if text in SYMBOLS:
                        requests.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage", json={"chat_id": CHAT_ID, "text": "⏳ Chờ AI soi nến..."})
                        await analyze_and_report(SYMBOLS[text], text)
            
            # 2. Tự động quét (15 phút)
            if time.time() - last_auto_scan > 900:
                for name, sym in SYMBOLS.items():
                    await analyze_and_report(sym, name, is_auto=True)
                last_auto_scan = time.time()
        except: await asyncio.sleep(5)
        await asyncio.sleep(0.5)

@app.route('/')
def home(): return "Bot Online", 200

if __name__ == "__main__":
    Thread(target=lambda: app.run(host='0.0.0.0', port=10000)).start()
    asyncio.run(main_worker())
