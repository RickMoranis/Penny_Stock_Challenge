# app.py
import streamlit as st
import pandas as pd
import os
import yfinance as yf
from datetime import datetime, timezone
import streamlit_authenticator as stauth

# Import from project modules
from data_handler import load_data, save_trade, delete_trade
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
    menu_items={
        'Get Help': None,
        'Report a bug': None,
        'About': "A friendly penny stock trading competition app!"
    }
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
            else:
                 st.warning(f"Skipping database user due to incomplete data: {user.get('username', 'N/A')}")
except Exception as e:
    st.error(f"Critical Error: Failed to load user credentials from database: {e}")
    credentials_dict = {"usernames": {}}


# --- Initialize Authenticator ---
authenticator = None
try:
    # Read cookie config from Environment Variables (set in Railway or your deployment platform)
    cookie_name = os.environ.get("COOKIE_NAME", "pennystockcookie_local")
    cookie_key = os.environ.get("COOKIE_KEY", "a_default_secret_key_for_local_dev") # Use a default for local dev
    cookie_expiry_str = os.environ.get("COOKIE_EXPIRY_DAYS", "30")

    if cookie_key == "a_default_secret_key_for_local_dev":
        st.warning("Using a default cookie key. Set the COOKIE_KEY environment variable for production.")

    authenticator = stauth.Authenticate(
        credentials_dict,
        cookie_name,
        cookie_key,
        int(cookie_expiry_str)
    )
except Exception as e:
     st.error(f"Error initializing authenticator: {e}")
     st.stop()


# --- Authentication Check and App Logic ---
if st.session_state.get("authentication_status"):
    # --- User is Logged In ---
    name = st.session_state.get("name")
    username = st.session_state.get("username")

    # --- Store Admin Status in Session State ---
    current_user_data = get_user_by_username(username)
    if current_user_data:
        st.session_state.is_admin = (current_user_data.get('is_admin', 0) == 1)
    else:
        st.session_state.is_admin = False
        st.warning("Could not verify user data after login.")

    # --- Sidebar ---
    st.sidebar.write(f'Welcome *{name}* ({username})')
    if st.session_state.get('is_admin'):
        st.sidebar.info("👑 Admin Access")
    authenticator.logout('Logout', 'sidebar', key='logout_button')
    st.sidebar.divider()

    with st.sidebar.expander("🔑 Change My Password"):
        with st.form("change_password_form", clear_on_submit=True):
            current_password = st.text_input("Current Password", type="password", key="change_pw_current")
            new_password = st.text_input("New Password", type="password", key="change_pw_new")
            confirm_new_password = st.text_input("Confirm New Password", type="password", key="change_pw_confirm")
            submitted = st.form_submit_button("Change Password")

            if submitted:
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
    # --- Trade Entry Form ---
    st.sidebar.header(f"Enter New Trade")
    try:
        trades = load_data()
        portfolios = calculate_portfolio(trades.copy())
    except Exception as e:
        st.error(f"An critical error occurred loading data or calculating portfolios: {e}")
        trades = pd.DataFrame()
        portfolios = {}
    existing_tickers = sorted([str(t) for t in trades['ticker'].dropna().unique()]) if not trades.empty else []
    ticker_options = ["-- Enter New Ticker --"] + existing_tickers
    selected_ticker_option = st.sidebar.selectbox("Ticker Symbol:", ticker_options, key='ticker_select_sidebar')
    new_ticker_input = ""
    if selected_ticker_option == "-- Enter New Ticker --":
        new_ticker_input = st.sidebar.text_input("Enter New Ticker Symbol:", placeholder="e.g., GME", key='new_ticker_sidebar').upper().strip()
    action = st.sidebar.selectbox("Action:", ["Buy", "Sell"], key='action_select_sidebar')
    shares = st.sidebar.number_input("Number of Shares:", min_value=1, step=1, key='shares_input_sidebar')
    price = st.sidebar.number_input("Price per Share:", min_value=0.001, step=0.001, format="%.3f", key='price_input_sidebar')
    trade_button = st.sidebar.button("Record Trade", type="primary", key='trade_button_sidebar')

    if trade_button:
        # --- Trade Processing Logic ---
        basic_inputs_valid = False; ticker_determined = False; ticker_validated = False; sell_action_valid = True
        ticker_to_use = ""

        if shares > 0 and price > 0: basic_inputs_valid = True
        else: st.sidebar.error("Shares and Price must be positive numbers.")

        if basic_inputs_valid:
            if selected_ticker_option == "-- Enter New Ticker --":
                if new_ticker_input: ticker_to_use = new_ticker_input; validation_needed = True
                else: st.sidebar.error("Please enter a new ticker symbol.")
            else: ticker_to_use = selected_ticker_option; validation_needed = False
            if ticker_to_use: ticker_determined = True

        if ticker_determined and validation_needed:
            st.sidebar.info(f"Validating new ticker: {ticker_to_use}...")
            try:
                ticker_obj = yf.Ticker(ticker_to_use)
                if ticker_obj.info and ticker_obj.info.get('symbol'):
                    ticker_validated = True; st.sidebar.success(f"Ticker {ticker_to_use} appears valid.")
                else: st.sidebar.error(f"Invalid or unrecognized ticker: {ticker_to_use}.")
            except Exception as e: st.sidebar.error(f"Could not validate ticker {ticker_to_use}: {e}")
        elif ticker_determined:
            ticker_validated = True

        if basic_inputs_valid and ticker_determined and ticker_validated and action == 'Sell':
            participant_portfolio = portfolios.get(username, {})
            shares_owned = participant_portfolio.get('holdings', {}).get(ticker_to_use, {}).get('shares', 0)
            if shares > shares_owned:
                sell_action_valid = False; st.sidebar.error(f"Sell failed: You only own {shares_owned:,.0f} shares of {ticker_to_use}.")

        if basic_inputs_valid and ticker_determined and ticker_validated and sell_action_valid:
            new_trade_df = pd.DataFrame([{'participant': username, 'timestamp': datetime.now(timezone.utc), 'ticker': ticker_to_use, 'action': action, 'shares': shares, 'price': price}])
            try:
                save_trade(new_trade_df)
                st.sidebar.success(f"Trade recorded!")
                st.cache_data.clear()
                st.rerun()
            except Exception as e: st.sidebar.error(f"Error saving trade: {e}")

    # --- Main Page Content ---
    st.title(f"📈 Penny Stock Trading Competition - Welcome {name}! 🏆")
    st.markdown("---")

    if not isinstance(portfolios, dict):
        st.error("Portfolio data is unavailable.")
    else:
        # --- NEW: View Selection and Refresh Button in Columns ---
        col1, col2 = st.columns([3, 1]) # Give more space to the selectbox

        with col1:
            view_options = ["My Dashboard", "Leaderboard"]
            if st.session_state.get('is_admin'):
                view_options.append("Admin Panel")
            view_option = st.selectbox(
                "Select View:",
                view_options,
                label_visibility="collapsed",
                key='view_select_main'
            )

        with col2:
            if st.button("🔄 Refresh Live Prices", use_container_width=True):
                st.cache_data.clear()
                st.toast("Prices and portfolios refreshed!", icon="✅")
                # A rerun is implicitly triggered by the button click
        # --------------------------------------------------------

        st.markdown("---")

        if view_option == "My Dashboard":
            participant_data = portfolios.get(username)
            st.header(f"📊 {name}'s Dashboard")
            if participant_data:
                display_portfolio(participant_data)
                st.divider()
                st.subheader(f"My Trade History")
                user_trades_df = participant_data.get('trades')
                if user_trades_df is not None and not user_trades_df.empty and 'id' in user_trades_df.columns:
                    for index, trade in user_trades_df.sort_values(by='timestamp', ascending=False).iterrows():
                        trade_id = trade['id']
                        with st.container():
                            cols = st.columns([2, 1, 1, 1, 1, 1])
                            cols[0].write(trade['timestamp'].strftime('%Y-%m-%d %H:%M:%S') if pd.notnull(trade['timestamp']) else 'N/A')
                            cols[1].write(trade['ticker'])
                            cols[2].write(trade['action'])
                            cols[3].write(f"{trade['shares']:,.0f}")
                            cols[4].write(f"{trade['price']:,.3f}")
                            if cols[5].button("🗑️", key=f"delete_trade_{trade_id}", help=f"Delete Trade ID {trade_id}"):
                                if delete_trade(trade_id, username):
                                    st.success(f"Trade ID {trade_id} deleted.")
                                    st.cache_data.clear()
                                    st.rerun()
                                else:
                                    st.error(f"Failed to delete trade ID {trade_id}.")
                else:
                    st.info("You haven't recorded any trades yet.")
            else:
                 st.info("👋 Welcome! Enter your first trade to get started.")

        elif view_option == "Leaderboard":
            leaderboard_table_data = []
            initial_capital = 500.0
            for p_name, p_data in portfolios.items():
                if isinstance(p_data, dict) and 'total_value' in p_data:
                    total_value = p_data.get('total_value', initial_capital)
                    performance = ((total_value - initial_capital) / initial_capital) * 100 if initial_capital > 0 else 0
                    leaderboard_table_data.append({'Participant': p_data.get('participant', p_name), 'Performance (%)': performance, 'Total Value ($)': total_value})
            display_leaderboard(leaderboard_table_data, portfolios)

        elif view_option == "Admin Panel":
            if not st.session_state.get('is_admin'): st.error("⛔ Access Denied."); st.stop()
            st.header("👑 Admin Panel")
            st.subheader("User Management")
            try:
                all_users_data = get_all_users()
                if all_users_data:
                    users_df = pd.DataFrame(all_users_data)
                    display_cols = {'user_id': 'ID', 'username': 'Username', 'name': 'Name', 'email': 'Email', 'registration_date': 'Registered', 'is_admin': 'Admin?'}
                    users_df_display = users_df[list(display_cols.keys())].rename(columns=display_cols)
                    users_df_display['Admin?'] = users_df_display['Admin?'].apply(lambda x: 'Yes' if x == 1 else 'No')
                    st.dataframe(users_df_display, hide_index=True, use_container_width=True)
                    st.markdown("---")
                    col1, col2 = st.columns(2)
                    with col1:
                        st.subheader("Delete User")
                        usernames_list_del = [""] + sorted([user['username'] for user in all_users_data if user['username'] != username])
                        user_to_delete = st.selectbox("Select user to delete:", usernames_list_del, key="delete_user_select")
                        if user_to_delete and st.button(f"⚠️ Delete User '{user_to_delete}'", type="primary"):
                            if delete_user(user_to_delete):
                                st.success(f"User '{user_to_delete}' deleted."); st.cache_data.clear(); st.rerun()
                            else: st.error(f"Failed to delete '{user_to_delete}'.")
                    with col2:
                        st.subheader("Reset User Password")
                        usernames_list_reset = [""] + sorted([user['username'] for user in all_users_data])
                        user_to_reset = st.selectbox("Select user to reset:", usernames_list_reset, key="reset_user_select")
                        if user_to_reset:
                            generic_password = "password123"
                            if st.button(f"🔑 Reset password for '{user_to_reset}'"):
                                if update_user_password(user_to_reset, generic_password):
                                    st.success(f"Password for '{user_to_reset}' reset to: `{generic_password}`")
                                else: st.error(f"Failed to reset password for '{user_to_reset}'.")
                else: st.info("No users found.")
            except Exception as e: st.error(f"Error loading users: {e}")

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
            reg_name = st.text_input("Full Name", key="reg_name_unique")
            reg_email = st.text_input("Email Address", key="reg_email_unique")
            reg_username = st.text_input("Desired Username", key="reg_username_unique")
            reg_password = st.text_input("Password", type="password", key="reg_password_unique")
            reg_password_confirm = st.text_input("Confirm Password", type="password", key="reg_password_confirm_unique")
            if st.form_submit_button("Register Account"):
                if not all([reg_name, reg_email, reg_username, reg_password, reg_password_confirm]): st.warning("Please fill all fields.")
                elif reg_password != reg_password_confirm: st.error("Passwords do not match.")
                elif "@" not in reg_email or "." not in reg_email.split('@')[-1]: st.error("Please enter a valid email.")
                else:
                    try:
                        if get_user_by_username(reg_username): st.error(f"Username '{reg_username}' is taken.")
                        elif get_user_by_email(reg_email): st.error(f"Email '{reg_email}' is registered.")
                        else:
                            success, message = add_user(reg_username, reg_name, reg_email, reg_password)
                            if success: st.success(message); st.info("Registration successful! Proceed to the Login tab.")
                            else: st.error(message)
                    except Exception as e: st.error(f"Database error: {e}")
