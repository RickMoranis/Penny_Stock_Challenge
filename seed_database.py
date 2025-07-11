# seed_database.py
import sqlite3
import os
import bcrypt
from datetime import datetime, timedelta

DATABASE_FILE = "trades.db"

def hash_password(password: str) -> str:
    """Hashes a password using bcrypt."""
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def seed():
    """Deletes the old database and creates a new one with sample data."""
    # --- Delete old database if it exists ---
    if os.path.exists(DATABASE_FILE):
        os.remove(DATABASE_FILE)
        print(f"Removed old database: {DATABASE_FILE}")

    # --- Connect and create tables ---
    conn = sqlite3.connect(DATABASE_FILE)
    cursor = conn.cursor()

    # Create users table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            hashed_password TEXT NOT NULL,
            registration_date TEXT NOT NULL,
            is_admin INTEGER DEFAULT 0
        )
    ''')
    print("Created 'users' table.")

    # Create trades table
    # --- FIX: Changed 'timestamp TEXT NOT NULL' to 'timestamp TEXT' to allow nulls ---
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
    print("Created 'trades' table.")

    # --- Sample Data ---
    users_to_add = [
        # username, name, email, password, is_admin (1 for yes, 0 for no)
        ('jaha', 'Jaha', 'jaha@example.com', 'pass123', 1),
        ('hubernickel', 'Huber Nickel', 'hubes@example.com', 'pass123', 0),
        ('thegriddler', 'The Griddler', 'griddler@example.com', 'pass123', 0)
    ]

    trades_to_add = [
        # participant, timestamp (days ago), ticker, action, shares, price
        ('jaha', 35, 'ONDS', 'Buy', 100, 1.20),
        ('jaha', 30, 'IMUX', 'Buy', 200, 0.75),
        ('jaha', 25, 'ONDS', 'Sell', 50, 1.50),
        ('jaha', 15, 'RENB', 'Buy', 500, 0.25),
        ('jaha', 5, 'IMUX', 'Sell', 100, 0.95),

        ('hubernickel', 40, 'EONR', 'Buy', 300, 0.40),
        ('hubernickel', 38, 'ONDS', 'Buy', 150, 1.10),
        ('hubernickel', 20, 'EONR', 'Sell', 100, 0.35),
        ('hubernickel', 10, 'RENB', 'Buy', 1000, 0.30),

        ('thegriddler', 45, 'IMUX', 'Buy', 50, 0.80),
        ('thegriddler', 44, 'RENB', 'Buy', 200, 0.28),
        ('thegriddler', 22, 'IMUX', 'Sell', 50, 0.85),
        # This trade has a bad timestamp to test the error handling
        ('thegriddler', None, 'BADDATA', 'Buy', 10, 1.0)
    ]

    # --- Insert Users ---
    for username, name, email, password, is_admin in users_to_add:
        hashed_pw = hash_password(password)
        reg_date = (datetime.now() - timedelta(days=50)).strftime('%Y-%m-%d %H:%M:%S')
        cursor.execute(
            "INSERT INTO users (username, name, email, hashed_password, registration_date, is_admin) VALUES (?, ?, ?, ?, ?, ?)",
            (username, name, email, hashed_pw, reg_date, is_admin)
        )
    print(f"Inserted {len(users_to_add)} users.")

    # --- Insert Trades ---
    for participant, days_ago, ticker, action, shares, price in trades_to_add:
        if days_ago is not None:
            timestamp = (datetime.now() - timedelta(days=days_ago)).strftime('%Y-%m-%d %H:%M:%S')
        else:
            # Insert a null timestamp to test robustness
            timestamp = None
            
        cursor.execute(
            "INSERT INTO trades (participant, timestamp, ticker, action, shares, price) VALUES (?, ?, ?, ?, ?, ?)",
            (participant, timestamp, ticker, action, shares, price)
        )
    print(f"Inserted {len(trades_to_add)} trades.")


    # --- Commit and Close ---
    conn.commit()
    conn.close()
    print("Database seeded successfully!")

if __name__ == "__main__":
    seed()
