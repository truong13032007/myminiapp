import asyncio
import requests
import ccxt.async_support as ccxt
import google.generativeai as genai
import pandas as pd
import pandas_ta as ta
from flask import Flask
from threading import Thread
import time

# --- CẤU HÌNH ---
TOKEN = "8732938098:AAGrT0VC6B1mCMKPzdthChMUfGr2dv8tuZ0"
CHAT_ID = "6317501489"
GEMINI_KEY = "AIzaSyBV0eYnFTBON0WS0QN7T-4ZXjYYwArmyR4"

genai.configure(api_key=GEMINI_KEY)
ai_model = genai.GenerativeModel('gemini-1.5-flash')

SYMBOLS = {
    "BTC ₿": "BTC/USDT", "ETH Ξ": "ETH/USDT",
    "SOL ☀️": "SOL/USDT", "VÀNG 🏆": "PAXG/USDT"
}

app = Flask(__name__)
KEYBOARD = {"keyboard": [[{"text": "BTC ₿"}, {"text": "ETH Ξ"}], [{"text": "SOL ☀️"}, {"text": "VÀNG 🏆"}]], "resize_keyboard": True}

# --- HÀM PHÂN TÍCH CHUYÊN SÂU ---
async def fetch_and_analyze(sym, is_auto=False):
    ex = ccxt.okx({'timeout': 10000})
    try:
        bars = await ex.fetch_ohlcv(sym, timeframe='1h', limit=100)
        df = pd.DataFrame(bars, columns=['ts', 'open', 'high', 'low', 'close', 'vol'])
        
        # Chỉ báo kỹ thuật
        df['RSI'] = ta.rsi(df['close'], length=14)
        bbands = ta.bbands(df['close'], length=20, std=2)
        df = pd.concat([df, bbands], axis=1)
        
        last = df.iloc[-1]
        
        # Nếu là tự động quét, chỉ báo kèo khi thực sự ngon (RSI < 30 hoặc > 70)
        if is_auto:
            if not (last['RSI'] <= 30 or last['RSI'] >= 70):
                return None, None
        
        # Gọi AI soi kèo
        prompt = f"""
        Bạn là Chuyên gia Trading. Cặp {sym} giá {last['close']}, RSI {round(last['RSI'],1)}.
        BB: {round(last['BBL_20_2.0'],2)} - {round(last['BBU_20_2.0'],2)}.
        Nhiệm vụ: Phân tích nến và phán đoán dứt khoát: LONG, SHORT hoặc ĐỨNG NGOÀI.
        Yêu cầu có: Entry, TP, SL rõ ràng. Trả lời tiếng Việt súc tích.
        """
        response = await asyncio.to_thread(ai_model.generate_content, prompt)
        return last, response.text.strip()
    except:
        return None, None
    finally:
        await ex.close()

# --- LUỒNG TỰ ĐỘNG QUÉT KÈO (10 PHÚT/LẦN) ---
async def auto_scanner():
    last_alerts = {s: 0 for s in SYMBOLS}
    while True:
        try:
            for name, sym in SYMBOLS.items():
                data, ai_msg = await fetch_and_analyze(sym, is_auto=True)
                # Nếu có tín hiệu đẹp và giá đã thay đổi so với lần báo trước
                if data is not None and last_alerts[name] != data['close']:
                    msg = (f"🔔 *BÁO KÈO TỰ ĐỘNG: {name}*\n"
                           f"━━━━━━━━━━━━━━━\n"
                           f"💰 Giá: `{data['close']}` | RSI: `{round(data['RSI'],1)}`\n"
                           f"📝 *AI PHÁN ĐOÁN:* \n_{ai_msg}_\n")
                    requests.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage", 
                                  json={"chat_id": CHAT_ID, "text": msg, "parse_mode": "Markdown"})
                    last_alerts[name] = data['close']
            await asyncio.sleep(600) # Nghỉ 10 phút
        except:
            await asyncio.sleep(10)

# --- LUỒNG XỬ LÝ NÚT BẤM ---
async def button_handler():
    offset = 0
    while True:
        try:
            url = f"https://api.telegram.org/bot{TOKEN}/getUpdates?offset={offset}&timeout=10"
            res = requests.get(url, timeout=15).json()
            for update in res.get("result", []):
                offset = update["update_id"] + 1
                if "message" in update and "text" in update["message"]:
                    text = update["message"]["text"]
                    if text in SYMBOLS:
                        # Phản hồi ngay lập tức để tránh cảm giác đơ
                        requests.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage", 
                                      json={"chat_id": CHAT_ID, "text": f"⏳ Đang soi kèo {text} cho bạn..."})
                        
                        data, ai_msg = await fetch_and_analyze(SYMBOLS[text], is_auto=False)
                        if data is not None:
                            msg = (f"🏛 *CHUYÊN GIA SOI KÈO: {text}*\n"
                                   f"━━━━━━━━━━━━━━━\n"
                                   f"💰 Giá: `{data['close']}` | RSI: `{round(data['RSI'],1)}`\n\n"
                                   f"👨‍🏫 *NHẬN ĐỊNH:* \n_{ai_msg}_\n"
                                   f"━━━━━━━━━━━━━━━")
                            requests.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage", 
                                          json={"chat_id": CHAT_ID, "text": msg, "parse_mode": "Markdown", "reply_markup": KEYBOARD})
                    elif text == "/start":
                        requests.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage", 
                                      json={"chat_id": CHAT_ID, "text": "Hệ thống Trading Pro đã Online!", "reply_markup": KEYBOARD})
        except:
            await asyncio.sleep(1)

@app.route('/')
def home(): return "Bot Online", 200

if __name__ == "__main__":
    Thread(target=lambda: app.run(host='0.0.0.0', port=10000)).start()
    # Chạy song song cả 2 luồng: Quét tự động và Trả lời nút bấm
    loop = asyncio.get_event_loop()
    loop.create_task(auto_scanner())
    loop.create_task(button_handler())
    loop.run_forever()
