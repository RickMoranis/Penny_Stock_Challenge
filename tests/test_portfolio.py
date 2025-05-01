# tests/test_portfolio.py

import pandas as pd
from datetime import datetime, timezone
import pytest
from unittest import mock # Used for mocking external calls

# Make sure the portfolio module can be imported (adjust path if necessary)
# This assumes 'tests' is in the root alongside 'portfolio.py'
from portfolio import calculate_portfolio

# Use pytest.approx for comparing floating point numbers
approx = pytest.approx

# --- Test Scenarios ---

@mock.patch('portfolio.get_current_price') # Mock the price function *where it's used*
def test_empty_trades(mock_get_price):
    """Test calculation with no trades."""
    mock_get_price.return_value = None # Mock shouldn't be called anyway
    trades = pd.DataFrame(columns=['participant', 'timestamp', 'ticker', 'action', 'shares', 'price'])
    # Convert timestamp column to datetime if empty df is created without it
    trades['timestamp'] = pd.to_datetime(trades['timestamp'])

    portfolio_results = calculate_portfolio(trades.copy()) # Pass a copy

    assert portfolio_results == {} # Expect an empty result dictionary

@mock.patch('portfolio.get_current_price')
def test_single_buy(mock_get_price):
    """Test calculation after a single buy."""
    # Define mock prices
    mock_prices = {'GME': 15.00}
    mock_get_price.side_effect = lambda ticker: mock_prices.get(ticker)

    trades_list = [{
        'participant': 'user1',
        'timestamp': datetime(2024, 5, 1, 10, 0, 0, tzinfo=timezone.utc),
        'ticker': 'GME', 'action': 'Buy', 'shares': 10, 'price': 12.00
    }]
    trades = pd.DataFrame(trades_list)
    trades['timestamp'] = pd.to_datetime(trades['timestamp'])

    portfolio_results = calculate_portfolio(trades.copy())

    # Expected results
    initial_capital = 500.0
    cost = 10 * 12.00
    expected_cash = initial_capital - cost
    expected_holding_value = 10 * 15.00 # Based on mock current price
    expected_total_value = expected_cash + expected_holding_value
    expected_unrealized_pl = expected_holding_value - cost

    assert 'user1' in portfolio_results
    user_portfolio = portfolio_results['user1']

    assert user_portfolio['cash'] == approx(expected_cash)
    assert user_portfolio['holdings'] == {
        'GME': {'shares': 10, 'avg_price': approx(12.00)}
    }
    assert user_portfolio['total_realized_pl'] == approx(0.0)
    assert user_portfolio['total_unrealized_pl'] == approx(expected_unrealized_pl)
    assert user_portfolio['total_value'] == approx(expected_total_value)
    # Check value history (initial state + 1 trade)
    assert len(user_portfolio['value_history']) == 2
    assert user_portfolio['value_history'][0]['total_value'] == approx(initial_capital)
    assert user_portfolio['value_history'][1]['total_value'] == approx(expected_total_value) # Value uses current price

@mock.patch('portfolio.get_current_price')
def test_buy_sell_profit(mock_get_price):
    """Test calculation after buying and selling some shares at a profit."""
    mock_prices = {'AMC': 5.00} # Current price for remaining shares
    mock_get_price.side_effect = lambda ticker: mock_prices.get(ticker)

    trades_list = [
        {'participant': 'user2', 'timestamp': datetime(2024, 5, 1, 10, 0, 0, tzinfo=timezone.utc), 'ticker': 'AMC', 'action': 'Buy', 'shares': 20, 'price': 4.00},
        {'participant': 'user2', 'timestamp': datetime(2024, 5, 1, 11, 0, 0, tzinfo=timezone.utc), 'ticker': 'AMC', 'action': 'Sell', 'shares': 5, 'price': 6.00}
    ]
    trades = pd.DataFrame(trades_list)
    trades['timestamp'] = pd.to_datetime(trades['timestamp'])

    portfolio_results = calculate_portfolio(trades.copy())

    # Expected results
    initial_capital = 500.0
    buy_cost = 20 * 4.00
    sell_proceeds = 5 * 6.00
    cost_basis_sold = 5 * 4.00 # Avg buy price was 4.00
    realized_gain = sell_proceeds - cost_basis_sold # 5 * (6.00 - 4.00) = 10.00
    expected_cash = initial_capital - buy_cost + sell_proceeds

    remaining_shares = 20 - 5
    cost_basis_remaining = remaining_shares * 4.00
    current_value_remaining = remaining_shares * 5.00 # Mock price is 5.00
    expected_unrealized_pl = current_value_remaining - cost_basis_remaining
    expected_total_value = expected_cash + current_value_remaining

    assert 'user2' in portfolio_results
    user_portfolio = portfolio_results['user2']

    assert user_portfolio['cash'] == approx(expected_cash)
    assert user_portfolio['holdings'] == {
        'AMC': {'shares': 15, 'avg_price': approx(4.00)}
    }
    assert user_portfolio['total_realized_pl'] == approx(realized_gain)
    assert user_portfolio['total_unrealized_pl'] == approx(expected_unrealized_pl)
    assert user_portfolio['total_value'] == approx(expected_total_value)
    # Check value history (initial + buy + sell)
    assert len(user_portfolio['value_history']) == 3


# --- Add more test cases ---
# - Test selling all shares
# - Test multiple buys affecting average price
# - Test multiple participants
# - Test scenario where get_current_price returns None for a holding
# - Test invalid trade data handling (if calculate_portfolio includes checks)