import streamlit as st
import pandas as pd
import ta
import ccxt
from concurrent.futures import ThreadPoolExecutor, as_completed

st.set_page_config(page_title="Fast Crypto EMA Scanner", layout="wide")
st.title("⚡ Fast Crypto EMA Crossover Scanner")
st.write("Coins with **Price < EMA 200** & **EMA 14 crossing above EMA 50**")

col1, col2, col3 = st.columns(3)
with col1:
    exchange_choice = st.selectbox("Select Exchange:", ["binance", "kucoin"])
with col2:
    timeframe = st.selectbox("Select Timeframe:", ["15m", "1h", "4h", "1d"], index=1)
with col3:
    coin_limit = st.number_input("Limit Coins:", min_value=10, max_value=1000, value=1000, step=50)

@st.cache_data(ttl=300)
def fetch_exchange_pairs(exchange_id, limit):
    try:
        exchange_class = getattr(ccxt, exchange_id)()
        tickers = exchange_class.fetch_tickers()
        
        usdt_pairs = []
        for symbol, ticker in tickers.items():
            if symbol.endswith('/USDT') and 'UP/' not in symbol and 'DOWN/' not in symbol:
                vol = ticker.get('quoteVolume') or 0
                usdt_pairs.append({'symbol': symbol, 'volume': vol})
        
        sorted_pairs = sorted(usdt_pairs, key=lambda x: x['volume'], reverse=True)
        return [item['symbol'] for item in sorted_pairs[:limit]]
    except Exception as e:
        st.error(f"Error fetching pairs from {exchange_id.upper()}: {e}")
        return []

def check_crossover(exchange_id, symbol, tf):
    try:
        exchange_class = getattr(ccxt, exchange_id)()
        ohlcv = exchange_class.fetch_ohlcv(symbol, timeframe=tf, limit=250)
        
        if not ohlcv or len(ohlcv) < 200:
            return None

        df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df['close'] = df['close'].astype(float)

        df['EMA14'] = ta.trend.ema_indicator(df['close'], window=14)
        df['EMA50'] = ta.trend.ema_indicator(df['close'], window=50)
        df['EMA200'] = ta.trend.ema_indicator(df['close'], window=200)

        prev_row = df.iloc[-3]
        curr_row = df.iloc[-2]

        current_price = curr_row['close']
        ema200 = curr_row['EMA200']

        if current_price < ema200:
            prev_cross = prev_row['EMA14'] <= prev_row['EMA50']
            curr_cross = curr_row['EMA14'] > curr_row['EMA50']

            if prev_cross and curr_cross:
                return {
                    "Exchange": exchange_id.upper(),
                    "Symbol": symbol,
                    "Price": current_price,
                    "EMA 14": round(curr_row['EMA14'], 4),
                    "EMA 50": round(curr_row['EMA50'], 4),
                    "EMA 200": round(ema200, 4)
                }
    except Exception:
        pass
    return None

if st.button("🚀 Fast Scan Now"):
    st.info(f"Fetching Top {coin_limit} USDT Pairs from {exchange_choice.upper()}...")
    symbols = fetch_exchange_pairs(exchange_choice, coin_limit)
    
    if symbols:
        st.write(f"Scanning {len(symbols)} coins in parallel threads...")
        results = []
        
        progress_bar = st.progress(0)
        completed_count = 0
        total_coins = len(symbols)

        # Multithreading for ultra-fast scanning (20 parallel requests)
        with ThreadPoolExecutor(max_workers=20) as executor:
            future_to_symbol = {
                executor.submit(check_crossover, exchange_choice, symbol, timeframe): symbol 
                for symbol in symbols
            }
            
            for future in as_completed(future_to_symbol):
                res = future.result()
                if res:
                    results.append(res)
                
                completed_count += 1
                progress_bar.progress(completed_count / total_coins)

        if results:
            st.success(f"Found {len(results)} matching coins!")
            st.dataframe(pd.DataFrame(results), use_container_width=True)
        else:
            st.warning("No coins matched the condition right now.")
