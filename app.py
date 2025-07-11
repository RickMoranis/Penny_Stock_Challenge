# app.py
import streamlit as st
import pandas as pd
import os
import yfinance as yf
from datetime import datetime, timezone
import streamlit_authenticator as stauth

# Import from project modules
from data_handler import load_data, save_trade, delete_trade, admin_delete_trade, process_and_save_csv
from auth_handler import (
    get_all_users, add_user, get_user_by_username, get_user_by_email, delete_user,
    update_user_password, check_password
)
from portfolio import calculate_portfolio
from utils import get_current_price
from display import display_portfolio, display_leaderboard

# --- Page Configuration ---
st.set_page_config(
    page_title="Penny Stock Competition",
    layout="wide",
    initial_sidebar_state="expanded",
)

# --- Load Dynamic Credentials from Database ---
credentials_dict = {"usernames": {}}
try:
    db_users = get_all_users()
    if db_users:
        for user in db_users:
            if all(k in user for k in ['username', 'name', 'email', 'hashed_password']):
                 credentials_dict["usernames"][user['username']] = {
                     "email": user['email'],
                     "name": user['name'],
                     "password": user['hashed_password']
                 }
except Exception as e:
    st.error(f"Critical Error: Failed to load user credentials from database: {e}")
    credentials_dict = {"usernames": {}}


# --- Initialize Authenticator ---
authenticator = None
try:
    if 'RAILWAY_ENVIRONMENT' in os.environ:
        cookie_name = os.environ.get("COOKIE_NAME")
        cookie_key = os.environ.get("COOKIE_KEY")
        cookie_expiry = int(os.environ.get("COOKIE_EXPIRY_DAYS", "30"))
    else:
        st.warning("Running in local mode. Using default cookie settings.")
        cookie_name = "pennystockcookie_local"
        cookie_key = "a_default_secret_key_for_local_dev"
        cookie_expiry = 30
    
    authenticator = stauth.Authenticate(credentials_dict, cookie_name, cookie_key, cookie_expiry)
except Exception as e:
     st.error(f"Error initializing authenticator: {e}")
     st.stop()


# --- Authentication Check and App Logic ---
if st.session_state.get("authentication_status"):
    name = st.session_state.get("name")
    username = st.session_state.get("username")

    current_user_data = get_user_by_username(username)
    if current_user_data:
        st.session_state.is_admin = (current_user_data.get('is_admin', 0) == 1)
    else:
        st.session_state.is_admin = False

    # --- Sidebar ---
    st.sidebar.write(f'Welcome *{name}* ({username})')
    if st.session_state.get('is_admin'): st.sidebar.info("👑 Admin Access")
    authenticator.logout('Logout', 'sidebar', key='logout_button')
    st.sidebar.divider()

    with st.sidebar.expander("🔑 Change My Password"):
        with st.form("change_password_form", clear_on_submit=True):
            current_password = st.text_input("Current Password", type="password")
            new_password = st.text_input("New Password", type="password")
            confirm_new_password = st.text_input("Confirm New Password", type="password")
            if st.form_submit_button("Change Password"):
                if not all([current_password, new_password, confirm_new_password]):
                    st.warning("Please fill all password fields.")
                elif new_password != confirm_new_password:
                    st.error("New passwords do not match.")
                else:
                    user_data = get_user_by_username(username)
                    if user_data and check_password(current_password, user_data['hashed_password']):
                        if update_user_password(username, new_password):
                            st.success("Password updated successfully!")
                        else: st.error("Failed to update password.")
                    else: st.error("Current password is not correct.")
    st.sidebar.divider()

    with st.sidebar.expander("⬆️ Import Trades from CSV"):
        with st.form("csv_upload_form"):
            uploaded_file = st.file_uploader("Choose a CSV file", type="csv", help="CSV must have columns: timestamp, ticker, action, shares, price")
            if st.form_submit_button("Import Trades"):
                if uploaded_file is not None:
                    with st.spinner("Processing file..."):
                        success, message = process_and_save_csv(uploaded_file, username)
                        if success:
                            st.success(message)
                            st.cache_data.clear()
                            st.rerun()
                        else: st.error(message)
                else: st.warning("Please upload a file before importing.")
    st.sidebar.divider()

    st.sidebar.header(f"Enter New Trade")
    trades = load_data()
    portfolios = calculate_portfolio(trades.copy())
    existing_tickers = sorted([str(t) for t in trades['ticker'].dropna().unique()]) if not trades.empty else []
    
    with st.sidebar.form("new_trade_form", clear_on_submit=True):
        ticker_options = ["-- Enter New Ticker --"] + existing_tickers
        selected_ticker_option = st.selectbox("Ticker Symbol:", ticker_options)
        new_ticker_input = ""
        if selected_ticker_option == "-- Enter New Ticker --":
            new_ticker_input = st.text_input("Enter New Ticker Symbol:", placeholder="e.g., GME").upper().strip()
        action = st.selectbox("Action:", ["Buy", "Sell"])
        shares = st.number_input("Number of Shares:", min_value=1, step=1)
        price = st.number_input("Price per Share:", min_value=0.001, step=0.001, format="%.3f")
        if st.form_submit_button("Record Trade", type="primary"):
            ticker_to_use = new_ticker_input if selected_ticker_option == "-- Enter New Ticker --" else selected_ticker_option
            if ticker_to_use:
                new_trade_df = pd.DataFrame([{'participant': username, 'timestamp': datetime.now(timezone.utc), 'ticker': ticker_to_use, 'action': action, 'shares': shares, 'price': price}])
                save_trade(new_trade_df)
                st.sidebar.success(f"Trade recorded!")
                st.cache_data.clear()
                st.rerun()
            else:
                st.sidebar.error("Please select or enter a ticker.")

    # --- Main Page Content ---
    st.title(f"📈 Penny Stock Trading Competition")
    st.markdown("---")

    col1, col2 = st.columns([3, 1])
    with col1:
        view_options = ["My Dashboard", "Leaderboard"]
        if st.session_state.get('is_admin'): view_options.append("Admin Panel")
        view_option = st.selectbox("Select View:", view_options, label_visibility="collapsed")
    with col2:
        if st.button("🔄 Refresh Live Prices", use_container_width=True):
            st.cache_data.clear()
            st.toast("Prices and portfolios refreshed!", icon="✅")
    st.markdown("---")

    if view_option == "My Dashboard":
        participant_data = portfolios.get(username)
        if participant_data:
            display_portfolio(participant_data)
        else:
            st.info("👋 Welcome! Enter your first trade to get started.")
    elif view_option == "Leaderboard":
        leaderboard_table_data = [{'Participant': p_data.get('participant', p_name), 'Performance (%)': ((p_data.get('total_value', 500) - 500) / 500) * 100, 'Total Value ($)': p_data.get('total_value', 500)} for p_name, p_data in portfolios.items()]
        display_leaderboard(leaderboard_table_data, portfolios)
    elif view_option == "Admin Panel":
        if not st.session_state.get('is_admin'):
            st.error("⛔ Access Denied.")
            st.stop()
        
        st.header("👑 Admin Panel")
        admin_tab1, admin_tab2, admin_tab3 = st.tabs(["User Management", "Trade Management", "View User Dashboard"])

        with admin_tab1:
            st.subheader("Manage Users")
            all_users_data = get_all_users()
            if all_users_data:
                users_df = pd.DataFrame(all_users_data)
                st.dataframe(users_df[['user_id', 'username', 'name', 'email', 'registration_date', 'is_admin']], hide_index=True, use_container_width=True)
                
                col_del, col_reset = st.columns(2)
                with col_del:
                    st.subheader("Delete User")
                    user_to_delete = st.selectbox("Select user to delete:", [""] + [u['username'] for u in all_users_data if u['username'] != username])
                    if user_to_delete and st.button(f"⚠️ Delete User '{user_to_delete}'", type="primary"):
                        if delete_user(user_to_delete): st.success(f"User '{user_to_delete}' deleted."); st.cache_data.clear(); st.rerun()
                        else: st.error(f"Failed to delete '{user_to_delete}'.")
                with col_reset:
                    st.subheader("Reset User Password")
                    user_to_reset = st.selectbox("Select user to reset:", [""] + [u['username'] for u in all_users_data])
                    if user_to_reset and st.button(f"🔑 Reset password for '{user_to_reset}'"):
                        if update_user_password(user_to_reset, "password123"): st.success(f"Password for '{user_to_reset}' reset to: `password123`")
                        else: st.error(f"Failed to reset password.")
            else: st.info("No users found.")

        with admin_tab2:
            st.subheader("Manage All Trades")
            if not trades.empty:
                st.info(f"Displaying all {len(trades)} trades in the system.")
                # Create a header
                cols = st.columns([2, 3, 1, 1, 1, 1, 1])
                cols[0].write("**Participant**")
                cols[1].write("**Timestamp**")
                cols[2].write("**Ticker**")
                cols[3].write("**Action**")
                cols[4].write("**Shares**")
                cols[5].write("**Price**")
                cols[6].write("**Delete**")
                st.markdown("---")

                for index, trade in trades.sort_values(by='timestamp', ascending=False).iterrows():
                    trade_id = trade['id']
                    cols = st.columns([2, 3, 1, 1, 1, 1, 1])
                    cols[0].write(f"{trade['participant']}")
                    cols[1].write(trade['timestamp'].strftime('%Y-%m-%d %H:%M:%S') if pd.notnull(trade['timestamp']) else "No Timestamp")
                    cols[2].write(trade['ticker'])
                    cols[3].write(trade['action'])
                    cols[4].write(f"{trade['shares']:,.0f}")
                    cols[5].write(f"${trade['price']:.3f}")
                    if cols[6].button("🗑️", key=f"admin_delete_{trade_id}", help=f"Delete Trade ID {trade_id}"):
                        if admin_delete_trade(trade_id):
                            st.success(f"Trade ID {trade_id} deleted.")
                            st.cache_data.clear()
                            st.rerun()
                        else: st.error(f"Failed to delete trade ID {trade_id}.")
            else: st.info("No trades in the system.")

        with admin_tab3:
            st.subheader("View Participant Dashboard")
            all_participants = sorted(portfolios.keys())
            if all_participants:
                selected_user = st.selectbox("Select a user to view their dashboard:", all_participants)
                if selected_user:
                    st.divider()
                    st.markdown(f"### 👁️ Viewing Dashboard for: **{selected_user}**")
                    user_portfolio_data = portfolios.get(selected_user)
                    if user_portfolio_data:
                        display_portfolio(user_portfolio_data)
                    else: st.warning(f"No portfolio data found for {selected_user}")
            else: st.info("No participants with portfolios to display.")

# --- User NOT Logged In ---
else:
    st.title("📈 Penny Stock Trading Competition")
    st.markdown("Please log in or register to participate.")
    st.divider()
    login_tab, register_tab = st.tabs(["Login", "Register"])
    with login_tab:
        st.subheader("Member Login")
        if not credentials_dict["usernames"]: st.warning("No users exist. Please register an account.")
        else:
            authenticator.login(location='main')
            if st.session_state.get("authentication_status") is False: st.error('Username/password is incorrect.')
            elif st.session_state.get("authentication_status") is None: st.info('Please enter your credentials.')
    with register_tab:
        st.subheader("Create New Account")
        with st.form("New_User_Registration_Form"):
            reg_name = st.text_input("Full Name")
            reg_email = st.text_input("Email Address")
            reg_username = st.text_input("Desired Username")
            reg_password = st.text_input("Password", type="password")
            reg_password_confirm = st.text_input("Confirm Password", type="password")
            if st.form_submit_button("Register Account"):
                if not all([reg_name, reg_email, reg_username, reg_password, reg_password_confirm]): st.warning("Please fill all fields.")
                elif reg_password != reg_password_confirm: st.error("Passwords do not match.")
                elif "@" not in reg_email or "." not in reg_email.split('@')[-1]: st.error("Please enter a valid email.")
                else:
                    success, message = add_user(reg_username, reg_name, reg_email, reg_password)
                    if success: st.success(message); st.info("Registration successful! Proceed to the Login tab.")
                    else: st.error(message)
