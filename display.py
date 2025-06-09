# display.py
import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime

# --- Formatting & Color Constants ---
GAIN_COLOR = "green"
LOSS_COLOR = "red"
NEUTRAL_COLOR = "inherit"

def format_currency(value):
    """Safely formats a number as USD currency."""
    if value is None or not isinstance(value, (int, float)):
        return "N/A"
    return f"${value:,.2f}"

def format_percentage(value):
    """Safely formats a number as a percentage string."""
    if value is None or not isinstance(value, (int, float)):
        return "N/A"
    return f"{value:.2f}%"

def color_performance(val):
    """Applies color styling based on positive or negative value."""
    if pd.isna(val):
        return 'color: grey'
    color = GAIN_COLOR if val > 0 else LOSS_COLOR if val < 0 else NEUTRAL_COLOR
    return f'color: {color}'

# --- Charting Functions ---

def display_portfolio_value_chart(value_history, participant_name):
    """
    Displays an interactive line chart of an individual's portfolio value over time.
    The fix for potentially empty charts is to require only 1 data point.
    """
    st.subheader("Portfolio Value Over Time")
    if not value_history or len(value_history) < 1:
        st.info("No portfolio history available to plot a chart.")
        return

    try:
        history_df = pd.DataFrame(value_history)
        history_df['timestamp'] = pd.to_datetime(history_df['timestamp'])
        
        # A single point can be plotted, but a line needs at least two.
        if len(history_df) < 2:
            st.info("Need at least two data points (e.g., one trade) to show a trend line.")
            st.dataframe(history_df)
            return

        history_df = history_df.sort_values(by='timestamp').set_index('timestamp')

        time_frame = st.radio(
            "Select Time Frame:", ("1D", "1W", "1M", "All"),
            index=3, horizontal=True, key=f"time_filter_{participant_name}"
        )

        now = pd.Timestamp.now(tz=history_df.index.tz)
        plot_df = history_df

        if time_frame != "All":
            days = {"1D": 1, "1W": 7, "1M": 30}[time_frame]
            start_date = now - pd.Timedelta(days=days)
            
            # Find the last data point *before* the start date to anchor the chart
            try:
                anchor_point = history_df[history_df.index < start_date].iloc[-1:]
            except IndexError:
                anchor_point = pd.DataFrame() # No data before this period

            # Get data within the current period
            period_data = history_df[history_df.index >= start_date]
            plot_df = pd.concat([anchor_point, period_data])

        if plot_df.empty or len(plot_df) < 2:
            st.info(f"No portfolio data available for the selected '{time_frame}' period.")
            return

        plot_df = plot_df.reset_index()
        fig = px.line(plot_df, x='timestamp', y='total_value', title=f"{participant_name}'s Portfolio Value ({time_frame})")
        fig.update_layout(hovermode="x unified", labels={'timestamp': 'Date', 'total_value': 'Portfolio Value ($)'})
        st.plotly_chart(fig, use_container_width=True)

    except Exception as e:
        st.error(f"Error plotting portfolio value chart: {e}")

def display_leaderboard_value_chart(portfolios_data):
    """
    Displays a more accurate combined line chart by normalizing data points to a daily frequency.
    It forward-fills the last known value for each participant to create a continuous daily timeline.
    FIXED: Now requires only 1 data point per user to be included.
    """
    st.subheader("All Participants Value Over Time")
    all_history_dfs = []

    if not portfolios_data:
        st.info("No portfolio data available to build leaderboard chart.")
        return

    # 1. Collect all valid history data from portfolios
    for participant, data in portfolios_data.items():
        history = data.get('value_history')
        # FIX: Changed len(history) >= 2 to >= 1 to include users with no trades.
        if history and isinstance(history, list) and len(history) >= 1:
            try:
                df = pd.DataFrame(history)
                df['participant'] = participant
                all_history_dfs.append(df)
            except Exception:
                pass # Ignore participants with bad data

    if not all_history_dfs:
        st.info("No valid history data found across all participants to plot a chart.")
        return

    try:
        combined_df = pd.concat(all_history_dfs, ignore_index=True)
        combined_df['timestamp'] = pd.to_datetime(combined_df['timestamp']).dt.tz_localize(None)
        combined_df = combined_df.sort_values(by='timestamp')

        # 3. Create a complete daily date range
        start_date = combined_df['timestamp'].min().normalize()
        end_date = pd.Timestamp.now().normalize()
        full_date_range = pd.date_range(start=start_date, end=end_date, freq='D')

        # 4. Normalize each participant's data
        normalized_dfs = []
        for name, group in combined_df.groupby('participant'):
            group = group.set_index('timestamp').sort_index()
            group = group[~group.index.duplicated(keep='last')]
            participant_normalized = group.reindex(full_date_range)
            participant_normalized['total_value'].ffill(inplace=True) # Forward-fill values
            participant_normalized['total_value'].bfill(inplace=True) # Back-fill for users who join late
            participant_normalized['participant'] = name
            normalized_dfs.append(participant_normalized)

        if not normalized_dfs:
            st.info("Data normalization failed. Cannot plot chart.")
            return

        plot_df = pd.concat(normalized_dfs).reset_index().rename(columns={'index': 'timestamp'})

        fig = px.line(plot_df, x='timestamp', y='total_value', color='participant', title="Portfolio Value Comparison")
        fig.update_layout(hovermode="x unified", legend_title_text='Participant', labels={'timestamp': 'Date', 'total_value': 'Portfolio Value ($)'})
        fig.update_traces(line=dict(shape='hv')) # Use 'hv' shape for a step-chart look

        st.plotly_chart(fig, use_container_width=True)
    except Exception as e:
        st.error(f"Error plotting leaderboard chart: {e}")

def display_portfolio_composition_chart(participant_data):
    """Displays a pie chart of the user's asset allocation."""
    st.subheader("Portfolio Allocation")
    cash_value = participant_data.get('cash', 0)
    holdings_values = participant_data.get('current_holdings_value', {})
    
    chart_data = {'Asset': ['Cash'], 'Value': [cash_value]}
    for ticker, value in holdings_values.items():
        if value is not None and value > 0:
            chart_data['Asset'].append(ticker)
            chart_data['Value'].append(value)

    if sum(chart_data['Value']) < 0.01:
        st.info("No assets with value to display in allocation chart.")
        return
        
    df_chart = pd.DataFrame(chart_data)
    fig = px.pie(df_chart, values='Value', names='Asset', title='Asset Allocation', hole=0.3)
    fig.update_traces(textposition='inside', textinfo='percent+label')
    st.plotly_chart(fig, use_container_width=True)

# --- Main Display Functions ---

def display_portfolio(participant_data):
    """Renders the entire user dashboard view, including metrics and charts."""
    # --- Summary Metrics ---
    st.subheader("Portfolio Summary")
    col1, col2, col3, col4 = st.columns(4)
    initial_capital = 500
    total_value = participant_data.get('total_value', initial_capital)
    performance_pct = ((total_value - initial_capital) / initial_capital) * 100 if initial_capital > 0 else 0
    
    col1.metric("Cash Balance", format_currency(participant_data.get('cash')))
    col2.metric("Total Holdings Value", format_currency(total_value - participant_data.get('cash', 0)))
    col3.metric("Total Portfolio Value", format_currency(total_value))
    col4.metric("Overall Performance", format_percentage(performance_pct), delta=f"{format_currency(total_value - initial_capital)}")
    st.divider()

    # --- Value Chart ---
    display_portfolio_value_chart(participant_data.get('value_history', []), participant_data.get('participant', ''))
    st.divider()

    # --- Holdings and Allocation ---
    col_holdings, col_chart = st.columns([2, 1])
    with col_holdings:
        # --- NEW: Expandable Holdings View ---
        st.subheader("Current Holdings")
        holdings_dict = participant_data.get('holdings', {})
        user_trades_df = participant_data.get('trades')

        if not holdings_dict:
            st.info("You do not have any holdings. Buy a stock to get started!")
        else:
            for ticker, data in holdings_dict.items():
                shares = data.get('shares', 0)
                avg_price = data.get('avg_price', 0)
                current_price = participant_data.get('current_holdings_price', {}).get(ticker)
                current_value = shares * current_price if current_price is not None else shares * avg_price
                
                expander_title = f"**{ticker}**: {shares:,.0f} Shares @ Avg. Cost of {format_currency(avg_price)}"
                with st.expander(expander_title):
                    st.metric("Current Value", value=format_currency(current_value), delta=f"{format_currency(current_price)} / share")
                    
                    # Filter trades for this specific ticker
                    ticker_trades_df = user_trades_df[user_trades_df['ticker'] == ticker].copy()
                    st.dataframe(
                        ticker_trades_df[['timestamp', 'action', 'shares', 'price']].sort_values(by='timestamp', ascending=False),
                        hide_index=True, use_container_width=True
                    )

    with col_chart:
        display_portfolio_composition_chart(participant_data)
    st.divider()

def display_leaderboard(leaderboard_table_data, all_portfolios_data):
    """Renders the entire leaderboard view."""
    st.header("Leaderboard")
    
    # --- Leaderboard Chart ---
    display_leaderboard_value_chart(all_portfolios_data)
    st.divider()
    
    # --- Standings Table ---
    st.subheader("Current Standings")
    if leaderboard_table_data:
        try:
            leaderboard_df = pd.DataFrame(leaderboard_table_data)
            leaderboard_df['Performance (%)'] = pd.to_numeric(leaderboard_df['Performance (%)'], errors='coerce')
            leaderboard_df = leaderboard_df.sort_values(by='Performance (%)', ascending=False).reset_index(drop=True)
            leaderboard_df.index += 1
            leaderboard_df.index.name = 'Rank'
            
            styled_df = leaderboard_df.style.map(color_performance, subset=['Performance (%)']).format({
                'Performance (%)': '{:.2f}%', 'Total Value ($)': format_currency
            })
            st.dataframe(styled_df, use_container_width=True)
        except Exception as e:
            st.error(f"Error displaying leaderboard standings: {e}")
            st.dataframe(leaderboard_table_data) # Fallback to unstyled
    else:
        st.info("No data available for leaderboard standings.")