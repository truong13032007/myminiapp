import asyncio
import requests
import ccxt.async_support as ccxt
import google.generativeai as genai
from flask import Flask
from threading import Thread
import time

# --- CẤU HÌNH ---
TOKEN = "8732938098:AAGrT0VC6B1mCMKPzdthChMUfGr2dv8tuZ0"
CHAT_ID = "6317501489"
GEMINI_KEY = "DÁN_KEY_GEMINI_CỦA_BẠN_VÀO_ĐÂY" 

# Cấu hình Gemini
genai.configure(api_key=GEMINI_KEY)
ai_model = genai.GenerativeModel('gemini-1.5-flash')

SYMBOLS = {
    "BTC ₿": "BTC/USDT", "ETH Ξ": "ETH/USDT",
    "SOL ☀️": "SOL/USDT", "VÀNG 🏆": "PAXG/USDT"
}

app = Flask(__name__)
KEYBOARD = {"keyboard": [[{"text": "BTC ₿"}, {"text": "ETH Ξ"}], [{"text": "SOL ☀️"}, {"text": "VÀNG 🏆"}]], "resize_keyboard": True}

# --- HÀM PHÂN TÍCH ---
def calculate_indicators(closes):
    if len(closes) < 15: return 50
    diff = [closes[i] - closes[i-1] for i in range(1, len(closes))]
    gain = sum([d for d in diff[-14:] if d > 0]) / 14
    loss = sum([-d for d in diff[-14:] if d < 0]) / 14
    rsi = round(100 - (100 / (1 + (gain/abs(loss)))), 2) if loss != 0 else 100
    return rsi

async def get_ai_analysis(name, price, rsi):
    try:
        prompt = f"Giá {name} hiện tại {price}, RSI {rsi}. Phân tích xu hướng cực ngắn gọn trong 1 câu tiếng Việt."
        response = await asyncio.to_thread(ai_model.generate_content, prompt)
        return response.text.strip()
    except:
        return "AI đang bận, hãy dựa vào chỉ số RSI."

async def get_signal_message(name, sym):
    ex = ccxt.okx({'timeout': 10000}) 
    try:
        ohlcv = await ex.fetch_ohlcv(sym, timeframe='1h', limit=50)
        closes = [x[4] for x in ohlcv]
        curr = closes[-1]
        rsi = calculate_indicators(closes)
        
        # Nhận định AI
        ai_remark = await get_ai_analysis(name, curr, rsi)
        
        # Xác định xu hướng
        trend = "ĐI NGANG"
        if rsi > 55: trend = "TĂNG"
        elif rsi < 45: trend = "GIẢM"
        
        signal_line = ""
        if rsi <= 32:
            signal_line = f"\n🚨 **TÍN HIỆU: LONG**\n📍 **ENTRY: {curr}**"
        elif rsi >= 68:
            signal_line = f"\n🚨 **TÍN HIỆU: SHORT**\n📍 **ENTRY: {curr}**"
        
        msg = (f"📊 *{name}*\n"
               f"━━━━━━━━━━━━━━━\n"
               f"💰 Giá: `{curr}`\n"
               f"📈 RSI: `{rsi}`\n"
               f"🔍 Xu hướng: *{trend}*\n"
               f"🤖 AI: _{ai_remark}_\n"
               f"━━━━━━━━━━━━━━━"
               f"{signal_line}")
            
        return msg, curr, (True if signal_line else False)
    except Exception as e:
        print(f"Lỗi fetch: {e}")
        return None, None, False
    finally:
        await ex.close()

# --- LUỒNG XỬ LÝ CHÍNH ---
async def main_worker():
    offset = 0
    last_alerts = {s: 0 for s in SYMBOLS}
    last_scan_time = 0

    while True:
        try:
            # 1. Xử lý nút bấm (Ưu tiên cao)
            url = f"https://api.telegram.org/bot{TOKEN}/getUpdates?offset={offset}&timeout=5"
            res = requests.get(url, timeout=10).json()
            
            for update in res.get("result", []):
                offset = update["update_id"] + 1
                if "message" in update and "text" in update["message"]:
                    text = update["message"]["text"]
                    if text in SYMBOLS:
                        msg, _, _ = await get_signal_message(text, SYMBOLS[text])
                        if msg:
                            requests.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage", 
                                          json={"chat_id": CHAT_ID, "text": msg, "parse_mode": "Markdown", "reply_markup": KEYBOARD})
                    elif text == "/start":
                        requests.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage", 
                                      json={"chat_id": CHAT_ID, "text": "Hệ thống AI Trading Online!", "reply_markup": KEYBOARD})

            # 2. Tự động quét kèo (Mỗi 5 phút một lần để tránh đơ luồng)
            current_time = time.time()
            if current_time - last_scan_time > 300:
                for name, sym in SYMBOLS.items():
                    msg, curr, has_signal = await get_signal_message(name, sym)
                    if has_signal and last_alerts[name] != curr:
                        requests.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage", 
                                      json={"chat_id": CHAT_ID, "text": "🔔 *QUÉT TỰ ĐỘNG*\n" + msg, "parse_mode": "Markdown"})
                        last_alerts[name] = curr
                last_scan_time = current_time

        except Exception as e:
            print(f"Lỗi hệ thống: {e}")
            await asyncio.sleep(5) # Đợi 5s nếu lỗi mạng rồi tự chạy lại
        
        await asyncio.sleep(0.5)

@app.route('/')
def home(): return "Bot is Running", 200

if __name__ == "__main__":
    # Chạy Web Server trong luồng riêng
    Thread(target=lambda: app.run(host='0.0.0.0', port=10000)).start()
    # Chạy vòng lặp bot chính
    asyncio.run(main_worker())
