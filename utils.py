import streamlit as st
import yfinance as yf

@st.cache_data(ttl=300)

def get_current_price(ticker):
    print(f"Fetching live price for {ticker}...")
    try:
        ticker_data = yf.Ticker(ticker)
        info = ticker_data.info
        if 'currentPrice' in info:
            return info['currentPrice']
        else:
            return None
    except Exception as e:
        print(f"Error fetching price for {ticker}: {e}")
        return None