#!/usr/bin/env python3
"""
FieldKit Phase 1: Password Hash Generator
Created: 2026-02-10
Purpose: Generate bcrypt password hashes for seed users
"""

import bcrypt
import sys

def hash_password(password: str) -> str:
    """
    Generate bcrypt hash for a password.
    Uses cost factor of 12 (good balance of security and performance).
    """
    password_bytes = password.encode('utf-8')
    salt = bcrypt.gensalt(rounds=12)
    hashed = bcrypt.hashpw(password_bytes, salt)
    return hashed.decode('utf-8')

def verify_password(password: str, hashed: str) -> bool:
    """Verify a password against its hash."""
    password_bytes = password.encode('utf-8')
    hashed_bytes = hashed.encode('utf-8')
    return bcrypt.checkpw(password_bytes, hashed_bytes)

def main():
    """Generate password hashes for default users."""
    
    print("=" * 60)
    print("FieldKit Password Hash Generator")
    print("=" * 60)
    print()
    
    # Default password for all seed users
    default_password = "fieldkit2026"
    
    print(f"Generating bcrypt hash for default password: {default_password}")
    print()
    
    # Generate hash
    password_hash = hash_password(default_password)
    
    print("Generated hash:")
    print(password_hash)
    print()
    
    # Verify it works
    if verify_password(default_password, password_hash):
        print("✓ Hash verified successfully")
    else:
        print("✗ Hash verification failed")
        sys.exit(1)
    
    print()
    print("=" * 60)
    print("To update seed_data.sql:")
    print("=" * 60)
    print()
    print("Replace all instances of '$2b$12$PLACEHOLDER' with:")
    print(f"'{password_hash}'")
    print()
    print("Or run: sed -i 's/\\$2b\\$12\\$PLACEHOLDER/{}/g' database/seed/seed_data.sql".format(password_hash.replace('$', '\\$')))
    print()
    print("IMPORTANT: Users should change their passwords after first login!")
    print()

if __name__ == "__main__":
    # Check if bcrypt is installed
    try:
        import bcrypt
    except ImportError:
        print("Error: bcrypt module not found")
        print("Install it with: pip install bcrypt --break-system-packages")
        sys.exit(1)
    
    main()
