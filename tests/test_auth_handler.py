# tests/test_auth_handler.py
import pytest

# Make sure auth_handler can be imported
from auth_handler import hash_password, check_password

def test_password_hashing_and_checking():
    """Test that hashing creates a valid hash and checking works."""
    plain = "password123"
    hashed = hash_password(plain)

    # Check hash format (basic check)
    assert isinstance(hashed, str)
    assert hashed.startswith("$2b$") # bcrypt hash identifier
    assert len(hashed) == 60 # Standard bcrypt hash length

    # Check correct password
    assert check_password(plain, hashed) is True

    # Check incorrect password
    assert check_password("wrongpassword", hashed) is False

    # Check behaviour with empty strings (adjust if specific handling is needed)
    assert check_password("", hash_password("")) is True
    assert check_password("a", hash_password("")) is False

def test_hash_with_none_input():
    """Test that hash_password returns None when input is None."""
    # The function catches the internal AttributeError and returns None
    hashed = hash_password(None)
    assert hashed is None

def test_check_password_with_none_input():
    """Test check_password handles None input for password gracefully."""
    # Assuming check_password handles None input by returning False
    # (You might want to verify the check_password implementation handles None args safely)
    # Provide a dummy valid hash structure for the second argument
    dummy_hash = "$2b$12$abcdefghijklmnopqrstuvwxyzABCDEFGHIJKL." # Example structure
    assert check_password(None, dummy_hash) is False
    # Optionally test None hash too if relevant for your logic
    # assert check_password("some_password", None) is False

# Add tests for other auth_handler functions (add_user, get_user) later
# These will require mocking the database connection (sqlite3.connect)
# or using a temporary in-memory database.