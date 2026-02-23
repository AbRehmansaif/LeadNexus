"""
Data validation utilities
"""
import re
from typing import Optional
from email_validator import validate_email, EmailNotValidError


def is_valid_email(email: str) -> bool:
    """
    Validate email address
    
    Args:
        email: Email address to validate
        
    Returns:
        True if valid, False otherwise
    """
    if not email:
        return False
    
    try:
        validate_email(email)
        return True
    except EmailNotValidError:
        return False


def is_valid_url(url: str) -> bool:
    """
    Validate URL format
    
    Args:
        url: URL to validate
        
    Returns:
        True if valid, False otherwise
    """
    if not url:
        return False
    
    url_pattern = re.compile(
        r'^https?://'  # http:// or https://
        r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|'  # domain...
        r'localhost|'  # localhost...
        r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'  # ...or ip
        r'(?::\d+)?'  # optional port
        r'(?:/?|[/?]\S+)$', re.IGNORECASE)
    
    return url_pattern.match(url) is not None


def is_valid_phone(phone: str) -> bool:
    """
    Validate phone number (basic validation)
    
    Args:
        phone: Phone number to validate
        
    Returns:
        True if valid, False otherwise
    """
    if not phone:
        return False
    
    # Remove common separators
    cleaned = re.sub(r'[\s\-\(\)\+]', '', phone)
    
    # Check if it's a valid phone number (10-15 digits)
    return bool(re.match(r'^\d{10,15}$', cleaned))


def extract_email_from_text(text: str) -> Optional[str]:
    """
    Extract email address from text
    
    Args:
        text: Text to search for email
        
    Returns:
        First valid email found or None
    """
    if not text:
        return None
    
    email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
    matches = re.findall(email_pattern, text)
    
    for match in matches:
        if is_valid_email(match):
            return match
    
    return None


def extract_phone_from_text(text: str) -> Optional[str]:
    """
    Extract phone number from text
    
    Args:
        text: Text to search for phone number
        
    Returns:
        First valid phone found or None
    """
    if not text:
        return None
    
    # Common phone patterns
    patterns = [
        r'\+?\d{1,3}[-.\s]?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}',  # +1-234-567-8900
        r'\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}',  # (234) 567-8900
        r'\d{3}[-.\s]?\d{3}[-.\s]?\d{4}',  # 234-567-8900
    ]
    
    for pattern in patterns:
        matches = re.findall(pattern, text)
        for match in matches:
            if is_valid_phone(match):
                return match
    
    return None


def clean_text(text: str) -> str:
    """
    Clean and normalize text
    
    Args:
        text: Text to clean
        
    Returns:
        Cleaned text
    """
    if not text:
        return ""
    
    # Remove extra whitespace
    text = re.sub(r'\s+', ' ', text)
    
    # Remove leading/trailing whitespace
    text = text.strip()
    
    return text


def extract_domain(url: str) -> Optional[str]:
    """
    Extract domain from URL
    
    Args:
        url: URL to extract domain from
        
    Returns:
        Domain or None
    """
    if not url:
        return None
    
    pattern = r'https?://(?:www\.)?([^/]+)'
    match = re.search(pattern, url)
    
    return match.group(1) if match else None
