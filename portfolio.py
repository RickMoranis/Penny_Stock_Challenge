# portfolio.py
import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta
import streamlit as st

from utils import get_current_price

@st.cache_data
def get_historical_prices(tickers, start_date, end_date):
    """
    Fetches historical daily closing prices for a list of tickers.
    This version is more robust, fetching one ticker at a time.
    """
    if not tickers:
        return pd.DataFrame()

    all_prices = []
    for ticker in tickers:
        try:
            data = yf.download(ticker, start=start_date, end=end_date, progress=False, auto_adjust=True)['Close']
            if not data.empty:
                data.name = ticker
                all_prices.append(data)
        except Exception:
            st.warning(f"Could not fetch historical data for ticker: {ticker}")
            continue
    
    if not all_prices:
        return pd.DataFrame()

    historical_df = pd.concat(all_prices, axis=1)
    return historical_df


@st.cache_data
def calculate_portfolio(trades_df: pd.DataFrame):
    """
    Calculates the daily portfolio value for each participant from the first trade to today.
    """
    if trades_df.empty:
        return {}

    initial_capital = 500.0
    portfolios = {}
    all_tickers = trades_df['ticker'].unique().tolist()
    
    start_date = trades_df['timestamp'].min().normalize()
    end_date = pd.Timestamp.now().normalize()

    if pd.isna(start_date):
        return {}

    historical_prices = get_historical_prices(all_tickers, start_date, end_date + timedelta(days=1))
    if historical_prices.empty:
        st.warning("Could not fetch any historical price data. Graphs may be inaccurate.")

    latest_prices_str = get_current_price(all_tickers)
    if latest_prices_str is None:
        latest_prices_str = {}
    latest_prices = {k: v for k, v in latest_prices_str.items() if isinstance(v, (int, float))}
    
    participants = trades_df['participant'].unique()
    for participant in participants:
        portfolios[participant] = {
            'participant': participant,
            'cash': initial_capital,
            'holdings': {},
            'realized_pl': 0,
            'value_history': [],
            'trades': trades_df[trades_df['participant'] == participant].copy()
        }

    for current_date in pd.date_range(start=start_date, end=end_date):
        daily_trades = trades_df[trades_df['timestamp'] < current_date + timedelta(days=1)]

        for participant in participants:
            participant_trades = daily_trades[daily_trades['participant'] == participant].sort_values(by='timestamp')
            
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
            
            holdings_value = 0
            if not historical_prices.empty:
                try:
                    day_prices = historical_prices.asof(current_date)
                    for ticker, data in holdings.items():
                        if ticker in day_prices and pd.notna(day_prices[ticker]):
                            holdings_value += data['shares'] * day_prices[ticker]
                except Exception:
                    holdings_value = 0 
            
            total_value = cash + holdings_value
            
            portfolios[participant]['value_history'].append({
                'timestamp': current_date,
                'total_value': total_value
            })

    for participant in participants:
        participant_trades = trades_df[trades_df['participant'] == participant].sort_values(by='timestamp')
        
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

        final_total_value = cash + current_holdings_value

        portfolios[participant]['cash'] = cash
        portfolios[participant]['holdings'] = holdings
        portfolios[participant]['total_realized_pl'] = realized_pl
        portfolios[participant]['total_unrealized_pl'] = total_unrealized_pl
        portfolios[participant]['current_holdings_value'] = {t: d['shares'] * latest_prices.get(t, 0) for t, d in holdings.items()}
        portfolios[participant]['current_holdings_price'] = current_holdings_price
        portfolios[participant]['total_value'] = final_total_value

        if portfolios[participant]['value_history']:
            portfolios[participant]['value_history'].append({
                'timestamp': pd.Timestamp.now(),
                'total_value': final_total_value
            })

    return portfolios
