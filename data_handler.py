# data_handler.py
import pandas as pd
import os
import sqlite3
from datetime import datetime

# --- Smart Database Path ---
if 'RAILWAY_ENVIRONMENT' in os.environ:
    DATABASE_FILE = "/data/trades.db"
else:
    DATABASE_FILE = "trades.db"

# --- Database Initialization ---

def init_db():
    """Initializes the database and creates the trades table if it doesn't exist."""
    try:
        if 'RAILWAY_ENVIRONMENT' in os.environ:
            os.makedirs(os.path.dirname(DATABASE_FILE), exist_ok=True)

        conn = sqlite3.connect(DATABASE_FILE)
        cursor = conn.cursor()
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS trades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            participant TEXT NOT NULL,
            timestamp TEXT,
            ticker TEXT NOT NULL,
            action TEXT NOT NULL,
            shares REAL NOT NULL,
            price REAL NOT NULL
        )
        ''')
        conn.commit()
        print(f"Database '{DATABASE_FILE}' initialized successfully.")
    except sqlite3.Error as e:
        print(f"Database error during initialization: {e}")
    finally:
        if 'conn' in locals() and conn:
            conn.close()

def load_data() -> pd.DataFrame:
    """Loads all trade data from the SQLite database into a Pandas DataFrame."""
    if not os.path.exists(DATABASE_FILE):
        print(f"Database file {DATABASE_FILE} not found. Initializing.")
        init_db()
        return pd.DataFrame(columns=['id', 'participant', 'timestamp', 'ticker', 'action', 'shares', 'price'])

    conn = None
    try:
        conn = sqlite3.connect(DATABASE_FILE)
        query = "SELECT id, participant, timestamp, ticker, action, shares, price FROM trades"
        df = pd.read_sql_query(query, conn)
        if 'timestamp' in df.columns and not df.empty:
            df['timestamp'] = pd.to_datetime(df['timestamp'], errors='coerce')
        print(f"Loaded {len(df)} records from {DATABASE_FILE}")
        return df
    except Exception as e:
        print(f"An unexpected error occurred during data load: {e}")
        return pd.DataFrame()
    finally:
        if conn:
            conn.close()

def log_trade(participant: str, ticker: str, action: str, shares: float, price: float):
    """
    Logs a single new trade to the database with a current timestamp.
    This is the FIX for Bug #1.
    """
    conn = None
    try:
        conn = sqlite3.connect(DATABASE_FILE)
        cursor = conn.cursor()
        # Generate timestamp right before insertion
        timestamp_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        sql = """
        INSERT INTO trades (participant, timestamp, ticker, action, shares, price)
        VALUES (?, ?, ?, ?, ?, ?)
        """
        cursor.execute(sql, (participant, timestamp_str, ticker, action, shares, price))
        conn.commit()
        print(f"Logged trade for {participant}: {action} {shares} {ticker} @ {price}")
        return True
    except Exception as e:
        print(f"Database error logging trade: {e}")
        return False
    finally:
        if conn:
            conn.close()

def save_trade(new_trade_df: pd.DataFrame):
    """Saves one or more new trades from a DataFrame (used for CSV import)."""
    if new_trade_df.empty:
        return
    df_to_save = new_trade_df.copy()
    if 'timestamp' in df_to_save.columns:
        # Convert datetime objects to string for database compatibility
        df_to_save['timestamp'] = df_to_save['timestamp'].apply(
            lambda x: x.strftime('%Y-%m-%d %H:%M:%S') if pd.notnull(x) else None
        )

    conn = None
    try:
        conn = sqlite3.connect(DATABASE_FILE)
        df_to_save.to_sql('trades', conn, if_exists='append', index=False)
        print(f"Saved {len(df_to_save)} trade(s) to database from DataFrame.")
    except Exception as e:
        print(f"Database error saving trade from DataFrame: {e}")
    finally:
        if conn:
            conn.close()

def delete_trade(trade_id: int, username: str) -> bool:
    """Deletes a specific trade by its ID, ensuring it belongs to the user."""
    conn = None
    try:
        conn = sqlite3.connect(DATABASE_FILE)
        cursor = conn.cursor()
        sql = "DELETE FROM trades WHERE id = ? AND participant = ?"
        cursor.execute(sql, (trade_id, username))
        deleted_count = cursor.rowcount
        conn.commit()
        return deleted_count > 0
    except Exception as e:
        print(f"Database error deleting trade ID {trade_id}: {e}")
        return False
    finally:
        if conn:
            conn.close()

def admin_delete_trade(trade_id: int) -> bool:
    """Deletes a single trade by its ID, for admin use."""
    conn = None
    try:
        conn = sqlite3.connect(DATABASE_FILE)
        cursor = conn.cursor()
        sql = "DELETE FROM trades WHERE id = ?"
        cursor.execute(sql, (trade_id,))
        deleted_count = cursor.rowcount
        conn.commit()
        return deleted_count > 0
    except Exception as e:
        print(f"Database error during admin delete for trade ID {trade_id}: {e}")
        return False
    finally:
        if conn:
            conn.close()

def admin_update_trade_timestamp(trade_id: int, new_timestamp: datetime) -> bool:
    """Updates the timestamp for a specific trade, for admin use."""
    conn = None
    try:
        conn = sqlite3.connect(DATABASE_FILE)
        cursor = conn.cursor()
        timestamp_str = new_timestamp.strftime('%Y-%m-%d %H:%M:%S')
        sql = "UPDATE trades SET timestamp = ? WHERE id = ?"
        cursor.execute(sql, (timestamp_str, trade_id))
        updated_count = cursor.rowcount
        conn.commit()
        return updated_count > 0
    except Exception as e:
        print(f"Database error updating timestamp for trade ID {trade_id}: {e}")
        return False
    finally:
        if conn:
            conn.close()

def process_and_save_csv(uploaded_file, participant_name: str) -> (bool, str):
    """Reads a CSV file, validates it, and saves the trades to the database."""
    try:
        df = pd.read_csv(uploaded_file)
    except Exception as e:
        return False, f"Error reading CSV file: {e}"

    required_columns = ['timestamp', 'ticker', 'action', 'shares', 'price']
    df.columns = df.columns.str.lower().str.strip()
    missing_cols = [col for col in required_columns if col not in df.columns]
    if missing_cols:
        return False, f"CSV is missing required columns: {', '.join(missing_cols)}"

    df = df[required_columns]
    df.dropna(inplace=True)

    if df.empty:
        return False, "No valid trade data found in the uploaded file after cleaning."

    try:
        df['timestamp'] = pd.to_datetime(df['timestamp'], errors='coerce')
        df['shares'] = pd.to_numeric(df['shares'], errors='coerce')
        df['price'] = pd.to_numeric(df['price'], errors='coerce')
        df['action'] = df['action'].str.strip().str.title()
    except Exception as e:
        return False, f"Error converting data types in CSV: {e}"

    df.dropna(inplace=True)
    df = df[df['action'].isin(['Buy', 'Sell'])]
    df = df[(df['shares'] > 0) & (df['price'] > 0)]

    if df.empty:
        return False, "No valid trade data remaining after validation."

    df['participant'] = participant_name

    try:
        save_trade(df)
        return True, f"Successfully imported {len(df)} trades!"
    except Exception as e:
        return False, f"A database error occurred during import: {e}"

# --- Call init_db() once on module load to ensure DB/table exists ---
print(f"Data handler module loaded. Checking/Initializing DB: {DATABASE_FILE}")
init_db()