import streamlit as st
import yfinance as yf
import pandas as pd
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart


@st.cache_data(ttl=300)

def get_current_price(ticker):
    """
    Fetches the current price for a ticker using yfinance.
    Tries multiple potential keys for the price.
    Returns float or None.
    """
    print(f"--- Attempting get_current_price for {ticker} ---")
    try:
        # Fetch data only once
        ticker_data = yf.Ticker(ticker)
        info = ticker_data.info

        if not info: # Handle cases where info dict is empty
             print(f"!!! Received empty info dict for {ticker}.")
             return None

        # Define potential keys for the current price, in order of preference
        price_keys_to_try = ['currentPrice', 'regularMarketPrice', 'marketPrice', 'open']
        # Add 'previousClose' as a last resort if needed:
        # price_keys_to_try = ['currentPrice', 'regularMarketPrice', 'marketPrice', 'open', 'previousClose']

        for key in price_keys_to_try:
            if key in info:
                price = info[key]
                # Check if price is a valid number (int/float) and positive
                # Use pd.isna to handle potential numpy NaN values safely
                if price is not None and not pd.isna(price) and isinstance(price, (int, float)) and price > 0:
                    print(f"+++ Successfully fetched price for {ticker} using key '{key}': {price}")
                    return float(price) # Return as float
                else:
                    # Log if key exists but value is invalid (None, NaN, zero, negative, wrong type)
                    print(f"--- Found key '{key}' for {ticker}, but value '{price}' is invalid or not positive.")

        # If loop finishes without finding a valid price
        print(f"!!! No valid/positive price found for {ticker} using keys: {price_keys_to_try}. Info keys available: {list(info.keys())}")
        return None

    except Exception as e:
        # Catch exceptions during yf.Ticker or .info access
        print(f"!!! EXCEPTION fetching info/price for {ticker}: {e}")
        return None
    
def send_password_reset_email(recipient_email: str, username: str, token: str):
    """Sends an email with the password reset token."""
    try:
        # Get email credentials from secrets
        smtp_user = st.secrets["email_credentials"]["username"]
        smtp_pass = st.secrets["email_credentials"]["password"]
        smtp_server = st.secrets["email_credentials"]["smtp_server"]
        smtp_port = st.secrets["email_credentials"]["smtp_port"]

        # Create the email message
        subject = "Password Reset Request - Penny Stock Challenge"
        body = f"""
        Hi {username},

        A password reset was requested for your account. Please use the token below to reset your password in the app.

        Your token is: {token}

        If you did not request this, please ignore this email.

        Thanks,
        The Penny Stock Challenge Team
        """

        msg = MIMEMultipart()
        msg['From'] = smtp_user
        msg['To'] = recipient_email
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'plain'))

        # Send the email
        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.starttls() # Secure the connection
            server.login(smtp_user, smtp_pass)
            server.send_message(msg)

        print(f"Password reset email successfully sent to {recipient_email}")
        return True, "If that user exists, a password reset email has been sent."

    except KeyError:
        error_msg = "Email sending credentials are not configured in secrets.toml."
        print(f"ERROR: {error_msg}")
        # Don't expose detailed errors to the user for security
        return False, "Could not send email due to a server configuration issue."
    except Exception as e:
        print(f"Failed to send email: {e}")
        return False, "An error occurred while trying to send the email."