"""
Data validation utilities (ported from the standalone scraper)
"""
import re
from typing import Optional


def is_valid_email(email: str) -> bool:
    if not email:
        return False
    pattern = r'^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$'
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
    if not text:
        return None
    email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
    matches = re.findall(email_pattern, text)
    for match in matches:
        if is_valid_email(match):
            return match
    return None


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


def clean_text(text: str) -> str:
    if not text:
        return ""
    text = re.sub(r'\s+', ' ', text)
    return text.strip()
