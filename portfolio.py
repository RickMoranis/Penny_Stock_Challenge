# portfolio.py
import pandas as pd
import streamlit as st
from utils import get_current_price # Assuming utils.py contains get_current_price(ticker)
from datetime import datetime

@st.cache_data
def calculate_portfolio(trades_df):
    portfolio = {}
    initial_capital = 500

    # Ensure timestamp is datetime
    if not trades_df.empty and 'timestamp' in trades_df.columns and not pd.api.types.is_datetime64_any_dtype(trades_df['timestamp']):
        try:
            trades_df['timestamp'] = pd.to_datetime(trades_df['timestamp'])
        except Exception as e:
            st.error(f"Error converting timestamp column: {e}")
            return {} # Return empty if timestamp fails

    # Pre-fetch current prices for all unique tickers
    unique_tickers = trades_df['ticker'].unique() if 'ticker' in trades_df.columns else []
    current_prices = {ticker: get_current_price(ticker) for ticker in unique_tickers}
    # st.write(f"Fetched current prices: {current_prices}") # Optional Debug print

    # Get the timestamp of the very first trade for baseline
    first_trade_time = trades_df['timestamp'].min() if not trades_df.empty else datetime.now()

    for participant in trades_df['participant'].unique():
        participant_trades = trades_df[trades_df['participant'] == participant].sort_values(by='timestamp').copy()
        holdings = {}
        cash_balance = initial_capital
        realized_gains_losses_list = []
        value_history = [] # To store {'timestamp': ts, 'total_value': val}

        # Add initial state before any trades
        # Use a slightly earlier time for the initial point if possible, or first trade time
        initial_time = first_trade_time - pd.Timedelta(seconds=1) if not participant_trades.empty else first_trade_time
        value_history.append({'timestamp': initial_time, 'total_value': initial_capital})

        # Helper function to calculate current total value based on holdings, cash, and a prices dict
        def get_current_total_value(current_holdings, cash, prices):
            value = cash
            for ticker, holding_data in current_holdings.items():
                price = prices.get(ticker)
                if price is not None and holding_data.get('shares', 0) > 0:
                    value += holding_data['shares'] * price
                elif holding_data.get('shares', 0) > 0: # If price fetch failed but holding exists
                     # Fallback: Add cost basis? Or Zero? Let's add cost basis for a stable value.
                     value += holding_data['shares'] * holding_data.get('avg_price', 0)
            return value

        # Process trades and record value history
        for index, trade in participant_trades.iterrows():
            ticker = trade.get('ticker')
            action = trade.get('action')
            shares = trade.get('shares')
            price = trade.get('price')
            timestamp = trade.get('timestamp')

            if not all([ticker, action, isinstance(shares, (int, float)), isinstance(price, (int, float)), timestamp]):
                st.warning(f"Skipping invalid trade data for {participant}: {trade}")
                continue

            valid_trade = False # Flag to check if trade was processed
            if action == 'Buy':
                cost = shares * price
                if cash_balance >= cost:
                    cash_balance -= cost
                    if ticker in holdings:
                        old_total_shares = holdings[ticker]['shares']
                        old_total_cost = holdings[ticker]['shares'] * holdings[ticker]['avg_price']
                        new_total_shares = old_total_shares + shares
                        new_total_cost = old_total_cost + cost
                        holdings[ticker]['shares'] = new_total_shares
                        holdings[ticker]['avg_price'] = new_total_cost / new_total_shares if new_total_shares > 0 else 0
                    else:
                        holdings[ticker] = {'shares': shares, 'avg_price': price}
                    valid_trade = True
                else:
                    st.warning(f"{participant} insufficient funds for trade {index} ({timestamp}). Skipping.")

            elif action == 'Sell':
                if ticker in holdings and holdings[ticker].get('shares', 0) >= shares:
                    sell_value = shares * price
                    cost_basis_per_share = holdings[ticker].get('avg_price', 0)
                    gain_loss = (price - cost_basis_per_share) * shares
                    cash_balance += sell_value
                    holdings[ticker]['shares'] -= shares
                    realized_gains_losses_list.append({
                        'timestamp': timestamp, 'ticker': ticker,
                        'shares_sold': shares, 'gain_loss': gain_loss
                    })
                    if holdings[ticker]['shares'] == 0: del holdings[ticker]
                    valid_trade = True
                else:
                    st.warning(f"{participant} invalid sell for trade {index} ({timestamp}). Invalid ticker or insufficient shares. Skipping.")

            # Calculate and record total value AFTER the trade if it was valid
            if valid_trade:
                 current_total_val = get_current_total_value(holdings, cash_balance, current_prices)
                 value_history.append({'timestamp': timestamp, 'total_value': current_total_val})

        # Final calculations (P/L, final value etc.)
        gains_df = pd.DataFrame(realized_gains_losses_list)
        total_realized_pl = gains_df['gain_loss'].sum() if not gains_df.empty else 0

        final_total_value = get_current_total_value(holdings, cash_balance, current_prices)

        total_unrealized_pl = 0
        current_holdings_value_dict = {}
        current_holdings_price_dict = {} # Store actual fetched prices used
        cost_of_current_holdings = 0
        value_of_current_holdings = 0

        for ticker, holding_data in holdings.items():
            current_price = current_prices.get(ticker)
            current_holdings_price_dict[ticker] = current_price # Store price (or None)

            cost_basis = holding_data.get('shares', 0) * holding_data.get('avg_price', 0)
            cost_of_current_holdings += cost_basis

            if current_price is not None and holding_data.get('shares', 0) > 0:
                holding_value = holding_data['shares'] * current_price
                current_holdings_value_dict[ticker] = holding_value
                value_of_current_holdings += holding_value
            elif holding_data.get('shares', 0) > 0: # Price fetch failed
                 current_holdings_value_dict[ticker] = None
                 # Use cost basis as value if price is unavailable? Adds stability.
                 value_of_current_holdings += cost_basis

        # Calculate unrealized P/L based on final holdings compared to cost
        total_unrealized_pl = value_of_current_holdings - cost_of_current_holdings

        portfolio[participant] = {
            'participant': participant,
            'holdings': holdings,
            'cash': cash_balance,
            'total_value': final_total_value,
            'trades': participant_trades,
            'total_realized_pl': total_realized_pl,
            'total_unrealized_pl': total_unrealized_pl,
            'current_holdings_value': current_holdings_value_dict,
            'current_holdings_price': current_holdings_price_dict,
            'value_history': value_history
        }
    return portfolio