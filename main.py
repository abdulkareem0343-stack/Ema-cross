import streamlit as st
import requests
import pandas as pd
import ta

st.set_page_config(page_title="Crypto EMA Crossover Scanner", layout="wide")
st.title("📈 Crypto EMA Crossover Scanner")
st.write("Coins with Price < EMA 200 & EMA 14 crossing above EMA 50")

timeframe = st.selectbox("Select Timeframe:", ["15m", "1h", "4h", "1d"], index=1)

def get_top_usdt_pairs():
    url = "https://api.binance.com/api/v3/ticker/24hr"
    try:
        data = requests.get(url).json()
        usdt_pairs = [d['symbol'] for d in data if d['symbol'].endswith('USDT') and 'UP' not in d['symbol'] and 'DOWN' not in d['symbol']]
        sorted_pairs = sorted(data, key=lambda x: float(x['quoteVolume']), reverse=True)
        return [d['symbol'] for d in sorted_pairs if d['symbol'] in usdt_pairs][:100]
    except Exception as e:
        st.error(f"Error fetching pairs: {e}")
        return []

def check_crossover(symbol, tf):
    url = f"https://api.binance.com/api/v3/klines?symbol={symbol}&interval={tf}&limit=250"
    data = requests.get(url).json()
    
    if not data or len(data) < 200:
        return None

    df = pd.DataFrame(data, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume', 'close_time', 'qav', 'num_trades', 'taker_base_vol', 'taker_quote_vol', 'ignore'])
    df['close'] = df['close'].astype(float)

    # Indicator Calculations using `ta` library
    df['EMA14'] = ta.trend.ema_indicator(df['close'], window=14)
    df['EMA50'] = ta.trend.ema_indicator(df['close'], window=50)
    df['EMA200'] = ta.trend.ema_indicator(df['close'], window=200)

    prev_row = df.iloc[-3]
    curr_row = df.iloc[-2]

    current_price = curr_row['close']
    ema200 = curr_row['EMA200']

    # Conditions
    if current_price < ema200:
        prev_cross = prev_row['EMA14'] <= prev_row['EMA50']
        curr_cross = curr_row['EMA14'] > curr_row['EMA50']

        if prev_cross and curr_cross:
            return {
                "Symbol": symbol,
                "Price": current_price,
                "EMA14": round(curr_row['EMA14'], 4),
                "EMA50": round(curr_row['EMA50'], 4),
                "EMA200": round(ema200, 4)
            }
    return None

if st.button("Scan Market Now"):
    st.info("Scanning Top 100 Binance Pairs...")
    symbols = get_top_usdt_pairs()
    results = []
    
    progress_bar = st.progress(0)
    for idx, symbol in enumerate(symbols):
        res = check_crossover(symbol, timeframe)
        if res:
            results.append(res)
        progress_bar.progress((idx + 1) / len(symbols))

    if results:
        st.success(f"Found {len(results)} matching coins!")
        st.dataframe(pd.DataFrame(results))
    else:
        st.warning("No coins matched the condition right now.")
