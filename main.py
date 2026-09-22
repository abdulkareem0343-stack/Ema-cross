import streamlit as st
import pandas as pd
import ta
import ccxt
from concurrent.futures import ThreadPoolExecutor, as_completed

st.set_page_config(page_title="Fast Crypto EMA Scanner", layout="wide")
st.title("⚡ Fast Crypto EMA Crossover Scanner")
st.write("Coins with **Price < EMA 200** & **EMA 14 crossing/near EMA 50**")

col1, col2, col3 = st.columns(3)
with col1:
    exchange_choice = st.selectbox("Select Exchange:", ["kucoin", "binance"])
with col2:
    timeframe = st.selectbox("Select Timeframe:", ["15m", "1h", "4h", "1d"], index=0)
with col3:
    coin_limit = st.number_input("Limit Coins:", min_value=10, max_value=1000, value=500, step=50)

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

        # Check last few candles
        row_0 = df.iloc[-1] # Current Live
        row_1 = df.iloc[-2] # Last Closed
        row_2 = df.iloc[-3] # 2nd Last
        row_3 = df.iloc[-4] # 3rd Last

        current_price = row_0['close']
        ema200 = row_0['EMA200']

        # Rule 1: Price must be strictly BELOW EMA 200
        if current_price < ema200:
            
            # Check 1: Fresh Crossover in last 3 candles
            cross_1 = (row_2['EMA14'] <= row_2['EMA50']) and (row_1['EMA14'] > row_1['EMA50'])
            cross_2 = (row_3['EMA14'] <= row_3['EMA50']) and (row_2['EMA14'] > row_2['EMA50'])
            
            # Check 2: Near Crossover (EMA 14 is just below EMA 50, distance < 0.2%)
            diff_percent = abs(row_0['EMA14'] - row_0['EMA50']) / row_0['EMA50'] * 100
            is_near = (row_0['EMA14'] < row_0['EMA50']) and (diff_percent <= 0.2)

            status = ""
            if cross_1:
                status = "🚀 Bullish Cross (1 candle ago)"
            elif cross_2:
                status = "🚀 Bullish Cross (2 candles ago)"
            elif is_near:
                status = "👀 About to Cross (Near)"

            if status != "":
                return {
                    "Exchange": exchange_id.upper(),
                    "Symbol": symbol,
                    "Status": status,
                    "Price": current_price,
                    "EMA 14": round(row_0['EMA14'], 4),
                    "EMA 50": round(row_0['EMA50'], 4),
                    "EMA 200": round(ema200, 4)
                }
    except Exception:
        pass
    return None

if st.button("🚀 Fast Scan Now"):
    st.info(f"Fetching Top {coin_limit} USDT Pairs from {exchange_choice.upper()}...")
    symbols = fetch_exchange_pairs(exchange_choice, coin_limit)
    
    if symbols:
        st.write(f"Scanning {len(symbols)} coins...")
        results = []
        
        progress_bar = st.progress(0)
        completed_count = 0
        total_coins = len(symbols)

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
            st.warning("No coins matched right now. Try switching the Timeframe (e.g., 1h or 4h).")
