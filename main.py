import streamlit as st
import pandas as pd
import ta
import ccxt
from concurrent.futures import ThreadPoolExecutor, as_completed

st.set_page_config(page_title="Ultra-Fast EMA Scanner", layout="wide")
st.title("⚡ Ultra-Fast Crypto EMA Crossover Scanner")
st.write("Coins with **Price < EMA 200** & **EMA 14 crossed EMA 50 within last 5 candles**")

col1, col2, col3 = st.columns(3)
with col1:
    # MEXC & Bybit are recommended for 100% working & no restriction errors
    exchange_choice = st.selectbox("Select Exchange:", ["mexc", "bybit", "kucoin", "binance"], index=0)
with col2:
    timeframe = st.selectbox("Select Timeframe:", ["15m", "1h", "4h", "1d"], index=0)
with col3:
    coin_limit = st.number_input("Limit Coins:", min_value=10, max_value=1000, value=500, step=50)

def get_exchange_instance(exchange_id):
    if exchange_id == 'binance':
        return ccxt.binance({
            'enableRateLimit': False,
            'timeout': 5000,
            'urls': {
                'api': {
                    'public': 'https://data-api.binance.vision/api/v3'
                }
            }
        })
    elif exchange_id == 'mexc':
        return ccxt.mexc({'enableRateLimit': False, 'timeout': 5000})
    elif exchange_id == 'bybit':
        return ccxt.bybit({'enableRateLimit': False, 'timeout': 5000})
    else:
        return ccxt.kucoin({'enableRateLimit': False, 'timeout': 5000})

@st.cache_data(ttl=300)
def fetch_exchange_pairs(exchange_id, limit):
    try:
        exchange = get_exchange_instance(exchange_id)
        tickers = exchange.fetch_tickers()
        
        usdt_pairs = []
        for symbol, ticker in tickers.items():
            if symbol.endswith('/USDT') and 'UP/' not in symbol and 'DOWN/' not in symbol and 'BEAR/' not in symbol and 'BULL/' not in symbol:
                vol = ticker.get('quoteVolume') or ticker.get('baseVolume') or 0
                usdt_pairs.append({'symbol': symbol, 'volume': vol})
        
        sorted_pairs = sorted(usdt_pairs, key=lambda x: x['volume'], reverse=True)
        return [item['symbol'] for item in sorted_pairs[:limit]]
    except Exception as e:
        st.error(f"Error fetching pairs from {exchange_id.upper()}: {e}")
        return []

def process_single_coin(exchange_id, symbol, tf):
    try:
        exchange = get_exchange_instance(exchange_id)
        ohlcv = exchange.fetch_ohlcv(symbol, timeframe=tf, limit=100)
        
        if not ohlcv or len(ohlcv) < 60:
            return None

        df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df['close'] = df['close'].astype(float)

        df['EMA14'] = ta.trend.ema_indicator(df['close'], window=14)
        df['EMA50'] = ta.trend.ema_indicator(df['close'], window=50)
        df['EMA200'] = ta.trend.ema_indicator(df['close'], window=200)

        current_price = df.iloc[-1]['close']
        ema200 = df.iloc[-1]['EMA200']

        if current_price >= ema200:
            return None

        status = None
        crossed_candle_ago = None

        for i in range(1, 6):
            prev = df.iloc[-(i + 2)]
            curr = df.iloc[-(i + 1)]

            if (prev['EMA14'] <= prev['EMA50']) and (curr['EMA14'] > curr['EMA50']):
                crossed_candle_ago = i
                status = f"🚀 Bullish Cross ({i}c ago)"
                break

        if not status:
            row_0 = df.iloc[-1]
            diff_percent = abs(row_0['EMA14'] - row_0['EMA50']) / row_0['EMA50'] * 100
            if (row_0['EMA14'] < row_0['EMA50']) and (diff_percent <= 0.2):
                status = "👀 Near Cross"
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

        with ThreadPoolExecutor(max_workers=30) as executor:
            future_to_symbol = {
                executor.submit(process_single_coin, exchange_choice, symbol, timeframe): symbol 
                for symbol in symbols
            }
            
            for future in as_completed(future_to_symbol):
                res = future.result()
                if res:
                    results.append(res)
                
                completed_count += 1
                progress_bar.progress(completed_count / total_coins)

        st.write("---")
        m1, m2, m3 = st.columns(3)
        m1.metric("Scanned", f"{len(symbols)}")
        m2.metric("Matches", f"{len(results)}")
        fresh_crosses = len([r for r in results if r['Candles Ago'] <= 2])
        m3.metric("Fresh (1-2c)", f"{fresh_crosses}")
        st.write("---")

        if results:
            sorted_results = sorted(results, key=lambda x: x['Candles Ago'])
            st.subheader("🎯 Matched Opportunities")
            
            for coin in sorted_results:
                badge_color = "#10b981" if "Bullish" in coin['Status'] else "#f59e0b"
                
                card_html = f"""
                <div style="
                    border: 1px solid #334155; 
                    border-radius: 8px; 
                    padding: 8px 12px; 
                    margin-bottom: 6px; 
                    background-color: #1e293b;
                    color: white;">
                    <div style="display: flex; justify-content: space-between; align-items: center;">
                        <span style="font-size: 15px; font-weight: bold; color: #f8fafc;">🪙 {coin['Symbol']}</span>
                        <span style="background-color: {badge_color}; color: black; font-size: 10px; padding: 2px 6px; border-radius: 10px; font-weight: bold;">{coin['Status']}</span>
                    </div>
                    <div style="font-size: 11px; color: #94a3b8; margin-top: 1px;">
                        {coin['Exchange']} | {timeframe}
                    </div>
                    <div style="display: flex; justify-content: space-between; margin-top: 6px; font-size: 12px;">
                        <div><b>Price:</b> <span style="color: #38bdf8;">${coin['Price']}</span></div>
                        <div><b>EMA 200:</b> <span style="color: #f43f5e;">${coin['EMA200']}</span></div>
                    </div>
                    <div style="display: flex; justify-content: space-between; margin-top: 3px; font-size: 11px; color: #cbd5e1;">
                        <span>EMA 14: <b>{coin['EMA14']}</b></span>
                        <span>EMA 50: <b>{coin['EMA50']}</b></span>
                    </div>
                </div>
                """
                st.markdown(card_html, unsafe_allow_html=True)
        else:
            st.warning("No coins matched the condition right now.")
