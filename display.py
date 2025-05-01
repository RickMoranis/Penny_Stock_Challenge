# display.py
import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime, time # Import time

# (Keep format_currency, format_percentage, GAIN_COLOR, LOSS_COLOR, NEUTRAL_COLOR, color_performance definitions)
GAIN_COLOR = "green"
LOSS_COLOR = "red"
NEUTRAL_COLOR = "inherit"

def format_currency(value):
    if value is None or not isinstance(value, (int, float)): return "N/A"
    if value < 0: return f"-${abs(value):,.2f}"
    else: return f"${value:,.2f}"

def format_percentage(value):
     if value is None or not isinstance(value, (int, float)): return "N/A"
     return f"{value:.2f}%"

def color_performance(val):
    if pd.isna(val): return 'color: grey'
    color = GAIN_COLOR if val > 0 else LOSS_COLOR if val < 0 else NEUTRAL_COLOR
    return f'color: {color}'


# --- Updated Chart Function: Individual Portfolio Value ---
def display_portfolio_value_chart(value_history, participant_name):
    """Displays line chart of individual portfolio value with time frame selection."""
    st.subheader("Portfolio Value Over Time")
    if not value_history or len(value_history) < 2:
        st.info("Not enough data points to plot value history.")
        return

    try:
        history_df = pd.DataFrame(value_history)
        history_df['timestamp'] = pd.to_datetime(history_df['timestamp'])
        history_df = history_df.sort_values(by='timestamp').set_index('timestamp') # Set timestamp as index for easier filtering

        # --- Add Time Frame Selector ---
        time_frame = st.radio(
            "Select Time Frame:",
            ("1D", "1W", "1M", "All"),
            index=3,  # Default to 'All'
            horizontal=True,
            key=f"time_filter_{participant_name}" # Unique key per participant chart
        )

        # --- Filter Data Based on Selection ---
        now = pd.Timestamp.now(tz=history_df.index.tz) # Ensure tz consistency
        start_date = None
        plot_df = history_df # Default to all data

        if time_frame == "1D":
            start_date = now.normalize() # Start of today
        elif time_frame == "1W":
            start_date = now - pd.Timedelta(days=7)
        elif time_frame == "1M":
            start_date = now - pd.Timedelta(days=30) # Approx 1 month

        if start_date:
            # Find the last data point *before* the start date to ensure the line starts correctly
            try:
                start_value_row = history_df[history_df.index < start_date].iloc[-1:]
            except IndexError:
                 start_value_row = pd.DataFrame(columns=history_df.columns) # Empty if no data before start_date

            # Filter data within the time frame
            filtered_data = history_df[history_df.index >= start_date]

            # Combine the start point (if found) and the filtered data
            plot_df = pd.concat([start_value_row, filtered_data])
            # Ensure the timestamp index is unique if start_value_row's index == start_date
            plot_df = plot_df[~plot_df.index.duplicated(keep='last')]


        if plot_df.empty or len(plot_df) < 2:
             st.info(f"No portfolio data available for the selected '{time_frame}' period.")
             return

        # Reset index for plotting with Plotly Express
        plot_df = plot_df.reset_index()

        fig = px.line(plot_df,
                      x='timestamp',
                      y='total_value',
                      title=f"{participant_name}'s Portfolio Value Trend ({time_frame})",
                      labels={'timestamp': 'Time', 'total_value': 'Portfolio Value ($)'})
        fig.update_layout(hovermode="x unified")
        st.plotly_chart(fig, use_container_width=True)

    except Exception as e:
        st.error(f"Error plotting portfolio value chart: {e}")
        st.exception(e) # Show full traceback for debugging

# --- Updated Chart Function: Leaderboard Value History ---
def display_leaderboard_value_chart(portfolios_data):
    """Displays combined line chart with time frame selection via axis zoom."""
    st.subheader("All Participants Value Over Time")
    all_history_dfs = []

    if not portfolios_data:
        st.info("No portfolio data available.")
        return

    # Collect valid history data
    for participant, data in portfolios_data.items():
        history = data.get('value_history')
        if history and isinstance(history, (list, dict)) and len(history) >= 2:
            try:
                df = pd.DataFrame(history)
                df['participant'] = participant
                all_history_dfs.append(df)
            except Exception as e:
                st.warning(f"Could not process history for {participant}: {e}")

    if not all_history_dfs:
        st.info("Not enough valid data points across participants to plot value history.")
        return

    try:
        # Combine all histories
        combined_df = pd.concat(all_history_dfs, ignore_index=True)
        combined_df['timestamp'] = pd.to_datetime(combined_df['timestamp'])
        combined_df = combined_df.sort_values(by='timestamp')

        # --- Add Time Frame Selector ---
        time_frame_leaderboard = st.radio(
            "Select Time Frame:",
            ("1D", "1W", "1M", "All"),
            index=3,  # Default to 'All'
            horizontal=True,
            key="time_filter_leaderboard" # Unique key for this chart
        )

        # Plot the *full* data first
        fig = px.line(combined_df,
                      x='timestamp',
                      y='total_value',
                      color='participant',
                      title=f"Portfolio Value Comparison ({time_frame_leaderboard})",
                      labels={'timestamp': 'Time', 'total_value': 'Portfolio Value ($)', 'participant': 'Participant'})
        fig.update_layout(hovermode="x unified")

        # --- Adjust X-axis range based on selection ---
        now = pd.Timestamp.now(tz=combined_df['timestamp'].dt.tz) # Match timezone if exists
        start_date = combined_df['timestamp'].min() # Default start
        end_date = now # Default end

        if time_frame_leaderboard == "1D":
            start_date = now.normalize()
        elif time_frame_leaderboard == "1W":
            start_date = now - pd.Timedelta(days=7)
        elif time_frame_leaderboard == "1M":
            start_date = now - pd.Timedelta(days=30)
        # 'All' uses default full range

        # Apply range to x-axis
        # Ensure start_date is not after end_date
        if start_date < end_date:
             fig.update_xaxes(range=[start_date, end_date])
        # else: use default full range if calculation is weird

        st.plotly_chart(fig, use_container_width=True)
    except Exception as e:
         st.error(f"Error plotting combined value chart: {e}")
         st.exception(e)


# (display_portfolio_composition_chart remains the same)
def display_portfolio_composition_chart(participant_data):
    st.subheader("Portfolio Allocation")
    cash_value = participant_data.get('cash', 0)
    holdings_value_dict = participant_data.get('current_holdings_value', {})
    chart_data = {'Asset': [], 'Value': []}
    if cash_value > 0.01:
        chart_data['Asset'].append('Cash')
        chart_data['Value'].append(cash_value)
    for ticker, value in holdings_value_dict.items():
        if value is not None and value > 0.01:
            chart_data['Asset'].append(ticker)
            chart_data['Value'].append(value)
    if not chart_data['Value'] or sum(chart_data['Value']) < 0.01 :
        st.info("No significant assets with value to display in allocation chart.")
        return
    try:
        df_chart = pd.DataFrame(chart_data)
        fig = px.pie(df_chart, values='Value', names='Asset', title='Asset Allocation by Current Value', hole=0.3)
        fig.update_traces(textposition='inside', textinfo='percent+label', pull=[0.05 if n=='Cash' else 0 for n in df_chart['Asset']])
        fig.update_layout(showlegend=True, legend_title_text='Assets')
        st.plotly_chart(fig, use_container_width=True)
    except Exception as e:
        st.error(f"Error plotting allocation chart: {e}")


# (display_portfolio remains largely the same, just calls the updated value chart function)
def display_portfolio(participant_data):
    st.subheader(f"Portfolio Summary")
    # ... [Summary metrics code] ...
    col1, col2, col3, col4 = st.columns(4)
    initial_capital = 500
    total_value = participant_data.get('total_value', initial_capital)
    performance = ((total_value - initial_capital) / initial_capital) * 100 if initial_capital > 0 else 0
    with col1: st.metric("💰 Cash Balance", format_currency(participant_data.get('cash')))
    with col2: st.metric("🏦 Total Value", format_currency(total_value))
    with col3: st.metric(label="💸 Net Realized P/L", value=format_currency(participant_data.get('total_realized_pl', 0)))
    with col4: st.metric(label="💭 Unrealized P/L", value=format_currency(participant_data.get('total_unrealized_pl', 0)))
    st.markdown("---")
    performance_label = "📈 Overall Performance"
    performance_value_str = format_percentage(performance)
    if isinstance(performance, (int, float)):
        if performance > 0: perf_color = GAIN_COLOR
        elif performance < 0: perf_color = LOSS_COLOR
        else: perf_color = NEUTRAL_COLOR
    else: perf_color = NEUTRAL_COLOR
    performance_html = f"""
    <div style="text-align: center; margin-top: -10px; margin-bottom: 10px;">
        <div style="font-size: 0.875rem; color: #808495;">{performance_label}</div>
        <div style="font-size: 2.5rem; color: {perf_color}; font-weight: 600; line-height: 1.2;">{performance_value_str}</div>
    </div>
    """
    st.markdown(performance_html, unsafe_allow_html=True)
    st.divider()

    # --- Call Individual Value Chart (Now includes time filter radio) ---
    display_portfolio_value_chart(participant_data.get('value_history', []), participant_data['participant'])
    st.divider()

    # --- Holdings Table and Allocation Chart ---
    col_holdings, col_chart = st.columns([2, 1])
    with col_holdings:
        # (Holdings table display code remains the same)
        st.subheader("Holdings")
        # ... [Previous holdings table code] ...
        holdings_dict = participant_data.get('holdings', {})
        if holdings_dict:
            try:
                holdings_df = pd.DataFrame.from_dict(holdings_dict, orient='index')
                holdings_df.index.name = 'Ticker'
                holdings_df.rename(columns={'shares': 'Shares', 'avg_price': 'Avg Buy Price'}, inplace=True)
                holdings_df['Cost Basis'] = holdings_df['Shares'] * holdings_df['Avg Buy Price']
                current_prices = participant_data.get('current_holdings_price', {})
                holdings_df['Current Price'] = pd.to_numeric(holdings_df.index.map(current_prices), errors='coerce')
                holdings_df['Current Value'] = holdings_df['Shares'] * holdings_df['Current Price']
                holdings_df['Current Value'] = pd.to_numeric(holdings_df['Current Value'], errors='coerce')
                holdings_df['Unrealized P/L'] = holdings_df['Current Value'] - holdings_df['Cost Basis']
                columns_to_format = {
                    'Avg Buy Price': format_currency, 'Cost Basis': format_currency,
                    'Current Price': format_currency, 'Current Value': format_currency,
                    'Unrealized P/L': format_currency, 'Shares': '{:,.0f}'
                }
                display_cols = ['Shares', 'Avg Buy Price', 'Cost Basis', 'Current Price', 'Current Value', 'Unrealized P/L']
                formatted_holdings_df = holdings_df[display_cols].copy()
                for col, format_func in columns_to_format.items():
                     if col in formatted_holdings_df.columns:
                         if isinstance(format_func, str): formatted_holdings_df[col] = formatted_holdings_df[col].map(lambda x: format_func.format(x) if pd.notnull(x) else 'N/A')
                         else: formatted_holdings_df[col] = formatted_holdings_df[col].apply(lambda x: format_func(x) if pd.notnull(x) else 'N/A')
                st.dataframe(formatted_holdings_df, use_container_width=True)
            except Exception as e: st.error(f"Error displaying holdings table: {e}")
        else: st.info("No current holdings.")

    with col_chart:
        display_portfolio_composition_chart(participant_data)

    st.divider()


# (display_trade_history remains the same)
def display_trade_history(trades):
    st.subheader(f"Trade History")
    if isinstance(trades, pd.DataFrame) and not trades.empty:
        try:
            cols_to_display = ['timestamp', 'ticker', 'action', 'shares', 'price']
            display_df = trades[cols_to_display].copy()
            rename_map = {'timestamp': 'Timestamp', 'ticker': 'Ticker', 'action': 'Action', 'shares': 'Shares', 'price': 'Price ($)',}
            display_df.rename(columns=rename_map, inplace=True)
            display_df['Price ($)'] = display_df['Price ($)'].apply(lambda x: f"{x:,.2f}" if pd.notnull(x) else '')
            display_df['Timestamp'] = pd.to_datetime(display_df['Timestamp']).dt.strftime('%Y-%m-%d %H:%M:%S')
            st.dataframe(display_df.sort_values(by='Timestamp', ascending=False), use_container_width=True, hide_index=True)
        except Exception as e: st.error(f"Error displaying trade history: {e}")
    else: st.info("No trades recorded yet.")


# (display_leaderboard remains largely the same, just calls the updated value chart function)
def display_leaderboard(leaderboard_table_data, all_portfolios_data):
    st.header("🏆 Leaderboard")
    # Display the combined value chart (now includes time filter radio)
    display_leaderboard_value_chart(all_portfolios_data)
    st.divider()
    # Display the Leaderboard Table Standings
    st.subheader("Current Standings")
    if leaderboard_table_data:
        try:
            leaderboard_df = pd.DataFrame(leaderboard_table_data)
            leaderboard_df['Performance (%)'] = pd.to_numeric(leaderboard_df['Performance (%)'], errors='coerce')
            leaderboard_df = leaderboard_df.sort_values(by='Performance (%)', ascending=False, na_position='last')
            leaderboard_df = leaderboard_df.reset_index(drop=True)
            leaderboard_df.index += 1
            leaderboard_df.index.name = 'Rank'
            styled_df = leaderboard_df.style\
                .map(color_performance, subset=['Performance (%)'])\
                .format({'Performance (%)': '{:.2f}%', 'Total Value ($)': '${:,.2f}'})
            st.dataframe(styled_df, use_container_width=True)
        except Exception as e:
            st.error(f"Error displaying leaderboard table: {e}")
            st.dataframe(leaderboard_table_data)
    else:
        st.info("No trades recorded yet for the leaderboard.")