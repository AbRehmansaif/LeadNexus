import requests
import time
import re
from typing import List, Dict

class WhatsAppAPIChecker:
    """
    Using wa.me links to check WhatsApp availability
    This is a simpler approach that doesn't require authentication
    """
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
    
    def check_number(self, phone_number: str) -> bool:
        """
        Check if number has WhatsApp by testing wa.me link
        """
        if not phone_number:
            return False
            
        clean_number = re.sub(r'\D', '', phone_number)
        if not clean_number:
            return False
        
        try:
            # Try to access the wa.me link
            url = f"https://wa.me/{clean_number}"
            response = self.session.get(url, allow_redirects=True, timeout=10)
            
            # If we get redirected to WhatsApp Web, number exists
            if 'web.whatsapp.com' in response.url:
                return True
            
            # Check response content for indicators
            content = response.text.lower()
            
            # Positive indicators
            if any(phrase in content for phrase in ['continue to chat', 'message', 'chat']):
                return True
            
            # Negative indicators
            if any(phrase in content for phrase in ['invalid', 'error', 'not found']):
                return False
            
            # Default to True if we got a successful response
            return response.status_code == 200
            
        except Exception:
            return False

def format_phone_number(number: str, default_country_code: str = '') -> str:
    """
    Format phone number to international format.
    If default_country_code is empty, it only cleans the number.
    """
    if not number:
        return ''
        
    # Remove common separators and non-digit characters except '+'
    clean = re.sub(r'[^\d+]', '', str(number))
    
    # If it starts with 00, treat as +
    if clean.startswith('00'):
        clean = '+' + clean[2:]
    
    # Add country code if provided and not already present
    if default_country_code and not clean.startswith('+'):
        if clean.startswith('0'):
            clean = clean[1:]  # Remove leading 0
        
        # Prepend default if not already starting with those digits
        cc_digits = default_country_code.replace('+', '')
        if not clean.startswith(cc_digits):
            clean = cc_digits + clean
            
        if not clean.startswith('+'):
            clean = '+' + clean
    
    return clean
