# utils.py
import yfinance as yf
import streamlit as st
import pandas as pd

@st.cache_data(ttl=300) # Cache prices for 5 minutes
def get_current_price(tickers):
    """
    Fetches the last known price for a list of tickers using multiple methods
    for maximum robustness.
    """
    if not isinstance(tickers, list) or not tickers:
        return {}

    prices = {}
    
    # --- Method 1: Batch download for efficiency ---
    try:
        # Use yf.download for a short period. It's efficient for multiple tickers.
        data = yf.download(tickers, period="5d", progress=False, group_by='ticker')
        
        if not data.empty:
            for ticker in tickers:
                try:
                    # Access the 'Close' price for the specific ticker
                    # and get the last valid price in the series.
                    last_price = data[ticker]['Close'].dropna().iloc[-1]
                    if pd.notna(last_price):
                        prices[ticker] = last_price
                except (KeyError, IndexError):
                    # This ticker might have failed in the batch, will try individually later
                    prices[ticker] = None
    except Exception:
        # If the batch download fails entirely, initialize all prices to None
        for ticker in tickers:
            prices[ticker] = None

    # --- Method 2: Individual fallback for failed tickers ---
    # Find which tickers we still need a price for
    failed_tickers = [t for t, p in prices.items() if p is None]
    
    if failed_tickers:
        print(f"Batch price fetch failed for: {', '.join(failed_tickers)}. Trying individual fallback.")
        for ticker in failed_tickers:
            try:
                # Use the .info method which is good for single tickers
                info = yf.Ticker(ticker).info
                # Try a list of common keys where the price might be found
                price_keys = ['currentPrice', 'regularMarketPrice', 'open', 'previousClose']
                for key in price_keys:
                    if info.get(key) is not None:
                        prices[ticker] = info[key]
                        break # Stop once a valid price is found
            except Exception:
                # If this also fails, the ticker is likely invalid or delisted
                prices[ticker] = None

    # Final check for any remaining failures
    final_failed = [t for t, p in prices.items() if p is None]
    if final_failed:
        st.warning(f"Could not fetch a current price for: {', '.join(final_failed)}")
            
    return prices
