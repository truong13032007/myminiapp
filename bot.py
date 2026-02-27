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

SYMBOLS = {
    "BTC ₿": "BTC/USDT", "ETH Ξ": "ETH/USDT",
    "SOL ☀️": "SOL/USDT", "VÀNG 🏆": "PAXG/USDT"
}

app = Flask(__name__)
KEYBOARD = {"keyboard": [[{"text": "BTC ₿"}, {"text": "ETH Ξ"}], [{"text": "SOL ☀️"}, {"text": "VÀNG 🏆"}]], "resize_keyboard": True}

# --- HÀM XỬ LÝ DỮ LIỆU KỸ THUẬT ---
def get_analysis_indicators(df):
    # Tính RSI
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    df['rsi'] = 100 - (100 / (1 + rs))
    
    # Tính Bollinger Bands
    df['sma20'] = df['close'].rolling(window=20).mean()
    df['std'] = df['close'].rolling(window=20).std()
    df['upper'] = df['sma20'] + (df['std'] * 2)
    df['lower'] = df['sma20'] - (df['std'] * 2)
    
    # Tính biến động nến (Volatility)
    df['body_size'] = abs(df['close'] - df['open'])
    df['avg_body'] = df['body_size'].rolling(window=10).mean()
    
    return df

async def fetch_full_data(sym):
    ex = ccxt.okx({'timeout': 10000})
    try:
        # Lấy dữ liệu 2 khung thời gian
        h1_data = await ex.fetch_ohlcv(sym, timeframe='1h', limit=50)
        m15_data = await ex.fetch_ohlcv(sym, timeframe='15m', limit=50)
        
        df_h1 = pd.DataFrame(h1_data, columns=['ts', 'open', 'high', 'low', 'close', 'vol'])
        df_m15 = pd.DataFrame(m15_data, columns=['ts', 'open', 'high', 'low', 'close', 'vol'])
        
        df_h1 = get_analysis_indicators(df_h1)
        df_m15 = get_analysis_indicators(df_m15)
        
        return df_h1.iloc[-1], df_m15.iloc[-1], df_h1['close'].tail(15).tolist()
    finally:
        await ex.close()

# --- SIÊU TRÍ TUỆ AI PHÂN TÍCH ---
async def ai_expert_review(name, h1, m15, history):
    try:
        # Phân tích nến cuối: Có phải nến xả mạnh (Marubozu) hay nến rút râu (Pinbar)
        is_dumping = h1['body_size'] > (h1['avg_body'] * 1.5) and h1['close'] < h1['open']
        
        prompt = f"""
        Bạn là một Quản lý Quỹ Hedge Fund chuyên đánh Scalping. 
        Dữ liệu {name}:
        - Khung 1H: Giá {h1['close']}, RSI {round(h1['rsi'], 1)}, BB {round(h1['lower'], 2)}-{round(h1['upper'], 2)}.
        - Khung 15m: RSI {round(m15['rsi'], 1)}.
        - Lịch sử 15 nến: {history}.
        - Trạng thái nến hiện tại: {'Xả mạnh (Rủi ro cao)' if is_dumping else 'Bình thường'}.

        YÊU CẦU PHÂN TÍCH:
        1. Xu hướng cấu trúc: (Ví dụ: Dow tăng, nhưng 15m đang điều chỉnh).
        2. Soi kèo: Nếu RSI thấp nhưng nến đang 'Xả mạnh' thân dài, tuyệt đối cảnh báo ĐỨNG NGOÀI. Chỉ MUA khi giá chạm BB Lower và có dấu hiệu chững lại.
        3. Phán đoán: Entry cụ thể, TP (Chốt lời), SL (Cắt lỗ bắt buộc).
        Trả lời bằng tiếng Việt, giọng chuyên gia, không lý thuyết suông.
        """
        response = await asyncio.to_thread(ai_model.generate_content, prompt)
        return response.text.strip()
    except:
        return "⚠️ Hệ thống AI đang quét cấu trúc thị trường, vui lòng đợi..."

async def get_report(name, sym):
    try:
        h1, m15, history = await fetch_full_data(sym)
        ai_msg = await ai_expert_review(name, h1, m15, history)
        
        # Tín hiệu lọc cực gắt
        signal = ""
        if h1['rsi'] <= 28 and h1['close'] <= h1['lower']:
            signal = "💎 CƠ HỘI LONG CHIẾN LƯỢC"
        elif h1['rsi'] >= 72 and h1['close'] >= h1['upper']:
            signal = "💀 CƠ HỘI SHORT CHIẾN LƯỢC"

        msg = (f"🚀 *HỆ THỐNG PHÂN TÍCH CHUYÊN SÂU: {name}*\n"
               f"━━━━━━━━━━━━━━━━━━\n"
               f"💰 Giá: `{h1['close']}` | RSI 1H: `{round(h1['rsi'],1)}`\n"
               f"⏱ RSI 15m: `{round(m15['rsi'],1)}`\n"
               f"📊 *PHÂN TÍCH TỪ AI:* \n{ai_msg}\n"
               f"━━━━━━━━━━━━━━━━━━")
        
        if signal:
            msg += f"\n🔥 **{signal}**\n📍 **Mức giá hiện tại: {h1['close']}**"
        return msg, h1['close'], (True if signal else False)
    except Exception as e:
        print(f"Error: {e}")
        return None, None, False

# --- QUẢN LÝ LUỒNG VÀ WEB SERVER ---
async def main_worker():
    offset = 0
    last_scan = 0
    last_alerts = {s: 0 for s in SYMBOLS}
    
    while True:
        try:
            # Check Telegram Update
            url = f"https://api.telegram.org/bot{TOKEN}/getUpdates?offset={offset}&timeout=10"
            res = requests.get(url, timeout=15).json()
            for update in res.get("result", []):
                offset = update["update_id"] + 1
                if "message" in update and "text" in update["message"]:
                    cmd = update["message"]["text"]
                    if cmd in SYMBOLS:
                        # Gửi tin nhắn "Đang phân tích" để user không tưởng bot đơ
                        requests.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage", 
                                      json={"chat_id": CHAT_ID, "text": f"🔄 AI đang soi kèo {cmd}, chờ xíu..."})
                        msg, _, _ = await get_report(cmd, SYMBOLS[cmd])
                        if msg:
                            requests.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage", 
                                          json={"chat_id": CHAT_ID, "text": msg, "parse_mode": "Markdown", "reply_markup": KEYBOARD})
                    elif cmd == "/start":
                        requests.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage", 
                                      json={"chat_id": CHAT_ID, "text": "Hệ thống Super AI Pro Online!", "reply_markup": KEYBOARD})

            # Tự động quét kèo mỗi 15 phút (Khung dài hơn để lọc nhiễu)
            if time.time() - last_scan > 900:
                for name, sym in SYMBOLS.items():
                    msg, curr, has_sig = await get_report(name, sym)
                    if has_sig and last_alerts[name] != curr:
                        requests.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage", 
                                      json={"chat_id": CHAT_ID, "text": "🚨 *PHÁT HIỆN KÈO CHUYÊN GIA*\n" + msg, "parse_mode": "Markdown"})
                        last_alerts[name] = curr
                last_scan = time.time()
        except:
            await asyncio.sleep(5)
        await asyncio.sleep(0.5)

@app.route('/')
def home(): return "Super AI Active", 200

if __name__ == "__main__":
    Thread(target=lambda: app.run(host='0.0.0.0', port=10000)).start()
    asyncio.run(main_worker())
