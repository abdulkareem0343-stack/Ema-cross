import os
import time
import requests
import pandas as pd
import pandas_ta as ta

# GitHub Secrets se Environment Variables le raha hai
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
TIMEFRAME = "1h"  # Timeframe: 15m, 1h, 4h

def send_telegram_alert(message):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("Error: Telegram credentials missing!")
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "Markdown"}
    try:
        requests.post(url, json=payload)
    except Exception as e:
        print(f"Error sending alert: {e}")

def get_top_usdt_pairs():
    url = "https://api.binance.com/api/v3/ticker/24hr"
    try:
        data = requests.get(url).json()
        usdt_pairs = [d['symbol'] for d in data if d['symbol'].endswith('USDT') and 'UP' not in d['symbol'] and 'DOWN' not in d['symbol']]
        sorted_pairs = sorted(data, key=lambda x: float(x['quoteVolume']), reverse=True)
        top_pairs = [d['symbol'] for d in sorted_pairs if d['symbol'] in usdt_pairs][:100]
        return top_pairs
    except Exception as e:
        print(f"Error fetching pairs: {e}")
        return []

def check_crossover(symbol):
    url = f"https://api.binance.com/api/v3/klines?symbol={symbol}&interval={TIMEFRAME}&limit=250"
    data = requests.get(url).json()
    
    if not data or len(data) < 200:
        return

    df = pd.DataFrame(data, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume', 'close_time', 'qav', 'num_trades', 'taker_base_vol', 'taker_quote_vol', 'ignore'])
    df['close'] = df['close'].astype(float)

    # Indicator Calculations
    df['EMA14'] = ta.ema(df['close'], length=14)
    df['EMA50'] = ta.ema(df['close'], length=50)
    df['EMA200'] = ta.ema(df['close'], length=200)

    # Last complete candle
    prev_row = df.iloc[-3]
    curr_row = df.iloc[-2]

    current_price = curr_row['close']
    ema200 = curr_row['EMA200']

    # Conditions: Price < EMA 200 AND EMA 14 crosses above EMA 50
    if current_price < ema200:
        prev_cross = prev_row['EMA14'] <= prev_row['EMA50']
        curr_cross = curr_row['EMA14'] > curr_row['EMA50']

        if prev_cross and curr_cross:
            msg = (f"🚀 *EMA CROSSOVER ALERT* 🚀\n\n"
                   f"• *Coin:* #{symbol}\n"
                   f"• *Price:* {current_price}\n"
                   f"• *EMA 200:* {round(ema200, 4)}\n"
                   f"• *Condition:* Price is BELOW EMA200 & EMA14 crossed ABOVE EMA50\n"
                   f"• *Timeframe:* {TIMEFRAME}")
            print(f"[MATCH FOUND] {symbol}")
            send_telegram_alert(msg)

def run_scanner():
    print("Market Scanning Started...")
    symbols = get_top_usdt_pairs()
    for symbol in symbols:
        try:
            check_crossover(symbol)
            time.sleep(0.1)
        except Exception:
            continue
    print("Scan Completed.")

if __name__ == "__main__":
    run_scanner()
