import os
import base64
from cryptography.fernet import Fernet
from django.conf import settings

# This key is used to encrypt SMTP passwords in the database.
# In production, this MUST be set as an environment variable 'FERNET_KEY'.
FERNET_KEY = os.getenv("FERNET_KEY")

if not FERNET_KEY:
    # Deterministic fallback using SECRET_KEY if FERNET_KEY is missing.
    # We take the first 32 chars of the SECRET_KEY to create a valid Fernet key.
    # Note: For maximum security, the user should generate a unique key using 
    # Fernet.generate_key() and add it to their .env file.
    key_seed = settings.SECRET_KEY.encode('utf-8')[:32]
    # Ensure it's exactly 32 bytes for base64 encoding to a valid Fernet key
    if len(key_seed) < 32:
        key_seed = key_seed.ljust(32, b'0')
    FERNET_KEY = base64.urlsafe_b64encode(key_seed).decode('utf-8')

cipher_suite = Fernet(FERNET_KEY.encode('utf-8'))

def encrypt_password(text: str) -> str:
    """Encrypts a plain text string into a secure encrypted format."""
    if not text:
        return ""
    # Don't re-encrypt if it already looks like a Fernet token
    # (Tokens start with gAAAA)
    if text.startswith('gAAAA'):
        return text
    return cipher_suite.encrypt(text.encode('utf-8')).decode('utf-8')

def decrypt_password(encrypted_text: str) -> str:
    """Decrypts an encrypted string back to plain text."""
    if not encrypted_text:
        return ""
    try:
        # Only attempt decryption if it looks like an encrypted payload
        if encrypted_text.startswith('gAAAA'):
            return cipher_suite.decrypt(encrypted_text.encode('utf-8')).decode('utf-8')
        return encrypted_text # Fallback for legacy plain text passwords
    except Exception:
        # If decryption fails (e.g. key changed), return text as-is
        return encrypted_text
