# app.py
import streamlit as st
import pandas as pd
import os
import yfinance as yf
from datetime import datetime
import yaml
from yaml.loader import SafeLoader
import streamlit_authenticator as stauth
import os
# Removed: import extra_streamlit_components as stx # No longer explicitly used here

# Import from project modules
from data_handler import load_data, save_trade, delete_trade, admin_delete_trade # Assuming DATABASE_FILE is handled internally
from auth_handler import (
    get_all_users,
    add_user,
    get_user_by_username,
    get_user_by_email,
    delete_user,
    # check_password, # Not directly needed by stauth if using the dict
)
from portfolio import calculate_portfolio
from display import display_portfolio, display_leaderboard # Make sure display.py has these

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
credentials_dict = {"usernames": {}} # Initialize empty
try:
    db_users = get_all_users() # Fetch users from auth_handler
    if db_users:
        for user in db_users:
            # Check for essential keys fetched from the database
            if all(k in user for k in ['username', 'name', 'email', 'hashed_password']):
                 credentials_dict["usernames"][user['username']] = {
                     "email": user['email'],
                     "name": user['name'],
                     "password": user['hashed_password'] # Pass the ALREADY HASHED password from DB
                 }
            else:
                 # Log a warning if a user record from DB is incomplete
                 st.warning(f"Skipping database user due to incomplete data: {user.get('username', 'N/A')}")
                 print(f"Warning: Skipping database user due to incomplete data - {user}") # Also print to console
    else:
         # This case means the users table is empty
         st.info("No users found in the database. Please register the first user.")
         # Consider adding logic here for first-time setup if needed,
         # e.g., creating a default admin, but requires careful handling.

except Exception as e:
    # Handle errors during database fetching
    st.error(f"Critical Error: Failed to load user credentials from database: {e}")
    st.exception(e) # Show detailed error in console/logs
    # Fallback to empty credentials, preventing login but allowing registration attempt
    credentials_dict = {"usernames": {}}

# --- Initialize Authenticator Using st.secrets for Cookie Config ---
# Define authenticator variable outside try/except so it's always in scope
authenticator = None
try:
     # Read cookie config from Environment Variables
    cookie_name = os.environ.get("COOKIE_NAME", "pennystockcookie") # Provide a default name
    cookie_key = os.environ.get("COOKIE_KEY") # MUST be set via platform's Environment Variables
    cookie_expiry_str = os.environ.get("COOKIE_EXPIRY_DAYS", "30") # Read as string, default 30

    # Validate required environment variables
    if not cookie_key:
        st.error("CRITICAL: COOKIE_KEY environment variable not set!")
        # Optionally raise an error or st.stop() in production
        # For now, we'll let Authenticate handle a None key potentially
        # raise ValueError("COOKIE_KEY environment variable is missing!")
        st.stop() # Stop the app if the key is missing in deployed env

    try:
        cookie_expiry = int(cookie_expiry_str)
    except ValueError:
        st.warning(f"Invalid COOKIE_EXPIRY_DAYS value. Using default 30 days.")
        cookie_expiry = 30

    # *** Single Authenticator Instantiation ***
    authenticator = stauth.Authenticate(
        credentials_dict, # Credentials from DB
        cookie_name,      # Cookie settings from st.secrets
        cookie_key,       # Cookie settings from st.secrets
        cookie_expiry     # Cookie settings from st.secrets
    )

except KeyError as e:
    # Handle missing secrets gracefully
    st.error(f"Missing cookie configuration in Streamlit Secrets ([cookie] section in .streamlit/secrets.toml): {e}")
    st.error("Please ensure secrets are set locally or in deployment settings.")
    st.stop() # Stop the app if secrets aren't configured
except Exception as e:
     st.error(f"Error initializing authenticator with secrets: {e}")
     st.exception(e)
     st.stop()

# --- Authentication Check and App Logic ---

# Ensure authenticator was successfully created before proceeding
if authenticator is None:
    st.error("Authenticator could not be initialized. App cannot proceed.")
    st.stop()

# Check authentication status from session state
if st.session_state.get("authentication_status"):
    st.cache_data.clear()
    print("--- Cleared st.cache_data for debugging price fetch ---")
    # --- User is Logged In ---
    name = st.session_state.get("name")
    username = st.session_state.get("username")

    # --- Add Logging ---
    # print(f"--- [DEBUG] Attempting get_user_by_username for: '{username}' ---")
    # current_user_data = get_user_by_username(username) # Call to auth_handler
    # print(f"--- [DEBUG] Result from get_user_by_username: {current_user_data} ---")
    # --- End Logging ---

     # --- ADD: Store Admin Status in Session State ---
    # Fetch full user data including is_admin (might already be in credentials_dict, but safer to fetch fresh)
    # This assumes login was successful, so user exists.
    current_user_data = get_user_by_username(username)
    if current_user_data:
        st.session_state.is_admin = (current_user_data.get('is_admin', 0) == 1)
    else:
        # Should not happen if login succeeded, but handle defensively
        st.session_state.is_admin = False
        st.error("Could not verify user admin status.")
    # ---------------------------------------------

    st.sidebar.write(f'Welcome *{name}* ({username})') # Display username too for clarity
    authenticator.logout('Logout', 'sidebar', key='logout_button') # Use the single authenticator instance

    # --- Load trade data and calculate portfolios ---
    # Moved inside authenticated block to ensure fresh data potentially
    try:
        trades = load_data()
        if not trades.empty:
            # Ensure the 'id' column exists after loading (critical check)
            if 'id' not in trades.columns:
                 st.error("Critical Error: Trade 'id' column missing from loaded data. Portfolio calculation aborted.")
                 portfolios = {} # Prevent calculation
            else:
                 # Calculate portfolio data - consider caching carefully if performance is an issue
                 # For now, direct calculation ensures data freshness after trades/deletes
                 portfolios = calculate_portfolio(trades.copy()) # Pass a copy
        else:
            # No trades exist yet
            trades = pd.DataFrame(columns=['id', 'participant', 'timestamp', 'ticker', 'action', 'shares', 'price'])
            portfolios = {}
    except Exception as e:
        st.error(f"An critical error occurred loading trade data: {e}")
        st.exception(e)
        # Fallback to empty data structures on error
        trades = pd.DataFrame(columns=['id', 'participant', 'timestamp', 'ticker', 'action', 'shares', 'price'])
        portfolios = {}


    # --- Load existing tickers for dropdown ---
    if not trades.empty and 'ticker' in trades.columns:
        # Get unique, non-null tickers and sort them
        existing_tickers = sorted([str(t) for t in trades['ticker'].dropna().unique()])
    else:
        existing_tickers = []
    # Add the option to enter a new ticker
    ticker_options = ["-- Enter New Ticker --"] + existing_tickers


    # --- Sidebar for Trade Entry ---
    st.sidebar.header(f"Enter New Trade") # Simplified header

    # Use unique keys for sidebar widgets to prevent state conflicts
    selected_ticker_option = st.sidebar.selectbox(
        "Ticker Symbol:",
        ticker_options,
        index=0,
        key='ticker_select_sidebar'
        )
    new_ticker_input = ""
    # Show text input only if 'Enter New Ticker' is selected
    if selected_ticker_option == "-- Enter New Ticker --":
        new_ticker_input = st.sidebar.text_input(
            "Enter New Ticker Symbol:",
            placeholder="e.g., GME",
            key='new_ticker_sidebar'
            ).upper().strip()

    action = st.sidebar.selectbox(
        "Action:",
        ["Buy", "Sell"],
        key='action_select_sidebar'
        )
    shares = st.sidebar.number_input(
        "Number of Shares:",
        min_value=1,
        step=1,
        key='shares_input_sidebar'
        )
    price = st.sidebar.number_input(
        "Price per Share:",
        min_value=0.001,
        step=0.001,
        format="%.3f",
        key='price_input_sidebar'
        )
    trade_button = st.sidebar.button(
        "Record Trade",
        type="primary",
        key='trade_button_sidebar'
        )

    # --- Process Trade Button Click ---
    if trade_button:
        # Initialize validation flags
        basic_inputs_valid = False
        ticker_determined = False
        ticker_validated = False
        sell_action_valid = True # Assume valid unless proven otherwise

        ticker_to_use = ""
        participant_name_cleaned = username # Use the logged-in username

        # 1. Check Logged-in User (redundant check, already passed auth)
        if not participant_name_cleaned:
             st.sidebar.error("CRITICAL ERROR: User context lost.")
        # 2. Basic Input Checks
        elif shares <= 0: st.sidebar.error("Shares must be a positive number.")
        elif price <= 0: st.sidebar.error("Price must be a positive number.")
        else: basic_inputs_valid = True

        # 3. Determine Ticker to Use
        if basic_inputs_valid:
            validation_needed = False
            if selected_ticker_option == "-- Enter New Ticker --":
                if new_ticker_input:
                    ticker_to_use = new_ticker_input
                    validation_needed = True # New ticker needs validation
                else: st.sidebar.error("Please enter a new ticker symbol.")
            else:
                ticker_to_use = selected_ticker_option
                validation_needed = False # Existing ticker assumed valid
            # Set flag if a ticker was successfully determined
            if ticker_to_use: ticker_determined = True

        # 4. Validate Ticker via yfinance (if it's a new ticker)
        if ticker_determined:
            if not validation_needed:
                ticker_validated = True # Skip validation for existing tickers
            else:
                # Perform yfinance validation
                # st.sidebar.info(f"Validating new ticker: {ticker_to_use}...")
                # try:
                #     ticker_obj = yf.Ticker(ticker_to_use)
                #     ticker_info = ticker_obj.info
                #     # Check if info is usable or fallback to history check
                #     # Added check for empty info dict
                #     if isinstance(ticker_info, dict) and ticker_info and ticker_info.get('symbol', '').upper() == ticker_to_use:
                #         st.sidebar.success(f"Ticker {ticker_to_use} appears valid.")
                #         ticker_validated = True
                #     # If info is empty or symbol doesn't match, try history
                #     elif not ticker_info or ticker_info.get('symbol', '').upper() != ticker_to_use:
                #          st.sidebar.warning(f"Ticker info limited for {ticker_to_use}. Checking history...")
                #          hist = ticker_obj.history(period="5d", interval="1d", raise_errors=False) # Check last 5 days
                #          if not hist.empty and not hist.isnull().all().all(): # Check if history has actual data
                #               st.sidebar.success(f"Ticker {ticker_to_use} history found. Proceeding.")
                #               ticker_validated = True
                #          else:
                #               st.sidebar.error(f"Invalid or unrecognized ticker: {ticker_to_use}. No valid info or recent history found.")
                #     else: # Should not happen if above conditions are met, but as fallback
                #          st.sidebar.error(f"Ticker data inconsistency for symbol: {ticker_to_use}")
                # except Exception as e:
                #     st.sidebar.error(f"Could not validate ticker {ticker_to_use}: {e}")
                #     print(f"yfinance validation error for {ticker_to_use}: {e}") # Log detailed error
                ticker_validated = True # Force validation to pass temporarily

        # 5. Validate Sell Action (check holdings)
        if basic_inputs_valid and ticker_determined and ticker_validated and action == 'Sell':
            # Ensure portfolios is calculated and available
            if 'portfolios' in locals() and isinstance(portfolios, dict):
                participant_portfolio = portfolios.get(participant_name_cleaned)
                # Check if user has portfolio data and holdings
                if participant_portfolio and isinstance(participant_portfolio.get('holdings'), dict):
                    current_holdings = participant_portfolio.get('holdings', {})
                    shares_owned = current_holdings.get(ticker_to_use, {}).get('shares', 0)
                    if shares > shares_owned:
                        st.sidebar.error(f"Sell failed: You only own {shares_owned:,.0f} shares of {ticker_to_use}.")
                        sell_action_valid = False
                    # If shares_owned is 0 or ticker not held, sell_action_valid remains True but logic below handles it implicitly? No, should fail.
                    elif shares_owned <= 0:
                         st.sidebar.error(f"Sell failed: You do not own any shares of {ticker_to_use}.")
                         sell_action_valid = False

                else: # User might exist but have no trades/holdings yet
                    st.sidebar.error(f"Sell failed: You do not own any shares of {ticker_to_use}.")
                    sell_action_valid = False
            else:
                st.sidebar.error("Error checking sell validity: Portfolio data unavailable.")
                sell_action_valid = False # Cannot validate sell if portfolio missing

        # 6. Save Trade (if ALL checks passed)
        if basic_inputs_valid and ticker_determined and ticker_validated and sell_action_valid:
            timestamp = datetime.now() # Record timestamp at time of saving
            # Create DataFrame for the new trade
            new_trade_df = pd.DataFrame([{
                'participant': participant_name_cleaned,
                'timestamp': timestamp,
                'ticker': ticker_to_use,
                'action': action,
                'shares': shares,
                'price': price
                # 'id' is handled by the database AUTOINCREMENT
            }])
            try:
                # Call function from data_handler to save the trade
                save_trade(new_trade_df)
                st.sidebar.success(f"Trade recorded: {action} {shares} {ticker_to_use} @ ${price:.3f}")
                st.cache_data.clear()
                # Rerun the app to reload data and update portfolio display
                st.rerun()
            except Exception as e:
                st.sidebar.error(f"Error saving trade to database: {e}")
                print(f"Database save error: {e}") # Log detailed error


    # --- Main Page Content (Authenticated User) ---
    st.title(f"📈 Penny Stock Trading Competition - Welcome {name}! 🏆")
    st.markdown("---")

    # Check if portfolio calculation succeeded before displaying
    if 'portfolios' not in locals():
        st.error("Portfolio data is unavailable due to earlier errors.")
    elif not portfolios and not trades.empty:
         # Trades exist but calculation failed - maybe bad data?
         st.warning("Portfolio data could not be calculated from existing trades. Please check data integrity or contact admin.")
    elif not portfolios and trades.empty:
         # User logged in, no trades yet
         st.info("👋 Your portfolio is empty. Enter your first trade using the sidebar to get started!")
    else:
        # --- Display Portfolio or Leaderboard ---
        # Get list of participants who have portfolio data
        participants = sorted([p for p in portfolios.keys() if isinstance(p, str)])
        view_options = ["My Dashboard", "Leaderboard"]
        if st.session_state.get('is_admin'):
            view_options.append("Admin Panel")
        default_view_index = 0

        # Selectbox for view choice
        view_option = st.selectbox(
            "Select View:",
            view_options,
            index=default_view_index,
            label_visibility="collapsed", # Hide label, use title/header instead
            key='view_select_main'
            )
        # --- DEBUG PRINT ADDED ---
        # print(f"--- [DEBUG APP] Value of view_option AFTER selectbox: '{view_option}' ---")
        # --- END DEBUG PRINT ---
        st.markdown("---") # Visual separator

        # --- Display Selected View ---
        if view_option == "Leaderboard":
            # --- DEBUG PRINT ADDED ---
            # print("--- [DEBUG VIEW] Entering Leaderboard ---")
            # --- END DEBUG PRINT ---
            leaderboard_table_data = []
            initial_capital = 500.0 # Use float for consistency
            # Filter for valid portfolio entries before processing
            valid_portfolios_for_leaderboard = {
                k: v for k, v in portfolios.items()
                if k in participants and isinstance(v, dict) and 'total_value' in v
                }

            for p_name, p_data in valid_portfolios_for_leaderboard.items():
                 total_value = p_data.get('total_value', initial_capital)
                 # Ensure total_value is numeric for calculation
                 if isinstance(total_value, (int, float)):
                      performance = ((total_value - initial_capital) / initial_capital) * 100 if initial_capital > 0 else 0
                 else:
                      performance = 0 # Assign 0 performance if value is invalid
                      total_value = initial_capital # Fallback value for display

                 leaderboard_table_data.append({
                     'Participant': p_data.get('participant', p_name), # Use name from data
                     'Performance (%)': performance,
                     'Total Value ($)': total_value
                  })
            # Call display function from display.py
            display_leaderboard(leaderboard_table_data, valid_portfolios_for_leaderboard)

        elif view_option == "My Dashboard":
             # --- DEBUG PRINT ADDED ---
             # print("--- [DEBUG VIEW] Entering My Dashboard ---")
             # --- END DEBUG PRINT ---
             # Get portfolio data for the currently logged-in user
             participant_data = portfolios.get(username)
             if participant_data:
                 st.header(f"📊 {name}'s Dashboard ({username})")
                 # Call display function from display.py
                 display_portfolio(participant_data)
                 st.divider() # Separator before trade history

                 # --- Trade History with Delete Button ---
                 st.subheader(f"My Trade History")
                 # Extract user's trades from their portfolio data
                 user_trades_df = participant_data.get('trades')

                 # Check if trades exist and have the 'id' column
                 if user_trades_df is not None and not user_trades_df.empty and 'id' in user_trades_df.columns:
                     # Clean data: remove trades with missing IDs and convert ID to int
                     user_trades_df = user_trades_df.dropna(subset=['id'])
                     if not user_trades_df.empty: # Check again after dropna
                         user_trades_df['id'] = user_trades_df['id'].astype(int)

                         # Display Headers using columns for alignment
                         h_cols = st.columns([2, 1, 1, 1, 1, 1]) # Adjust ratios as needed
                         h_cols[0].write("**Timestamp**"); h_cols[1].write("**Ticker**"); h_cols[2].write("**Action**")
                         h_cols[3].write("**Shares**"); h_cols[4].write("**Price ($)**"); h_cols[5].write("**Manage**")
                         st.divider() # Horizontal line below headers

                         # Iterate through trades (sorted newest first) and display rows
                         for index, trade in user_trades_df.sort_values(by='timestamp', ascending=False).iterrows():
                             trade_id = trade['id']
                             # Define unique keys for widgets inside the loop
                             confirm_key = f"confirm_delete_{trade_id}"
                             cancel_key = f"cancel_delete_{trade_id}"
                             delete_key = f"delete_{trade_id}"

                             # Use st.container to group elements of a single trade row
                             with st.container():
                                 cols = st.columns([2, 1, 1, 1, 1, 1]) # Match header columns
                                 # Display trade details, handling potential NaT timestamps
                                 cols[0].write(trade['timestamp'].strftime('%Y-%m-%d %H:%M:%S') if pd.notnull(trade['timestamp']) else 'N/A')
                                 cols[1].write(trade['ticker']); cols[2].write(trade['action'])
                                 cols[3].write(f"{trade['shares']:,.0f}"); cols[4].write(f"{trade['price']:,.3f}")

                                 # Placeholder for delete button/confirmation widgets
                                 confirm_placeholder = cols[5].empty()

                                 # Confirmation Logic: Show confirm/cancel if delete was clicked
                                 if st.session_state.get(f"confirming_delete_{trade_id}"):
                                     confirm_placeholder.warning(f"Delete {trade['ticker']}?", icon="⚠️")
                                     btn_cols = confirm_placeholder.columns(2) # Buttons side-by-side
                                     # Confirm Button
                                     if btn_cols[0].button("Confirm", key=confirm_key, type="primary"):
                                         deleted = delete_trade(trade_id, username) # Call delete function
                                         # Clean up confirmation state BEFORE rerun
                                         if f"confirming_delete_{trade_id}" in st.session_state:
                                             del st.session_state[f"confirming_delete_{trade_id}"]
                                         # Display result and rerun
                                         if deleted:
                                             st.success(f"Trade ID {trade_id} deleted.")
                                             st.cache_data.clear() # Clear cache only if delete succeeded
                                         else: st.error(f"Failed to delete trade ID {trade_id}.")
                                         st.rerun() # Rerun to reflect deletion
                                     # Cancel Button
                                     if btn_cols[1].button("Cancel", key=cancel_key):
                                         # Just remove confirmation state and rerun
                                         if f"confirming_delete_{trade_id}" in st.session_state:
                                             del st.session_state[f"confirming_delete_{trade_id}"]
                                         st.rerun()
                                 else:
                                     # Initial State: Show Delete button
                                     if confirm_placeholder.button("🗑️", key=delete_key, help=f"Delete Trade ID {trade_id}"):
                                         # Set state to trigger confirmation on next rerun
                                         st.session_state[f"confirming_delete_{trade_id}"] = True
                                         st.rerun()

                         st.divider() # Divider after the last trade row
                     else:
                        # Handles case where dropna might have removed all trades
                        st.info("No trades with valid IDs found in your history.")

                 # --- THIS IS THE BLOCK THAT SHOWS THE ERROR MESSAGE ---
                 else:
                    # Handles case where user_trades_df is None, empty, or missing 'id' column initially
                    # This condition triggers the error message you were seeing
                    st.error(f"An unexpected error occurred loading dashboard data for {name}.")
                    print(f"--- DEBUG: user_trades_df check failed for {name}. Value: {user_trades_df} ---") # Added more debug info here
                    # You might also check if user_trades_df is a DataFrame but empty: print(f"Is user_trades_df empty? {user_trades_df.empty if isinstance(user_trades_df, pd.DataFrame) else 'Not DataFrame'}")
                    # And check for 'id' column: print(f"Does user_trades_df have 'id'? {'id' in user_trades_df.columns if isinstance(user_trades_df, pd.DataFrame) else 'Not DataFrame'}")

                    # The original code had st.info here, but the error message suggests it reaches the st.error instead.
                    # st.info("You haven't recorded any trades yet.")

             # --- Handling if participant_data itself is missing for logged-in user ---
             else:
                 # This might happen if calculate_portfolio failed entirely or user has no trades AT ALL.
                 if username not in portfolios and ('trades' in locals() and not trades[trades['participant'] == username].empty):
                     # Trades exist but portfolio calculation failed for this user
                      st.warning(f"Could not calculate portfolio data for {name}. Check trade data or contact admin.")
                 elif username not in portfolios:
                     # No trades recorded yet for this user
                     st.info(f"Welcome {name}! Your dashboard is ready. Enter your first trade.")
                 else: # Should not be reachable if portfolios exists but key is missing, but as failsafe
                      st.error(f"An unexpected error occurred loading dashboard data for {name}.")


        elif view_option == "Admin Panel":
            # --- DEBUG PRINT ADDED ---
            # print("--- [DEBUG VIEW] Entering Admin Panel ---")
            # --- END DEBUG PRINT ---
            # --- Security Check ---
            if not st.session_state.get('is_admin'):
                 st.error("⛔ Access Denied. Administrator privileges required.")
                 st.stop() # Stop execution for non-admins trying to access

            st.header("👑 Admin Panel")
            st.subheader("User Management")

            # --- DEBUG PRINT ADDED ---
            # print("--- [DEBUG ADMIN] Attempting to load user data for admin panel ---")
            # --- END DEBUG PRINT ---

            try:
                all_users = get_all_users() # Fetch all users including admin status
                if not all_users:
                    st.info("No users found in the database.")
                else:
                    # Prepare data for display (optional: format dates, boolean)
                    users_df = pd.DataFrame(all_users)
                    # Select and potentially rename columns for display
                    display_cols = {
                        'user_id': 'ID',
                        'username': 'Username',
                        'name': 'Name',
                        'email': 'Email',
                        'registration_date': 'Registered On',
                        'is_admin': 'Is Admin?'
                    }
                    users_df_display = users_df[list(display_cols.keys())].rename(columns=display_cols)
                    # Optional: Format 'Registered On' if needed
                    # users_df_display['Registered On'] = pd.to_datetime(users_df_display['Registered On']).dt.strftime('%Y-%m-%d')

                    st.info(f"Total users: {len(users_df_display)}")
                    st.dataframe(users_df_display, hide_index=True, use_container_width=True)

                    st.subheader("Delete User")
                    usernames_list = [""] + sorted([user['username'] for user in all_users if user['username'] != username]) # Exclude self
                    user_to_delete = st.selectbox("Select user to delete:", usernames_list, index=0, key="delete_user_select")

                    if user_to_delete:
                         # Add a confirmation step
                         if st.button(f"⚠️ Delete User '{user_to_delete}'", key=f"confirm_delete_btn_{user_to_delete}", type="primary"):

                             # Double confirmation (optional but recommended for destructive actions)
                             confirm_key = f"confirm_delete_{user_to_delete}"
                             if confirm_key not in st.session_state:
                                  st.session_state[confirm_key] = True
                                  st.rerun() # Rerun to show the final confirmation

                         # Show final confirmation if flag is set
                         if st.session_state.get(f"confirm_delete_{user_to_delete}"):
                              st.warning(f"**Are you sure you want to permanently delete user '{user_to_delete}'?** This cannot be undone.", icon="🚨")
                              col_confirm, col_cancel = st.columns(2)
                              if col_confirm.button("Yes, Delete Permanently", key=f"final_delete_{user_to_delete}", type="primary"):
                                  deleted = delete_user(user_to_delete) # Call delete function
                                  # Clean up confirmation state
                                  del st.session_state[f"confirm_delete_{user_to_delete}"]
                                  if deleted:
                                       st.success(f"User '{user_to_delete}' deleted successfully.")
                                       # Clear cache? Might not be strictly needed here unless user list is cached heavily upstream
                                       # st.cache_data.clear() # Consider if needed
                                  else:
                                       st.error(f"Failed to delete user '{user_to_delete}'. Check logs.")
                                  st.rerun() # Rerun to refresh user list

                              if col_cancel.button("Cancel", key=f"cancel_delete_{user_to_delete}"):
                                  # Clean up state and rerun
                                  del st.session_state[f"confirm_delete_{user_to_delete}"]
                                  st.rerun()

            except Exception as e:
                 st.error(f"Error loading or managing users: {e}")
                 st.exception(e)
                 # --- DEBUG PRINT ADDED ---
                 # print("--- [DEBUG ADMIN] Finished Admin Panel try-except block ---")
                 # --- END DEBUG PRINT ---

             # --- All Trade History Section (NEW) ---
            st.subheader("All Trade History Management")

            try:
                # Load ALL trades using the existing function
                all_trades_df = load_data()

                if all_trades_df is None or all_trades_df.empty:
                    st.info("No trades found in the system.")
                elif 'id' not in all_trades_df.columns:
                    st.error("Critical Error: Trade 'id' column missing from loaded data for Admin Panel.")
                else:
                    # Clean data: ensure 'id' is usable
                    all_trades_df = all_trades_df.dropna(subset=['id'])
                    if all_trades_df.empty:
                        st.info("No trades with valid IDs found.")
                    else:
                        all_trades_df['id'] = all_trades_df['id'].astype(int)

                        # Prepare for display
                        # Define columns to show, including participant
                        display_cols_order = ['id', 'participant', 'timestamp', 'ticker', 'action', 'shares', 'price']
                        # Filter DataFrame to only include these columns in the desired order
                        trades_to_display = all_trades_df[display_cols_order].copy()

                        st.info(f"Total trades found: {len(trades_to_display)}")

                        # Display Headers
                        h_cols = st.columns([0.5, 1, 2, 1, 1, 1, 1, 1]) # Adjust ratios as needed (add participant)
                        h_cols[0].write("**ID**"); h_cols[1].write("**Participant**"); h_cols[2].write("**Timestamp**")
                        h_cols[3].write("**Ticker**"); h_cols[4].write("**Action**"); h_cols[5].write("**Shares**")
                        h_cols[6].write("**Price ($)**"); h_cols[7].write("**Manage**")
                        st.divider()

                        # Iterate and display rows with delete buttons
                        for index, trade in trades_to_display.sort_values(by='timestamp', ascending=False).iterrows():
                            trade_id = trade['id']
                            participant_name = trade['participant'] # Get participant for display/keys

                            # Use unique keys for admin delete widgets
                            admin_confirm_key = f"admin_confirm_delete_{trade_id}"
                            admin_cancel_key = f"admin_cancel_delete_{trade_id}"
                            admin_delete_key = f"admin_delete_{trade_id}"

                            with st.container():
                                cols = st.columns([0.5, 1, 2, 1, 1, 1, 1, 1]) # Match header columns
                                cols[0].write(str(trade_id))
                                cols[1].write(participant_name)
                                cols[2].write(trade['timestamp'].strftime('%Y-%m-%d %H:%M:%S') if pd.notnull(trade['timestamp']) else 'N/A')
                                cols[3].write(trade['ticker']); cols[4].write(trade['action'])
                                cols[5].write(f"{trade['shares']:,.0f}"); cols[6].write(f"{trade['price']:,.3f}")

                                admin_confirm_placeholder = cols[7].empty()

                                # Admin Confirmation Logic
                                if st.session_state.get(f"admin_confirming_delete_{trade_id}"):
                                    admin_confirm_placeholder.warning(f"Delete Trade {trade_id} ({trade['ticker']}) for {participant_name}?", icon="⚠️")
                                    btn_cols = admin_confirm_placeholder.columns(2)
                                    # Confirm Button - Calls admin_delete_trade
                                    if btn_cols[0].button("Confirm", key=admin_confirm_key, type="primary"):
                                        deleted = admin_delete_trade(trade_id) # Use the new admin function
                                        if f"admin_confirming_delete_{trade_id}" in st.session_state:
                                             del st.session_state[f"admin_confirming_delete_{trade_id}"]
                                        if deleted:
                                             st.success(f"Trade ID {trade_id} deleted by admin.")
                                             st.cache_data.clear() # Clear data cache
                                        else:
                                             st.error(f"Failed to delete trade ID {trade_id}.")
                                        st.rerun()
                                    # Cancel Button
                                    if btn_cols[1].button("Cancel", key=admin_cancel_key):
                                        if f"admin_confirming_delete_{trade_id}" in st.session_state:
                                             del st.session_state[f"admin_confirming_delete_{trade_id}"]
                                        st.rerun()
                                else:
                                    # Initial State: Show Delete button
                                    if admin_confirm_placeholder.button("🗑️", key=admin_delete_key, help=f"Admin Delete Trade ID {trade_id} for {participant_name}"):
                                        st.session_state[f"admin_confirming_delete_{trade_id}"] = True
                                        st.rerun()
                        st.divider()

            except Exception as e:
                st.error(f"An error occurred displaying trade history: {e}")
                st.exception(e)

        # --- End of Admin Panel View ---

# --- User NOT Logged In ---
else:
    # Display Login and Registration options using tabs
    st.title("📈 Penny Stock Trading Competition")
    st.markdown("Please log in or register to participate.")
    st.divider()

    login_tab, register_tab = st.tabs(["Login", "Register"])

    # --- Login Tab ---
    with login_tab:
        st.subheader("Member Login")


        # Check if the credentials dictionary actually contains any users
        if not credentials_dict["usernames"]:
            # If no users exist in the database, prompt registration
            st.warning("No users found in the database. Please use the 'Register' tab to create the first account.")
        else:

            # Only call authenticator.login if users exist and authenticator is initialized
            if authenticator:
                authenticator.login(location='main') # Authenticator uses the credentials_dict

                # Display feedback based on login attempt status
                if st.session_state.get("authentication_status") == False:
                    st.error('Username/password is incorrect. Please try again.')
                elif st.session_state.get("authentication_status") is None:
                     # Initial state or after logout
                     st.info('Please enter your username and password.')
            else:
                # This case should ideally not be reached if the initial authenticator check passes
                st.error("Login is unavailable because the authenticator failed to initialize.")


    # --- Registration Tab ---
    with register_tab:
        st.subheader("Create New Account")
        # Manual Registration Form (replaces authenticator.register_user)
        with st.form("Registration_Form", clear_on_submit=False): # Keep values on failure
            reg_name = st.text_input("Full Name", key="reg_form_name")
            reg_email = st.text_input("Email Address", key="reg_form_email")
            reg_username = st.text_input("Desired Username", key="reg_form_username")
            reg_password = st.text_input("Password", type="password", key="reg_form_password")
            reg_password_confirm = st.text_input("Confirm Password", type="password", key="reg_form_password_confirm")

            # Submit button for the form
            submitted = st.form_submit_button("Register Account")

            if submitted:
                # --- Form Validation Logic ---
                if not all([reg_name, reg_email, reg_username, reg_password, reg_password_confirm]):
                    st.warning("Please fill in all registration fields.")
                elif reg_password != reg_password_confirm:
                    st.error("Passwords do not match. Please re-enter.")
                # Optional: Add email format validation
                elif "@" not in reg_email or "." not in reg_email.split('@')[-1]:
                     st.error("Please enter a valid email address.")
                # Optional: Add username/password complexity rules if desired
                # elif len(reg_password) < 8:
                #     st.error("Password must be at least 8 characters long.")
                else:
                    # --- Check Database if username/email already exist ---
                    try:
                        existing_user_by_name = get_user_by_username(reg_username)
                        existing_user_by_email = get_user_by_email(reg_email)

                        if existing_user_by_name:
                            st.error(f"Username '{reg_username}' is already taken. Please choose another.")
                        elif existing_user_by_email:
                            st.error(f"Email '{reg_email}' is already registered. Please log in or use a different email.")
                        else:
                            # --- Attempt to Add User to Database ---
                            # Call the function from auth_handler
                            success, message = add_user(reg_username, reg_name, reg_email, reg_password)

                            if success:
                                st.success(message) # Show success message from add_user
                                st.info("Registration successful! Please switch to the Login tab and log in with your new credentials.")
                                # Form is not automatically cleared here unless clear_on_submit=True AND successful
                                # User needs to manually switch tab and log in.
                            else:
                                st.error(message) # Display specific error message from add_user
                    except Exception as db_check_error:
                         st.error(f"Database error during registration check: {db_check_error}")
                         print(f"DB Check Error: {db_check_error}")


# Footer or other elements outside authentication check can go here if needed
# st.markdown("---")
# st.caption("Penny Stock Challenge App")