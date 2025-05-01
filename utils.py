import streamlit as st
import yfinance as yf

@st.cache_data(ttl=300)

def get_current_price(ticker):
    # Add a more prominent start message
    print(f"--- Attempting get_current_price for {ticker} ---")
    try:
        ticker_data = yf.Ticker(ticker)
        info = ticker_data.info
        # Optional: Print the whole info dict for debugging? Can be large.
        # print(f"Info dict for {ticker}: {info}")
        if 'currentPrice' in info:
            price = info['currentPrice']
            if price is not None:
                print(f"+++ Successfully fetched price for {ticker}: {price}") # Success log
                return price
            else:
                # Handles case where key exists but value is None
                print(f"!!! Price value for {ticker} is None in info dict.") # Specific log
                return None
        else:
            # Handles case where key 'currentPrice' is missing entirely
            print(f"!!! Key 'currentPrice' not found in info dict for {ticker}.") # Specific log
            return None
    except Exception as e:
        # This is the block you are NOT seeing, but keep it
        print(f"!!! EXCEPTION fetching price for {ticker}: {e}")
        return None