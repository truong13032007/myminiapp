import asyncio
import requests
import ccxt.async_support as ccxt
import pandas as pd
import numpy as np
from flask import Flask
from threading import Thread
import time

# --- CẤU HÌNH ---
TOKEN = "8732938098:AAGrT0VC6B1mCMKPzdthChMUfGr2dv8tuZ0"
CHAT_ID = "6317501489"
SYMBOLS = {
    "BTC ₿": "BTC/USDT", "ETH Ξ": "ETH/USDT",
    "SOL ☀️": "SOL/USDT", "VÀNG 🏆": "PAXG/USDT"
}

app = Flask(__name__)
KEYBOARD = {"keyboard": [[{"text": "BTC ₿"}, {"text": "ETH Ξ"}], [{"text": "SOL ☀️"}, {"text": "VÀNG 🏆"}]], "resize_keyboard": True}

# --- HÀM TÍNH TOÁN LOGIC TRADING ---
def calculate_complex_logic(df):
    # 1. RSI
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    df['rsi'] = 100 - (100 / (1 + (gain / loss.abs())))
    
    # 2. EMA 50 & 200
    df['ema50'] = df['close'].ewm(span=50, adjust=False).mean()
    df['ema200'] = df['close'].ewm(span=200, adjust=False).mean()
    
    # 3. Bollinger Bands
    df['ma20'] = df['close'].rolling(window=20).mean()
    df['std'] = df['close'].rolling(window=20).std()
    df['upper'] = df['ma20'] + (df['std'] * 2)
    df['lower'] = df['ma20'] - (df['std'] * 2)
    
    # 4. ATR (Độ biến động để đặt SL/TP)
    high_low = df['high'] - df['low']
    high_close = (df['high'] - df['close'].shift()).abs()
    low_close = (df['low'] - df['close'].shift()).abs()
    ranges = pd.concat([high_low, high_close, low_close], axis=1)
    df['atr'] = ranges.max(axis=1).rolling(window=14).mean()
    
    # 5. Phân tích nến & Volume
    last = df.iloc[-1]
    prev = df.iloc[-2]
    
    verdict = "CHỜ TÍN HIỆU"
    strength = 0 # Thang điểm 0-100
    
    # --- LOGIC VÀO LỆNH LONG ---
    # Điều kiện: RSI thấp + Thủng BB Lower + Nằm trên EMA200 + Volume giảm dần (cạn bán)
    if last['rsi'] < 35 and last['close'] < last['lower']:
        strength = 50
        if last['close'] > last['ema200']: strength += 30 # Thuận xu hướng lớn
        if last['vol'] < df['vol'].tail(5).mean(): strength += 20 # Cạn lực xả
        verdict = "LONG (MUA)" if strength >= 70 else "THEO DÕI LONG"

    # --- LOGIC VÀO LỆNH SHORT ---
    elif last['rsi'] > 65 and last['close'] > last['upper']:
        strength = 50
        if last['close'] < last['ema200']: strength += 30 # Thuận xu hướng giảm
        if last['vol'] > df['vol'].tail(5).mean(): strength += 20 # Có lực xả mạnh
        verdict = "SHORT (BÁN)" if strength >= 70 else "THEO DÕI SHORT"

    return {
        "price": round(last['close'], 2),
        "rsi": round(last['rsi'], 1),
        "ema_status": "BULLISH" if last['ema50'] > last['ema200'] else "BEARISH",
        "verdict": verdict,
        "strength": strength,
        "tp": round(last['close'] + (last['atr'] * 2) if "LONG" in verdict else last['close'] - (last['atr'] * 2), 2),
        "sl": round(last['close'] - (last['atr'] * 1.5) if "LONG" in verdict else last['close'] + (last['atr'] * 1.5), 2)
    }

async def process_market(name, sym, is_auto=False):
    ex = ccxt.okx({'timeout': 5000})
    try:
        bars = await ex.fetch_ohlcv(sym, timeframe='1h', limit=250)
        df = pd.DataFrame(bars, columns=['ts', 'open', 'high', 'low', 'close', 'vol'])
        res = calculate_complex_logic(df)

        if is_auto and res['strength'] < 80: return # Chỉ báo tự động kèo cực ngon

        msg = (f"🛡 *PHẦN MỀM TRADING PRO: {name}*\n"
               f"━━━━━━━━━━━━━━━\n"
               f"💰 Giá: `{res['price']}` | RSI: `{res['rsi']}`\n"
               f"📈 Xu hướng: *{res['ema_status']}*\n"
               f"📊 Độ tin cậy: `{res['strength']}%`\n"
               f"━━━━━━━━━━━━━━━\n"
               f"📢 **LỆNH: {res['verdict']}**\n"
               f"🎯 TP (Mục tiêu): `{res['tp']}`\n"
               f"🛑 SL (Cắt lỗ): `{res['sl']}`\n"
               f"💡 *Lời khuyên: {'Quản lý vốn 2%' if res['strength'] > 70 else 'Đứng ngoài quan sát'}*")
        
        requests.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage", 
                      json={"chat_id": CHAT_ID, "text": msg, "parse_mode": "Markdown", "reply_markup": KEYBOARD})
    except: pass
    finally: await ex.close()

# --- VÒNG LẶP CHỐNG ĐƠ ---
async def main_loop():
    offset = 0
    last_scan = 0
    while True:
        try:
            url = f"https://api.telegram.org/bot{TOKEN}/getUpdates?offset={offset}&timeout=5"
            res = requests.get(url, timeout=10).json()
            for update in res.get("result", []):
                offset = update["update_id"] + 1
                if "message" in update and "text" in update["message"]:
                    cmd = update["message"]["text"]
                    if cmd in SYMBOLS:
                        await process_market(cmd, SYMBOLS[cmd])
                    elif cmd == "/start":
                        requests.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage", 
                            json={"chat_id": CHAT_ID, "text": "Hệ thống Trading Đa Tầng đã sẵn sàng!", "reply_markup": KEYBOARD})
            
            if time.time() - last_scan > 600: # 10 phút quét 1 lần
                for name, sym in SYMBOLS.items():
                    await process_market(name, sym, is_auto=True)
                last_scan = time.time()
        except: await asyncio.sleep(5)
        await asyncio.sleep(0.5)

@app.route('/')
def home(): return "Pro Logic Active", 200

if __name__ == "__main__":
    Thread(target=lambda: app.run(host='0.0.0.0', port=10000)).start()
    asyncio.run(main_loop())
