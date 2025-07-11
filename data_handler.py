# data_handler.py
import pandas as pd
import os
import sqlite3 # Import the sqlite3 library
from datetime import datetime # Keep datetime for potential type handling

DATA_DIR = "/data" # Define a data directory mount point
# In data_handler.py

# --- Smart Database Path ---
if 'RAILWAY_ENVIRONMENT' in os.environ:
    DATABASE_FILE = "/data/trades.db"
else:
    DATABASE_FILE = "trades.db"

# --- Database Initialization ---

def init_db():
    """Initializes the database and creates the trades table if it doesn't exist."""
    try:
        os.makedirs(DATA_DIR, exist_ok=True)
        conn = sqlite3.connect(DATABASE_FILE)
        cursor = conn.cursor()
        # Create table - Adjust column types as needed
        # Using TEXT for timestamp for simplicity, similar to CSV read. REAL for numeric.
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                participant TEXT NOT NULL,
                timestamp TEXT NOT NULL,
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
        if conn:
            conn.close()

def load_data() -> pd.DataFrame:
    """Loads all trade data from the SQLite database into a Pandas DataFrame."""
    # Ensure DB is initialized before loading
    if not os.path.exists(DATABASE_FILE):
         print(f"Database file {DATABASE_FILE} not found. Initializing.")
         init_db()
         # Return empty dataframe if DB was just created empty
         return pd.DataFrame(columns=['id', 'participant', 'timestamp', 'ticker', 'action', 'shares', 'price']) 

    conn = None # Initialize conn to None
    try:
        conn = sqlite3.connect(DATABASE_FILE)
        # Use pandas read_sql_query for convenience
        query = "SELECT id, participant, timestamp, ticker, action, shares, price FROM trades" # Added 'id' here
        df = pd.read_sql_query(query, conn)

        # --- Handle Timestamp Conversion ---
        # Convert timestamp column to datetime objects here for consistency
        # This centralizes the conversion previously done in portfolio.py
        if 'timestamp' in df.columns and not df.empty:
             try:
                # Attempt conversion, handling potential errors
                df['timestamp'] = pd.to_datetime(df['timestamp'], errors='coerce')
                # Optional: Drop rows where timestamp conversion failed if needed
                # df = df.dropna(subset=['timestamp'])
             except Exception as time_e:
                  print(f"Warning: Error converting timestamp column during load: {time_e}. Check data format.")
                  # Depending on requirements, either return df as-is or handle error differently

        print(f"Loaded {len(df)} records from {DATABASE_FILE}")
        return df

    except (sqlite3.Error, pd.io.sql.DatabaseError) as e:
        print(f"Database error loading data: {e}")
        # If loading fails (e.g., table doesn't exist yet after init somehow failed), return empty
        # Also try to re-initialize in case the file exists but table is missing
        print("Attempting to re-initialize DB due to load error.")
        init_db()
        return pd.DataFrame(columns=['participant', 'timestamp', 'ticker', 'action', 'shares', 'price'])
    except Exception as e:
         print(f"An unexpected error occurred during data load: {e}")
         return pd.DataFrame(columns=['participant', 'timestamp', 'ticker', 'action', 'shares', 'price'])
    finally:
        if conn:
            conn.close()


def save_trade(new_trade_df: pd.DataFrame):
    """Saves a new trade (passed as a single-row DataFrame) into the SQLite database."""
    if new_trade_df.empty:
        print("Error: Attempted to save an empty trade DataFrame.")
        return

    # Ensure DB and table exist
    if not os.path.exists(DATABASE_FILE):
         print(f"Database file {DATABASE_FILE} not found. Initializing.")
         init_db()

    conn = None # Initialize conn to None
    try:
        conn = sqlite3.connect(DATABASE_FILE)
        cursor = conn.cursor()

        # Extract data from the first (and assumed only) row of the DataFrame
        trade_data = new_trade_df.iloc[0]

        # Prepare data tuple for insertion
        # Convert timestamp to string for storage if it's a datetime object
        timestamp_val = trade_data['timestamp']
        if isinstance(timestamp_val, pd.Timestamp):
             timestamp_str = timestamp_val.isoformat() # Store in standard ISO format
        else:
             timestamp_str = str(timestamp_val) # Assume it's already string-like

        # Use parameterized query to prevent SQL injection
        sql = ''' INSERT INTO trades(participant, timestamp, ticker, action, shares, price)
                  VALUES(?,?,?,?,?,?) '''
        params = (
            trade_data['participant'],
            timestamp_str,
            trade_data['ticker'],
            trade_data['action'],
            float(trade_data['shares']), # Ensure numeric types
            float(trade_data['price'])
        )

        cursor.execute(sql, params)
        conn.commit()
        print(f"Saved trade for {trade_data['participant']} - {trade_data['ticker']}")

    except (sqlite3.Error, KeyError, IndexError) as e:
        print(f"Database error saving trade: {e}")
        # Potentially roll back if needed, though commit is atomic here
    except Exception as e:
         print(f"An unexpected error occurred during trade save: {e}")
    finally:
        if conn:
            conn.close()

def delete_trade(trade_id: int, username: str):
    """Deletes a specific trade by its ID, ensuring it belongs to the user."""
    if not isinstance(trade_id, int) or trade_id <= 0:
         print(f"Error: Invalid trade_id provided for deletion: {trade_id}")
         return False # Indicate failure

    conn = None
    deleted_count = 0
    try:
        conn = sqlite3.connect(DATABASE_FILE)
        cursor = conn.cursor()
        # Delete only if the id matches AND the participant matches the logged-in user
        sql = "DELETE FROM trades WHERE id = ? AND participant = ?"
        cursor.execute(sql, (trade_id, username))
        deleted_count = cursor.rowcount # Check how many rows were affected
        conn.commit()
        if deleted_count > 0:
             print(f"Successfully deleted trade ID {trade_id} for user {username}.")
             return True # Indicate success
        else:
             print(f"Warning: Trade ID {trade_id} not found or does not belong to user {username}. No deletion occurred.")
             return False # Indicate failure or no action needed

    except sqlite3.Error as e:
        print(f"Database error deleting trade ID {trade_id}: {e}")
        return False # Indicate failure
    except Exception as e:
         print(f"An unexpected error occurred during trade deletion: {e}")
         return False # Indicate failure
    finally:
        if conn:
            conn.close()

def admin_delete_trade(trade_id: int) -> bool:
    """
    Deletes a specific trade by its ID without checking the participant.
    intended for admin use only. Returns True on success, False on failure.
    """
    if not isinstance(trade_id, int) or trade_id <= 0:
         print(f"Error: Invalid trade_id provided for admin deletion: {trade_id}")
         return False # Indicate failure

    conn = None
    deleted_count = 0
    try:
        conn = sqlite3.connect(DATABASE_FILE)
        cursor = conn.cursor()
        # Delete based only on trade ID
        sql = "DELETE FROM trades WHERE id = ?"
        cursor.execute(sql, (trade_id,))
        deleted_count = cursor.rowcount # Check how many rows were affected
        conn.commit()
        if deleted_count > 0:
             print(f"Admin successfully deleted trade ID {trade_id}.")
             return True # Indicate success
        else:
             print(f"Warning: Trade ID {trade_id} not found for admin deletion. No deletion occurred.")
             return False # Indicate failure or no action needed

    except sqlite3.Error as e:
        print(f"Database error during admin delete for trade ID {trade_id}: {e}")
        return False # Indicate failure
    except Exception as e:
         print(f"An unexpected error occurred during admin trade deletion: {e}")
         return False # Indicate failure
    finally:
        if conn:
            conn.close()

# --- Call init_db() once on module load to ensure DB/table exists ---
# This ensures the DB is ready before app.py tries to load/save
# Note: This runs when the module is first imported by Streamlit
print(f"Data handler module loaded. Checking/Initializing DB: {DATABASE_FILE}")
init_db()