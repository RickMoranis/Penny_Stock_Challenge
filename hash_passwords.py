import bcrypt
import sys

# --- IMPORTANT ---
# List the PLAIN TEXT passwords IN THE SAME ORDER
# as the users you defined in config.yaml
passwords_to_hash = [
    'Halo1987'
    # Add more passwords here if you have more users, in order
]
# ---------------

print("Generating Hashes using bcrypt (copy these into config.yaml in order):")

hashed_passwords_bcrypt = []
for pwd in passwords_to_hash:
    try:
        # Encode password to bytes (bcrypt requires bytes)
        pwd_bytes = pwd.encode('utf-8')

        # Generate salt and hash the password
        salt = bcrypt.gensalt()
        hashed = bcrypt.hashpw(pwd_bytes, salt)

        # Decode the hash back to a string for storing in YAML
        hashed_passwords_bcrypt.append(hashed.decode('utf-8'))
        print(f"  Successfully hashed password starting with: {pwd[:3]}...")

    except NameError:
        print("\nERROR: bcrypt library not found.", file=sys.stderr)
        print("Please install it: pip install bcrypt", file=sys.stderr)
        sys.exit(1) # Exit if bcrypt isn't installed
    except Exception as e:
         print(f"\nERROR hashing password starting with '{pwd[:3]}...': {e}", file=sys.stderr)
         hashed_passwords_bcrypt.append(f"ERROR_HASHING_{pwd[:3]}")

print("\nGenerated Hashes:")
print(hashed_passwords_bcrypt)