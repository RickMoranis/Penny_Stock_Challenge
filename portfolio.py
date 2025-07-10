# portfolio.py
import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta
import streamlit as st

# --- NEW: Import get_current_price from utils ---
from utils import get_current_price

# Use Streamlit's caching for the price fetching function
@st.cache_data
def get_historical_prices(tickers, start_date, end_date):
    """
    Fetches historical daily closing prices for a list of tickers.
    Caches the result to avoid repeated API calls.
    """
    if not tickers:
        return pd.DataFrame()
    try:
        # Download historical data for all tickers at once
        data = yf.download(list(tickers), start=start_date, end=end_date, progress=False)['Close']
        # If only one ticker, yf returns a Series, convert it to DataFrame
        if isinstance(data, pd.Series):
            data = data.to_frame(name=list(tickers)[0])
        return data
    except Exception as e:
        st.error(f"Failed to download historical prices: {e}")
        return pd.DataFrame()

@st.cache_data
def calculate_portfolio(trades_df: pd.DataFrame):
    """
    Calculates the daily portfolio value for each participant from the first trade to today.
    """
    if trades_df.empty:
        return {}

    # --- Initialization ---
    initial_capital = 500.0
    portfolios = {}
    all_tickers = trades_df['ticker'].unique().tolist()
    
    # Determine date range for historical price fetching
    start_date = trades_df['timestamp'].min().normalize()
    # --- CORRECTED LINE: Use pandas Timestamp for .normalize() method ---
    end_date = pd.Timestamp.now().normalize()

    if pd.isna(start_date):
        return {}

    # Fetch all required historical prices in one go
    historical_prices = get_historical_prices(all_tickers, start_date, end_date + timedelta(days=1))
    if historical_prices.empty:
        st.warning("Could not fetch historical price data. Portfolio values may not be accurate.")

    # Get the latest prices for current value calculation
    latest_prices_str = get_current_price(all_tickers)
    latest_prices = {k: v for k, v in latest_prices_str.items() if isinstance(v, (int, float))}
    
    # --- Main Daily Calculation Loop ---
    participants = trades_df['participant'].unique()
    for participant in participants:
        portfolios[participant] = {
            'participant': participant,
            'cash': initial_capital,
            'holdings': {},  # {ticker: {'shares': float, 'avg_price': float}}
            'realized_pl': 0,
            'value_history': [],
            'trades': trades_df[trades_df['participant'] == participant].copy()
        }

    # Iterate through each day from the start to the end
    for current_date in pd.date_range(start=start_date, end=end_date):
        # Get trades that happened on or before the start of this day
        daily_trades = trades_df[trades_df['timestamp'] < current_date + timedelta(days=1)]

        # Recalculate state for each participant up to this day
        for participant in participants:
            participant_trades = daily_trades[daily_trades['participant'] == participant].sort_values(by='timestamp')
            
            # Reset state for daily recalculation
            cash = initial_capital
            holdings = {}
            realized_pl = 0

            # Process trades chronologically
            for _, trade in participant_trades.iterrows():
                shares = trade['shares']
                price = trade['price']
                ticker = trade['ticker']
                cost = shares * price

                if trade['action'] == 'Buy':
                    cash -= cost
                    if ticker in holdings:
                        old_shares = holdings[ticker]['shares']
                        old_cost = holdings[ticker]['avg_price'] * old_shares
                        new_shares = old_shares + shares
                        holdings[ticker]['avg_price'] = (old_cost + cost) / new_shares
                        holdings[ticker]['shares'] = new_shares
                    else:
                        holdings[ticker] = {'shares': shares, 'avg_price': price}
                
                elif trade['action'] == 'Sell':
                    if ticker in holdings and holdings[ticker]['shares'] >= shares:
                        cash += cost
                        realized_pl += (price - holdings[ticker]['avg_price']) * shares
                        holdings[ticker]['shares'] -= shares
                        if holdings[ticker]['shares'] < 1e-6: # If effectively zero shares
                            del holdings[ticker]
            
            # --- Calculate Portfolio Value for the current_date ---
            holdings_value = 0
            if not historical_prices.empty:
                try:
                    # Get prices for the current day, forward-fill to handle weekends/holidays
                    day_prices = historical_prices.asof(current_date)
                    for ticker, data in holdings.items():
                        if ticker in day_prices and pd.notna(day_prices[ticker]):
                            holdings_value += data['shares'] * day_prices[ticker]
                except Exception:
                    # Fallback if pricing data for the day is problematic
                    holdings_value = 0 
            
            total_value = cash + holdings_value
            
            # Append to this participant's value history
            portfolios[participant]['value_history'].append({
                'timestamp': current_date,
                'total_value': total_value
            })

    # --- Final Calculation for Current State (using latest prices) ---
    for participant in participants:
        participant_trades = trades_df[trades_df['participant'] == participant].sort_values(by='timestamp')
        
        # Reset and recalculate final state
        cash = initial_capital
        holdings = {}
        realized_pl = 0
        
        for _, trade in participant_trades.iterrows():
            shares = trade['shares']
            price = trade['price']
            ticker = trade['ticker']
            cost = shares * price
            if trade['action'] == 'Buy':
                cash -= cost
                if ticker in holdings:
                    old_shares = holdings[ticker]['shares']
                    old_cost = holdings[ticker]['avg_price'] * old_shares
                    new_shares = old_shares + shares
                    holdings[ticker]['avg_price'] = (old_cost + cost) / new_shares
                    holdings[ticker]['shares'] = new_shares
                else:
                    holdings[ticker] = {'shares': shares, 'avg_price': price}
            elif trade['action'] == 'Sell':
                if ticker in holdings and holdings[ticker]['shares'] >= shares:
                    cash += cost
                    realized_pl += (price - holdings[ticker]['avg_price']) * shares
                    holdings[ticker]['shares'] -= shares
                    if holdings[ticker]['shares'] < 1e-6:
                        del holdings[ticker]

        # Calculate final current values using latest prices
        current_holdings_value = 0
        current_holdings_price = {}
        total_unrealized_pl = 0
        
        for ticker, data in holdings.items():
            current_price = latest_prices.get(ticker)
            if current_price is not None:
                value = data['shares'] * current_price
                current_holdings_value += value
                current_holdings_price[ticker] = current_price
                total_unrealized_pl += (current_price - data['avg_price']) * data['shares']

        # Update the portfolio dictionary with the final, current state
        portfolios[participant]['cash'] = cash
        portfolios[participant]['holdings'] = holdings
        portfolios[participant]['total_realized_pl'] = realized_pl
        portfolios[participant]['total_unrealized_pl'] = total_unrealized_pl
        portfolios[participant]['current_holdings_value'] = {t: d['shares'] * latest_prices.get(t, 0) for t, d in holdings.items()}
        portfolios[participant]['current_holdings_price'] = current_holdings_price
        portfolios[participant]['total_value'] = cash + current_holdings_value

    return portfolios
