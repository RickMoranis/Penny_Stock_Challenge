# repair_timestamps.py
import sqlite3
import pandas as pd
from datetime import datetime, timedelta
import yfinance as yf
import os

# --- Smart Database Path ---
if 'RAILWAY_ENVIRONMENT' in os.environ:
    DATABASE_FILE = "/data/trades.db"
else:
    DATABASE_FILE = "trades.db"

def get_historical_data_for_repair(tickers):
    """Fetches the last 45 days of OHLC data for given tickers."""
    if not tickers:
        return None
    try:
        # Fetch Open, High, Low, Close data
        end_date = datetime.now()
        start_date = end_date - timedelta(days=45)
        data = yf.download(tickers, start=start_date, end=end_date, progress=False)
        return data
    except Exception as e:
        print(f"Error fetching historical data for repair: {e}")
        return None

def repair_timestamps():
    """
    Finds trades with null timestamps and assigns them an accurate timestamp
    by matching the trade price against historical daily price ranges.
    Returns a list of log messages.
    """
    output_log = []
    conn = None
    try:
        conn = sqlite3.connect(DATABASE_FILE)
        trades_df = pd.read_sql_query("SELECT * FROM trades", conn)
        null_timestamp_trades = trades_df[trades_df['timestamp'].isnull()]

        if null_timestamp_trades.empty:
            output_log.append("No trades with missing timestamps found. Database is clean.")
            return output_log

        output_log.append(f"Found {len(null_timestamp_trades)} trades with missing timestamps. Attempting smart repair...")
        
        tickers_to_fetch = null_timestamp_trades['ticker'].unique().tolist()
        historical_data = get_historical_data_for_repair(tickers_to_fetch)

        if historical_data is None or historical_data.empty:
            output_log.append("Could not fetch historical data. Cannot perform smart repair.")
            return output_log

        trades_to_fix = null_timestamp_trades.sort_values(by='id')
        cursor = conn.cursor()

        for index, trade in trades_to_fix.iterrows():
            trade_id = trade['id']
            ticker = trade['ticker']
            trade_price = trade['price']
            found_date = None

            try:
                # Get the historical data for the specific ticker
                # The columns are multi-level, e.g., ('High', 'ONDS'), ('Low', 'ONDS')
                # We need to select the data for the current ticker.
                ticker_history = historical_data.loc[:, (slice(None), ticker)]
                ticker_history.columns = ticker_history.columns.droplevel(1) # Drop the ticker level from columns
                
                # Search for a date where the trade price is within the day's high-low range
                for date, day_data in ticker_history.iterrows():
                    if pd.notna(day_data['Low']) and pd.notna(day_data['High']):
                        if day_data['Low'] <= trade_price <= day_data['High']:
                            found_date = date.to_pydatetime()
                            break # Use the first match
            except (KeyError, IndexError):
                # This ticker might not have been in the fetched data
                pass

            if found_date:
                # We found a matching date!
                new_timestamp_str = found_date.strftime('%Y-%m-%d 12:00:00') # Assign noon as a placeholder time
                output_log.append(f"Found match for Trade ID {trade_id} ({ticker} @ ${trade_price:.2f}). Assigning timestamp: {new_timestamp_str}")
            else:
                # Fallback if no match was found (e.g., price is outside historical range)
                output_log.append(f"Could not find price match for Trade ID {trade_id}. Using estimation (not recommended).")
                new_timestamp_str = (datetime.now() - timedelta(days=15)).strftime('%Y-%m-%d %H:%M:%S')

            # Update the database
            cursor.execute(
                "UPDATE trades SET timestamp = ? WHERE id = ?",
                (new_timestamp_str, int(trade_id))
            )

        conn.commit()
        output_log.append("\nDatabase repair complete!")
        return output_log

    except Exception as e:
        output_log.append(f"An unexpected error occurred: {e}")
        return output_log
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    log_messages = repair_timestamps()
    for msg in log_messages:
        print(msg)