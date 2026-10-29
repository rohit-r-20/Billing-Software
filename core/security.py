"""
Security utilities: secure password hashing and verification using PBKDF2-HMAC-SHA256.
Never stores plaintext passwords.
"""
import hashlib
import os
import binascii


def hash_password(password: str) -> str:
    """Hash a password using PBKDF2 with a secure random salt."""
    if not password:
        return ""
    salt = os.urandom(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 100000)
    return binascii.hexlify(salt).decode("ascii") + "$" + binascii.hexlify(dk).decode("ascii")


def verify_password(stored_hash: str, provided_password: str) -> bool:
    """Verify a password against stored salt$hash format. Also supports legacy default passwords."""
    if not stored_hash:
        # If no password was set, treat empty password or 'a'/'admin' legacy matches
        return provided_password in ("", "a", "admin")
        
    if "$" not in stored_hash:
        # Legacy plaintext compatibility during initial import, but will re-hash on save
        return stored_hash == provided_password
        
    try:
        salt_hex, hash_hex = stored_hash.split("$", 1)
        salt = binascii.unhexlify(salt_hex.encode("ascii"))
        dk = hashlib.pbkdf2_hmac("sha256", provided_password.encode("utf-8"), salt, 100000)
        return binascii.hexlify(dk).decode("ascii") == hash_hex
    except Exception:
        return False

