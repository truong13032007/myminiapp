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
GEMINI_KEY = "AIzaSyBV0eYnFTBON0WS0QN7T-4ZXjYYwArmyR4" # Đã dán Key của bạn

# Cấu hình AI Gemini
genai.configure(api_key=GEMINI_KEY)
ai_model = genai.GenerativeModel('gemini-1.5-flash')

SYMBOLS = {
    "BTC ₿": "BTC/USDT", "ETH Ξ": "ETH/USDT",
    "SOL ☀️": "SOL/USDT", "VÀNG 🏆": "PAXG/USDT"
}

app = Flask(__name__)
KEYBOARD = {"keyboard": [[{"text": "BTC ₿"}, {"text": "ETH Ξ"}], [{"text": "SOL ☀️"}, {"text": "VÀNG 🏆"}]], "resize_keyboard": True}

# --- HÀM TÍNH TOÁN CHỈ BÁO ---
def get_indicators(closes):
    if len(closes) < 20: return 50, 0, 0
    # RSI 14
    diff = [closes[i] - closes[i-1] for i in range(1, len(closes))]
    gain = sum([d for d in diff[-14:] if d > 0]) / 14
    loss = sum([-d for d in diff[-14:] if d < 0]) / 14
    rsi = round(100 - (100 / (1 + (gain/abs(loss)))), 2) if loss != 0 else 100
    # Bollinger Bands
    sma20 = sum(closes[-20:]) / 20
    std_dev = (sum((x - sma20) ** 2 for x in closes[-20:]) / 20) ** 0.5
    upper, lower = sma20 + (std_dev * 2), sma20 - (std_dev * 2)
    return rsi, round(upper, 2), round(lower, 2)

# --- HÀM AI PHÂN TÍCH ---
async def ai_analyze(name, price, rsi, history):
    try:
        prompt = (f"Bạn là chuyên gia trade coin. {name} giá {price}, RSI {rsi}. "
                  f"Lịch sử nến gần đây: {history}. "
                  f"Phân tích ngắn gọn 2 dòng: "
                  f"1. Xu hướng và lý do. 2. Kèo (Long/Short/Chờ) + Entry/TP/SL. "
                  f"Trả lời tiếng Việt, súc tích.")
        # Chạy AI trong thread riêng để bot không bị treo
        response = await asyncio.to_thread(ai_model.generate_content, prompt)
        return response.text.strip()
    except Exception as e:
        return "AI đang bận soi nến, hãy xem chỉ số kỹ thuật bên trên."

async def get_full_report(name, sym):
    ex = ccxt.okx({'timeout': 7000})
    try:
        ohlcv = await ex.fetch_ohlcv(sym, timeframe='1h', limit=50)
        closes = [x[4] for x in ohlcv]
        curr = closes[-1]
        rsi, upper, lower = get_indicators(closes)
        
        # AI nhận định
        history = ", ".join(map(str, closes[-10:]))
        ai_remark = await ai_analyze(name, curr, rsi, history)
        
        # Tín hiệu code gắt (RSI < 30 hoặc > 70 mới báo)
        signal = ""
        if rsi <= 30 and curr <= lower: signal = "🟢 TÍN HIỆU: LONG (MUA)"
        elif rsi >= 70 and curr >= upper: signal = "🔴 TÍN HIỆU: SHORT (BÁN)"

        msg = (f"🤖 *AI SOI KÈO: {name}*\n"
               f"━━━━━━━━━━━━━━━\n"
               f"💰 Giá: `{curr}` | RSI: `{rsi}`\n"
               f"💠 BB: `{lower}` - `{upper}`\n"
               f"━━━━━━━━━━━━━━━\n"
               f"📝 *AI NHẬN ĐỊNH:*\n_{ai_remark}_\n"
               f"━━━━━━━━━━━━━━━")
        if signal: msg += f"\n🔥 **{signal}**\n📍 **ENTRY: {curr}**"
        return msg, curr, (True if signal else False)
    except: return None, None, False
    finally: await ex.close()

# --- LUỒNG CHÍNH ---
async def main_worker():
    offset = 0
    last_scan = 0
    last_alerts = {s: 0 for s in SYMBOLS}
    while True:
        try:
            # 1. Xử lý nút bấm
            url = f"https://api.telegram.org/bot{TOKEN}/getUpdates?offset={offset}&timeout=5"
            res = requests.get(url, timeout=10).json()
            for update in res.get("result", []):
                offset = update["update_id"] + 1
                if "message" in update and "text" in update["message"]:
                    cmd = update["message"]["text"]
                    if cmd in SYMBOLS:
                        msg, _, _ = await get_full_report(cmd, SYMBOLS[cmd])
                        if msg: requests.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage", 
                            json={"chat_id": CHAT_ID, "text": msg, "parse_mode": "Markdown", "reply_markup": KEYBOARD})
                    elif cmd == "/start":
                        requests.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage", 
                            json={"chat_id": CHAT_ID, "text": "Hệ thống AI Expert đã dán Key. Sẵn sàng!", "reply_markup": KEYBOARD})

            # 2. Quét tự động mỗi 10 phút
            if time.time() - last_scan > 600:
                for name, sym in SYMBOLS.items():
                    msg, curr, has_sig = await get_full_report(name, sym)
                    if has_sig and last_alerts[name] != curr:
                        requests.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage", 
                            json={"chat_id": CHAT_ID, "text": "🚨 *AI PHÁT HIỆN KÈO THƠM*\n" + msg, "parse_mode": "Markdown"})
                        last_alerts[name] = curr
                last_scan = time.time()
        except: await asyncio.sleep(2)
        await asyncio.sleep(0.5)

@app.route('/')
def home(): return "AI Expert Running with Key", 200

if __name__ == "__main__":
    Thread(target=lambda: app.run(host='0.0.0.0', port=10000)).start()
    asyncio.run(main_worker())
