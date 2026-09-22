import streamlit as st
import pandas as pd
import ta
import ccxt
from concurrent.futures import ThreadPoolExecutor, as_completed

st.set_page_config(page_title="Advanced Crypto EMA Scanner", layout="wide")
st.title("⚡ Advanced Crypto EMA Crossover Scanner")
st.write("Coins with **Price < EMA 200** & **EMA 14 crossed EMA 50 within last 5 candles**")

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

        current_price = df.iloc[-1]['close']
        ema200 = df.iloc[-1]['EMA200']

        # Rule 1: Price strictly below EMA 200
        if current_price < ema200:
            status = None
            crossed_candle_ago = None

            # Rule 2: Check Crossover in last 5 candles
            for i in range(1, 6):
                prev = df.iloc[-(i + 2)]
                curr = df.iloc[-(i + 1)]

                if (prev['EMA14'] <= prev['EMA50']) and (curr['EMA14'] > curr['EMA50']):
                    crossed_candle_ago = i
                    status = f"🚀 Bullish Cross ({i} candle{'s' if i > 1 else ''} ago)"
                    break

            # Near Crossover Check
            if not status:
                row_0 = df.iloc[-1]
                diff_percent = abs(row_0['EMA14'] - row_0['EMA50']) / row_0['EMA50'] * 100
                if (row_0['EMA14'] < row_0['EMA50']) and (diff_percent <= 0.2):
                    status = "👀 About to Cross (Near)"
                    crossed_candle_ago = 0

            if status:
                return {
                    "Exchange": exchange_id.upper(),
                    "Symbol": symbol,
                    "Status": status,
                    "Candles Ago": crossed_candle_ago if crossed_candle_ago is not None else 99,
                    "Price": current_price,
                    "EMA14": round(df.iloc[-1]['EMA14'], 4),
                    "EMA50": round(df.iloc[-1]['EMA50'], 4),
                    "EMA200": round(ema200, 4)
                }
    except Exception:
        pass
    return None

if st.button("🚀 Fast Scan Now"):
    st.info(f"Fetching Top {coin_limit} USDT Pairs from {exchange_choice.upper()}...")
    symbols = fetch_exchange_pairs(exchange_choice, coin_limit)
    
    if symbols:
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

        # --- SUMMARY METRICS ---
        st.write("---")
        m1, m2, m3 = st.columns(3)
        m1.metric(label="Total Scanned", value=f"{len(symbols)} Coins")
        m2.metric(label="Matches Found", value=f"{len(results)} Coins", delta=f"{len(results)} Opportunities" if results else "0")
        
        fresh_crosses = len([r for r in results if r['Candles Ago'] <= 2])
        m3.metric(label="Fresh Crosses (1-2 Candles)", value=f"{fresh_crosses}")
        st.write("---")

        if results:
            # Sort results by recent crossover
            sorted_results = sorted(results, key=lambda x: x['Candles Ago'])
            
            st.subheader("🎯 Matched Opportunities Cards")
            
            # Grid Layout: Displaying 3 Coin Cards per Row
            cols_per_row = 3
            for i in range(0, len(sorted_results), cols_per_row):
                cols = st.columns(cols_per_row)
                for j in range(cols_per_row):
                    if i + j < len(sorted_results):
                        coin = sorted_results[i + j]
                        with cols[j]:
                            with st.container(border=True):
                                st.markdown(f"### 🪙 {coin['Symbol']}")
                                st.caption(f"Exchange: **{coin['Exchange']}** | Timeframe: **{timeframe}**")
                                st.success(f"{coin['Status']}")
                                
                                # Details inside the card
                                c1, c2 = st.columns(2)
                                c1.metric("Current Price", f"${coin['Price']}")
                                c2.metric("EMA 200", f"${coin['EMA200']}")
                                
                                st.write("---")
                                sub_c1, sub_c2 = st.columns(2)
                                sub_c1.write(f"**EMA 14:** `{coin['EMA14']}`")
                                sub_c2.write(f"**EMA 50:** `{coin['EMA50']}`")
        else:
            st.warning("No coins matched the condition within last 5 candles.")
