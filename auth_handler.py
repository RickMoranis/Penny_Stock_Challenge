# auth_handler.py
import sqlite3
import bcrypt
import os
from datetime import datetime

# Use the same database file as data_handler.py
# Option 1: Define it here (ensure it matches data_handler.py)
DATA_DIR = "/data" # Define a data directory mount point
DATABASE_FILE = os.path.join(DATA_DIR, "trades.db") # Path inside /data
# Option 2 (Slightly cleaner): Import from data_handler if it's defined there
# from data_handler import DATABASE_FILE # Uncomment if DATABASE_FILE defined in data_handler

# --- Hashing Utilities ---

def hash_password(plain_password):
    """Hashes a plain text password using bcrypt."""
    try:
        pwd_bytes = plain_password.encode('utf-8')
        salt = bcrypt.gensalt()
        hashed = bcrypt.hashpw(pwd_bytes, salt)
        return hashed.decode('utf-8') # Store hash as string
    except Exception as e:
        print(f"Error hashing password: {e}")
        return None

def check_password(plain_password, hashed_password):
    """Checks if a plain text password matches a stored bcrypt hash."""
    try:
        plain_bytes = plain_password.encode('utf-8')
        hashed_bytes = hashed_password.encode('utf-8')
        return bcrypt.checkpw(plain_bytes, hashed_bytes)
    except Exception as e:
        print(f"Error checking password: {e}")
        return False

# --- Database Initialization ---

def init_auth_db():
    """Initializes the database and creates the users table if it doesn't exist."""
    conn = None
    try:
        os.makedirs(DATA_DIR, exist_ok=True)
        conn = sqlite3.connect(DATABASE_FILE)
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                name TEXT NOT NULL,
                email TEXT UNIQUE NOT NULL,
                hashed_password TEXT NOT NULL,
                registration_date TEXT NOT NULL,
                is_admin BOOLEAN DEFAULT 0 NOT NULL
            )
        ''')

        try:
            cursor.execute("SELECT is_admin FROM users LIMIT 1")
            print("'is_admin' column already exists.")
        except sqlite3.OperationalError:
            print("Adding 'is_admin' column to users table...")
            cursor.execute("ALTER TABLE users ADD COLUMN is_admin BOOLEAN DEFAULT 0 NOT NULL")
            print("'is_admin' column added.")

        # Optional: Add indexes for faster lookups
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_username ON users (username)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_email ON users (email)")
        conn.commit()
        print(f"Users table in '{DATABASE_FILE}' initialized successfully.")
    except sqlite3.Error as e:
        print(f"Database error during auth initialization: {e}")
    finally:
        if conn:
            conn.close()

# --- User Management Functions ---

def add_user(username, name, email, plain_password):
    """Adds a new user. The first user registered is automatically made an admin."""
    hashed = hash_password(plain_password)
    if not hashed:
        return False, "Password hashing failed."

    conn = None
    try:
        conn = sqlite3.connect(DATABASE_FILE)
        cursor = conn.cursor()

        # --- Check if any users exist ---
        cursor.execute("SELECT COUNT(*) FROM users")
        user_count = cursor.fetchone()[0]
        # --------------------------------

        # --- Determine admin status ---
        is_first_user = (user_count == 0)
        admin_flag = 1 if is_first_user else 0
        # ----------------------------

        # --- Modified SQL INSERT to include is_admin ---
        sql = ''' INSERT INTO users(username, name, email, hashed_password, registration_date, is_admin)
                  VALUES(?,?,?,?,?,?) ''' # Added is_admin placeholder
        params = (
            username,
            name,
            email,
            hashed,
            datetime.now().isoformat(),
            admin_flag # Use the determined admin flag
        )
        # ---------------------------------------------

        cursor.execute(sql, params)
        conn.commit()

        admin_status_message = " (as Admin)" if is_first_user else ""
        print(f"User '{username}' added successfully{admin_status_message}.")
        return True, "User registered successfully."

    except sqlite3.IntegrityError as e:
        # (keep existing error handling for unique constraints)
        error_msg = str(e).lower()
        if 'unique constraint failed: users.username' in error_msg:
            print(f"Error adding user: Username '{username}' already exists.")
            return False, f"Username '{username}' is already taken."
        elif 'unique constraint failed: users.email' in error_msg:
            print(f"Error adding user: Email '{email}' already exists.")
            return False, f"Email '{email}' is already registered."
        else:
             print(f"Database integrity error adding user: {e}")
             return False, f"Database error: {e}"
    except sqlite3.Error as e:
        print(f"Database error adding user: {e}")
        return False, f"Database error: {e}"
    finally:
        if conn:
            conn.close()

def get_user_by_username(username):
    """Retrieves user details (including is_admin) by username (case-insensitive).""" # Updated docstring
    conn = None
    try:
        conn = sqlite3.connect(DATABASE_FILE)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        # --- MODIFIED QUERY: Added COLLATE NOCASE ---
        sql = "SELECT user_id, username, name, email, hashed_password, is_admin FROM users WHERE username = ? COLLATE NOCASE"
        cursor.execute(sql, (username,))
        # -------------------------------------------
        user_data = cursor.fetchone()
        # --- ADD extra debug ---
        print(f"--- [DEBUG INSIDE HANDLER] Fetched data for '{username}': {user_data}")
         # Convert to dict only if user_data is not None
        return dict(user_data) if user_data else None
    except sqlite3.Error as e:
        print(f"Database error fetching user by username '{username}': {e}")
        return None
    finally:
        if conn:
            conn.close()

def get_user_by_email(email):
     """Retrieves user details by email."""
     conn = None
     try:
         conn = sqlite3.connect(DATABASE_FILE)
         conn.row_factory = sqlite3.Row
         cursor = conn.cursor()
         cursor.execute("SELECT user_id, username, name, email, hashed_password FROM users WHERE email = ?", (email,))
         user_data = cursor.fetchone()
         return dict(user_data) if user_data else None
     except sqlite3.Error as e:
         print(f"Database error fetching user by email '{email}': {e}")
         return None
     finally:
         if conn:
             conn.close()


def get_all_users():
    """Retrieves all users (including all necessary columns) for admin panel and streamlit-authenticator."""
    conn = None
    users = []
    try:
        conn = sqlite3.connect(DATABASE_FILE)
        conn.row_factory = sqlite3.Row # Get rows as dictionary-like objects
        cursor = conn.cursor()
        # --- CORRECTED SQL QUERY ---
        # Ensure ALL columns needed by app.py are selected here
        cursor.execute("""
            SELECT
                user_id,
                username,
                name,
                email,
                hashed_password, -- Needed for authenticator init
                is_admin,        -- Needed for admin panel & role check
                registration_date -- Needed for admin panel
            FROM users
            ORDER BY username
        """)
        # --------------------------
        rows = cursor.fetchall()
        for row in rows:
            users.append(dict(row)) # Convert each row to a dictionary
        return users
    except sqlite3.Error as e:
        print(f"Database error fetching all users: {e}")
        # Consider raising the error or returning empty list depending on desired handling
        return [] # Return empty list on error
    finally:
        if conn:
            conn.close()

def delete_user(username_to_delete: str) -> bool:
    """Deletes a user by username. Returns True on success, False on failure."""
    conn = None
    try:
        conn = sqlite3.connect(DATABASE_FILE)
        cursor = conn.cursor()
        # Delete the user matching the username
        sql = "DELETE FROM users WHERE username = ?"
        cursor.execute(sql, (username_to_delete,))
        deleted_count = cursor.rowcount # Check if a row was actually deleted
        conn.commit()
        if deleted_count > 0:
             print(f"Successfully deleted user '{username_to_delete}'.")
             return True
        else:
             print(f"User '{username_to_delete}' not found. No deletion occurred.")
             return False
    except sqlite3.Error as e:
        print(f"Database error deleting user '{username_to_delete}': {e}")
        return False
    except Exception as e:
         print(f"An unexpected error occurred during user deletion: {e}")
         return False
    finally:
        if conn:
            conn.close()


# --- Initialize DB on module load ---
print(f"Auth handler module loaded. Checking/Initializing users table in: {DATABASE_FILE}")
init_auth_db()