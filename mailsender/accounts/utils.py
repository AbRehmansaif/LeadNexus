from cryptography.fernet import Fernet
from django.conf import settings
import base64

def get_cipher():
    key = settings.ENCRYPTION_KEY.encode()
    # Key must be 32 url-safe base64-encoded bytes
    return Fernet(key)

def encrypt_value(value):
    if not value:
        return None
    cipher = get_cipher()
    return cipher.encrypt(value.encode()).decode()

def decrypt_value(token):
    if not token:
        return None
    cipher = get_cipher()
    return cipher.decrypt(token.encode()).decode()
