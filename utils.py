import streamlit as st
import yfinance as yf
import pandas as pd

@st.cache_data(ttl=300)

def get_current_price(ticker):
    """
    Fetches the current price for a ticker using yfinance.
    Tries multiple potential keys for the price.
    Returns float or None.
    """
    print(f"--- Attempting get_current_price for {ticker} ---")
    try:
        # Fetch data only once
        ticker_data = yf.Ticker(ticker)
        info = ticker_data.info

        if not info: # Handle cases where info dict is empty
             print(f"!!! Received empty info dict for {ticker}.")
             return None

        # Define potential keys for the current price, in order of preference
        price_keys_to_try = ['currentPrice', 'regularMarketPrice', 'marketPrice', 'open']
        # Add 'previousClose' as a last resort if needed:
        # price_keys_to_try = ['currentPrice', 'regularMarketPrice', 'marketPrice', 'open', 'previousClose']

        for key in price_keys_to_try:
            if key in info:
                price = info[key]
                # Check if price is a valid number (int/float) and positive
                # Use pd.isna to handle potential numpy NaN values safely
                if price is not None and not pd.isna(price) and isinstance(price, (int, float)) and price > 0:
                    print(f"+++ Successfully fetched price for {ticker} using key '{key}': {price}")
                    return float(price) # Return as float
                else:
                    # Log if key exists but value is invalid (None, NaN, zero, negative, wrong type)
                    print(f"--- Found key '{key}' for {ticker}, but value '{price}' is invalid or not positive.")

        # If loop finishes without finding a valid price
        print(f"!!! No valid/positive price found for {ticker} using keys: {price_keys_to_try}. Info keys available: {list(info.keys())}")
        return None

    except Exception as e:
        # Catch exceptions during yf.Ticker or .info access
        print(f"!!! EXCEPTION fetching info/price for {ticker}: {e}")
        return None