# display.py
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta

# --- Style Constants and Formatting Functions ---
GAIN_COLOR = "#2ECC71"  # A nice green
LOSS_COLOR = "#E74C3C"  # A nice red
NEUTRAL_COLOR = "inherit"

def format_currency(value):
    if value is None or not isinstance(value, (int, float)): return "N/A"
    if value < 0: return f"-${abs(value):,.2f}"
    else: return f"${value:,.2f}"

def format_percentage(value):
     if value is None or not isinstance(value, (int, float)): return "N/A"
     return f"{value:.2f}%"

def color_performance(val):
    if pd.isna(val) or not isinstance(val, (int, float)): return 'color: grey'
    color = GAIN_COLOR if val > 0 else LOSS_COLOR if val < 0 else NEUTRAL_COLOR
    return f'color: {color}'


# --- Chart Function with Trade Markers ---
def display_portfolio_value_chart(value_history, user_trades, participant_name):
    st.subheader("Portfolio Value Over Time")
    if not value_history or len(value_history) < 2:
        st.info("Not enough data points to plot value history.")
        return
    try:
        history_df = pd.DataFrame(value_history)
        history_df['timestamp'] = pd.to_datetime(history_df['timestamp'])
        history_df = history_df.sort_values(by='timestamp').set_index('timestamp')
        time_frame = st.radio("Select Time Frame:", ("1D", "1W", "1M", "All"), index=3, horizontal=True, key=f"time_filter_{participant_name.replace(' ', '_')}")
        now = pd.Timestamp.now(tz=history_df.index.tz)
        
        plot_df = history_df
        start_date = plot_df.index.min()
        end_date = now

        if time_frame == "1D":
            start_date = now - timedelta(days=1)
        elif time_frame == "1W":
            start_date = now - timedelta(days=7)
        elif time_frame == "1M":
            start_date = now - timedelta(days=30)
        
        plot_df = history_df[history_df.index >= start_date]

        if plot_df.empty or len(plot_df) < 2:
             st.info(f"No portfolio data available for the selected '{time_frame}' period.")
             return
        
        fig = px.line(plot_df.reset_index(), x='timestamp', y='total_value', title=f"{participant_name}'s Portfolio Value Trend ({time_frame})", labels={'timestamp': 'Time', 'total_value': 'Portfolio Value ($)'})
        fig.update_layout(hovermode="x unified", legend_title_text="Actions")
        
        # --- FIX: Apply the zoom to the x-axis ---
        if time_frame != "All":
            fig.update_xaxes(range=[start_date, end_date])
        
        if user_trades is not None and not user_trades.empty:
            trades_df = user_trades.copy()
            trades_df['timestamp'] = pd.to_datetime(trades_df['timestamp'], errors='coerce')
            trades_df.dropna(subset=['timestamp'], inplace=True)
            if not trades_df.empty:
                trades_df = trades_df.sort_values(by='timestamp')
                merged_trades = pd.merge_asof(left=trades_df, right=history_df.reset_index(), on='timestamp', direction='nearest')
                merged_trades['hover_text'] = merged_trades.apply(lambda row: f"<b>{row['action']} {row['ticker']}</b><br>{row['shares']} shares @ {format_currency(row['price'])}", axis=1)
                buy_trades = merged_trades[merged_trades['action'] == 'Buy']
                sell_trades = merged_trades[merged_trades['action'] == 'Sell']
                if not buy_trades.empty:
                    fig.add_trace(go.Scatter(x=buy_trades['timestamp'], y=buy_trades['total_value'], mode='markers', marker=dict(symbol='triangle-up', color=GAIN_COLOR, size=12, line=dict(width=1, color='DarkSlateGrey')), name='Buy', text=buy_trades['hover_text'], hoverinfo='text'))
                if not sell_trades.empty:
                    fig.add_trace(go.Scatter(x=sell_trades['timestamp'], y=sell_trades['total_value'], mode='markers', marker=dict(symbol='triangle-down', color=LOSS_COLOR, size=12, line=dict(width=1, color='DarkSlateGrey')), name='Sell', text=sell_trades['hover_text'], hoverinfo='text'))
        
        st.plotly_chart(fig, use_container_width=True)
    except Exception as e:
        st.error(f"Error plotting portfolio value chart: {e}")


# --- Leaderboard Charts ---
def display_leaderboard_value_chart(portfolios_data):
    st.subheader("All Participants Value Over Time")
    all_history_dfs = []
    if not portfolios_data:
        st.info("No portfolio data available.")
        return
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
        combined_df = pd.concat(all_history_dfs, ignore_index=True)
        combined_df['timestamp'] = pd.to_datetime(combined_df['timestamp'])
        combined_df = combined_df.sort_values(by='timestamp')
        time_frame_leaderboard = st.radio("Select Time Frame:", ("1D", "1W", "1M", "All"), index=3, horizontal=True, key="time_filter_leaderboard")
        fig = px.line(combined_df, x='timestamp', y='total_value', color='participant', title=f"Portfolio Value Comparison ({time_frame_leaderboard})", labels={'timestamp': 'Time', 'total_value': 'Portfolio Value ($)', 'participant': 'Participant'})
        fig.update_layout(hovermode="x unified")
        now = pd.Timestamp.now(tz=combined_df['timestamp'].dt.tz)
        start_date = combined_df['timestamp'].min()
        end_date = now
        if time_frame_leaderboard == "1D": start_date = now - timedelta(days=1)
        elif time_frame_leaderboard == "1W": start_date = now - timedelta(days=7)
        elif time_frame_leaderboard == "1M": start_date = now - timedelta(days=30)
        if start_date < end_date:
             fig.update_xaxes(range=[start_date, end_date])
        st.plotly_chart(fig, use_container_width=True)
    except Exception as e:
         st.error(f"Error plotting combined value chart: {e}")

def display_leaderboard_bar_chart(leaderboard_table_data):
    st.subheader("Current Standings by Portfolio Value")
    if not leaderboard_table_data:
        st.info("No leaderboard data to display.")
        return
    try:
        df = pd.DataFrame(leaderboard_table_data)
        df = df.sort_values(by='Total Value ($)', ascending=False)
        initial_capital = 500.0
        df['color'] = df['Performance (%)'].apply(lambda p: GAIN_COLOR if p > 0 else LOSS_COLOR if p < 0 else NEUTRAL_COLOR)
        fig = go.Figure()
        fig.add_trace(go.Bar(
            y=df['Participant'], x=df['Total Value ($)'], orientation='h',
            marker=dict(color=df['color'], line=dict(color='rgba(0,0,0,0.5)', width=1)),
            text=df['Total Value ($)'].apply(format_currency), hoverinfo='text',
            hovertext=df.apply(lambda row: f"<b>{row['Participant']}</b><br>Value: {format_currency(row['Total Value ($)'])}<br>Perf: {format_percentage(row['Performance (%)'])}", axis=1)
        ))
        fig.add_vline(x=initial_capital, line_width=2, line_dash="dash", line_color="white", annotation_text="Starting Capital", annotation_position="bottom right")
        fig.update_layout(
            title_text='Leaderboard: Current Portfolio Value', xaxis_title='Total Value ($)', yaxis_title=None,
            yaxis=dict(autorange="reversed"), height=max(400, len(df) * 50), showlegend=False, bargap=0.3,
            plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)'
        )
        st.plotly_chart(fig, use_container_width=True)
    except Exception as e:
        st.error(f"Error plotting leaderboard bar chart: {e}")


# --- display_portfolio_composition_chart ---
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
        st.info("No significant assets to display in allocation chart.")
        return
    try:
        df_chart = pd.DataFrame(chart_data)
        fig = px.pie(df_chart, values='Value', names='Asset', title='Asset Allocation by Current Value', hole=0.3)
        fig.update_traces(textposition='inside', textinfo='percent+label', pull=[0.05 if n=='Cash' else 0 for n in df_chart['Asset']])
        fig.update_layout(showlegend=True, legend_title_text='Assets')
        st.plotly_chart(fig, use_container_width=True)
    except Exception as e:
        st.error(f"Error plotting allocation chart: {e}")


# --- display_trade_history ---
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


# --- display_portfolio ---
def display_portfolio(participant_data):
    st.subheader(f"Portfolio Summary")
    col1, col2, col3, col4 = st.columns(4)
    initial_capital = 500
    total_value = participant_data.get('total_value', initial_capital)
    performance = ((total_value - initial_capital) / initial_capital) * 100 if initial_capital > 0 else 0
    with col1: st.metric("💵 Cash Balance", format_currency(participant_data.get('cash')))
    with col2: st.metric("💰 Total Value", format_currency(total_value))
    with col3: st.metric(label="📈 Net Realized P/L", value=format_currency(participant_data.get('total_realized_pl', 0)))
    with col4: st.metric(label="📊 Unrealized P/L", value=format_currency(participant_data.get('total_unrealized_pl', 0)))
    st.markdown("---")
    performance_label = "🚀 Overall Performance"
    performance_value_str = format_percentage(performance)
    perf_color = color_performance(performance).replace('color: ', '')
    performance_html = f"""
    <div style="text-align: center; margin-top: -10px; margin-bottom: 10px;">
        <div style="font-size: 0.875rem; color: #808495;">{performance_label}</div>
        <div style="font-size: 2.5rem; color: {perf_color}; font-weight: 600; line-height: 1.2;">{performance_value_str}</div>
    </div>"""
    st.markdown(performance_html, unsafe_allow_html=True)
    st.divider()

    display_portfolio_value_chart(
        participant_data.get('value_history', []),
        participant_data.get('trades'),
        participant_data['participant']
    )
    st.divider()

    col_holdings, col_chart = st.columns([2, 1])
    with col_holdings:
        st.subheader("Current Holdings")
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
                holdings_df['Unrealized P/L'] = holdings_df['Current Value'] - holdings_df['Cost Basis']
                display_cols = ['Shares', 'Avg Buy Price', 'Cost Basis', 'Current Price', 'Current Value', 'Unrealized P/L']
                
                # --- FIX: Use .map() instead of deprecated .applymap() ---
                styled_df = holdings_df[display_cols].style\
                    .format({
                        'Shares': '{:,.0f}',
                        'Avg Buy Price': '${:,.3f}',
                        'Cost Basis': '${:,.2f}',
                        'Current Price': '${:,.3f}',
                        'Current Value': '${:,.2f}',
                        'Unrealized P/L': '${:,.2f}'
                    })\
                    .map(color_performance, subset=['Unrealized P/L'])
                
                st.dataframe(styled_df, use_container_width=True)
            except Exception as e:
                st.error(f"Error displaying holdings table: {e}")
        else:
            st.info("No current holdings.")
    
    with col_chart:
        display_portfolio_composition_chart(participant_data)
    
    st.divider()

    display_trade_history(participant_data.get('trades'))


# --- display_leaderboard ---
def display_leaderboard(leaderboard_table_data, all_portfolios_data):
    st.header("👑 Leaderboard")
    display_leaderboard_bar_chart(leaderboard_table_data)
    st.divider()
    with st.expander("Show Detailed History and Standings Table"):
        display_leaderboard_value_chart(all_portfolios_data)
        st.divider()
        st.subheader("Standings Table")
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
