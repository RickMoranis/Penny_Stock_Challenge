# utils.py
import yfinance as yf
import streamlit as st
import pandas as pd

@st.cache_data
def get_current_price(tickers):
    """
    Fetches the last known price for a list of tickers.
    This version is more robust against API failures.
    """
    if not isinstance(tickers, list) or not tickers:
        return {}

    prices = {}
    try:
        # Use yf.download for a short period to get the most recent closing price.
        # This is often more reliable than fetching 'info' for multiple tickers.
        data = yf.download(tickers, period="5d", progress=False, group_by='ticker')
        
        if data.empty:
            st.warning(f"Could not retrieve any price data for tickers: {', '.join(tickers)}")
            return {}

        for ticker in tickers:
            try:
                # For multiple tickers, yf.download creates a multi-level column index.
                # We need to access the 'Close' price for the specific ticker.
                # The .iloc[-1] gets the last available (most recent) price.
                last_price = data[ticker]['Close'].dropna().iloc[-1]
                if pd.notna(last_price):
                    prices[ticker] = last_price
                else:
                    prices[ticker] = None
            except (KeyError, IndexError):
                # Fallback for single tickers or if a column is missing
                try:
                    single_ticker_data = yf.Ticker(ticker).history(period="1d")
                    if not single_ticker_data.empty:
                        prices[ticker] = single_ticker_data['Close'].iloc[-1]
                    else:
                        prices[ticker] = None
                except Exception:
                    prices[ticker] = None
        
        # Log which tickers failed to fetch a price
        failed_tickers = [t for t, p in prices.items() if p is None]
        if failed_tickers:
            st.warning(f"Could not fetch a current price for: {', '.join(failed_tickers)}")
            
        return prices

    except Exception as e:
        st.error(f"An error occurred while fetching prices: {e}")
        return {ticker: None for ticker in tickers} # Return dict with Nones on major failure

