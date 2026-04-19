"""
Data validation utilities (ported from the standalone scraper)
"""
import re
from typing import Optional, List


def is_valid_email(email: str) -> bool:
    if not email:
        return False
    pattern = r'^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,24}$'
    return bool(re.match(pattern, email.strip()))


def is_valid_url(url: str) -> bool:
    if not url:
        return False
    url_pattern = re.compile(
        r'^https?://'
        r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,12}\.?|'
        r'localhost|'
        r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'
        r'(?::\d+)?'
        r'(?:/?|[/?]\S+)$', re.IGNORECASE)
    return url_pattern.match(url) is not None


def is_valid_phone(phone: str) -> bool:
    if not phone:
        return False
    cleaned = re.sub(r'[\s\-\(\)\+]', '', phone)
    return bool(re.match(r'^\d{10,15}$', cleaned))


def extract_email_from_text(text: str) -> Optional[str]:
    """Single email extraction - returns the first valid one."""
    emails = extract_emails_from_text(text)
    return emails[0] if emails else None


def extract_emails_from_text(text: str) -> List[str]:
    """
    Enhanced extraction to catch standard and obfuscated emails.
    Catches: user@domain.com, user[at]domain.com, user(at)domain.com
    """
    if not text:
        return []

    # 1. Obfuscation mapping
    text = text.replace("[at]", "@").replace("(at)", "@").replace("[dot]", ".").replace("(dot)", ".")
    
    # 2. Standard regex (no literal pipe in char class, max length 63 for TLD)
    email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,63}\b'
    matches = re.findall(email_pattern, text)
    
    unique_emails = []
    
    # 3. Aggressive cleanup of fused text (like user@lear.comCopyright)
    # If it ends with a common TLD followed by random letters, truncate it.
    tld_fusion_pattern = re.compile(
        r'\.(com|net|org|edu|gov|mil|int|co|io|ai|us|uk|ca|au|eu|de|fr|in|biz|info)[A-Za-z]{2,}$', 
        re.IGNORECASE
    )
    
    for match in matches:
        match = match.strip()
        
        # Strip leading numbers/hyphens if it looks like a phone number was fused to the front
        # e.g., 248-794-3472gstallings@lear.com -> gstallings@lear.com
        match = re.sub(r'^[\d\-]+([A-Za-z_])', r'\1', match)
        
        # Truncate trailing fused text from TLDs
        match = tld_fusion_pattern.sub(r'.\1', match)
        
        # Trim off any hanging weird characters
        match = match.rstrip('.,:;\'"-')
        
        if is_valid_email(match) and match not in unique_emails:
            unique_emails.append(match)
            
    return unique_emails


def extract_phone_from_text(text: str) -> Optional[str]:
    if not text:
        return None
    patterns = [
        r'\+?\d{1,3}[-.\\s]?\(?\d{3}\)?[-.\\s]?\d{3}[-.\\s]?\d{4}',
        r'\(?\d{3}\)?[-.\\s]?\d{3}[-.\\s]?\d{4}',
        r'\d{3}[-.\\s]?\d{3}[-.\\s]?\d{4}',
    ]
    for pattern in patterns:
        matches = re.findall(pattern, text)
        for match in matches:
            if is_valid_phone(match):
                return match
    return None


def decode_cloudflare_email(encoded_string: str) -> Optional[str]:
    """
    Decodes a Cloudflare protected email string.
    Cloudflare uses a simple XOR cipher. The first two characters are the XOR key.
    """
    try:
        if not encoded_string or len(encoded_string) < 4:
            return None
            
        # Extract the key (first 2 hex characters)
        key = int(encoded_string[:2], 16)
        
        # Decode the rest of the string
        email = ""
        for i in range(2, len(encoded_string), 2):
            char_hex = encoded_string[i:i+2]
            char_val = int(char_hex, 16)
            email += chr(char_val ^ key)
            
        return email if is_valid_email(email) else None
    except Exception:
        return None


def clean_text(text: str) -> str:
    if not text:
        return ""
    text = re.sub(r'\s+', ' ', text)
    return text.strip()
