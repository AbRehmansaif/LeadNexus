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

# ─── Forge Nexus Master Blacklists (Imported for Web Intelligence) ───────────────
JUNK_EMAILS_BLACKSET = {
    'example@domain.com', 'info@example.com', 'contact@example.com', 'admin@example.com',
    'support@example.com', 'sales@example.com', 'hello@example.com', 'test@example.com',
    'demo@example.com', 'user@example.com', 'mail@example.com', 'office@example.com',
    'service@example.com', 'team@example.com', 'noreply@example.com', 'no-reply@example.com',
    'dummy@example.com', 'sample@example.com', 'client@example.com', 'business@example.com',
    'company@example.com', 'name@domain.com', 'email@domain.com', 'yourname@domain.com',
    'your@email.com', 'abc@domain.com', 'xyz@domain.com', 'test123@example.com',
    'user123@example.com', 'webmaster@domain.com', 'postmaster@domain.com', 'hostmaster@domain.com',
    'root@domain.com', 'abuse@domain.com', 'security@domain.com', 'privacy@domain.com',
    'legal@domain.com', 'compliance@domain.com', 'administrator@domain.com', 'web@domain.com',
    'website@domain.com', 'cms@domain.com', 'cpanel@domain.com', 'panel@domain.com',
    'hosting@domain.com', 'no_reply@domain.com', 'donotreply@domain.com', 'do-not-reply@domain.com',
    'dontreply@domain.com', 'mailer-daemon@domain.com', 'bounce@domain.com', 'returns@domain.com',
    'notifications@domain.com', 'notification@domain.com', 'notify@domain.com', 'alerts@domain.com',
    'updates@domain.com', 'system@domain.com', 'server@domain.com', 'robot@domain.com',
    'bot@domain.com', 'automated@domain.com', 'auto@domain.com', 'autoresponder@domain.com',
    'mailer@domain.com', 'noreply@notifications.domain.com', 'system@notifications.domain.com',
    'mail@notifications.domain.com', 'test@test.com', 'test@domain.com', 'demo@domain.com',
    'sample@domain.com', 'fake@domain.com', 'spam@domain.com', 'trash@domain.com',
    'temp@domain.com', 'temporary@domain.com', 'tempmail@domain.com', 'disposable@domain.com',
    'throwaway@domain.com', 'unknown@domain.com', 'none@domain.com', 'null@domain.com',
    'blank@domain.com', 'noemail@domain.com', 'noemail@noemail.com', 'temp@mail.com',
    'fake@mail.com', 'user@user.com', 'email@email.com', 'contact@domain.com',
    'info@domain.com', 'admin@site.com', 'test@mail.com', 'hello@site.com',
    'support@site.com', 'asd@domain.com', 'qwe@domain.com', 'abc123@domain.com',
    '123@domain.com', 'test@test123.com', 'apollo@apollo.io'
}

JUNK_DOMAINS_BLACKSET = {
    'domain.com', 'example.com', 'test.com', 'none.com', 'null.com', 'dummy.com',
    'fake.com', 'sample.com', 'company.com', 'noemail.com', 'noemail.io', 'test.io',
    'sentry.io', 'wixpress.com'
}

JUNK_PREFIX_RE = re.compile(
    r'^(?:example|test|demo|user|mail|office|service|'
    r'noreply|no-reply|no_reply|donotreply|do-not-reply|dontreply|dummy|sample|client|company|'
    r'name|email|yourname|your|abc|xyz|webmaster|postmaster|hostmaster|root|abuse|security|privacy|'
    r'legal|compliance|administrator|web|website|cms|cpanel|panel|hosting|mailer-daemon|bounce|bounces|'
    r'return|returns|complaints|notifications|notification|notify|alerts|updates|system|server|robot|bot|'
    r'automated|automation|auto|autoresponder|mailer|maildaemon|dev|help|helpdesk|billing|accounts|'
    r'customerservice|unknown|none|null|blank|noemail|nobody|noone|asd|qwe|abc123|123|111|1234|'
    r'temp|temporary|tempmail|disposable|throwaway|fake|spam|trash|apollo|'
    r'temp\d*|test\d*|user\d*|abc\d*)', re.I
)

def is_high_quality_email(email: str) -> bool:
    """Provides a Forge-Nexus level high-standard email validation."""
    if not is_valid_email(email):
        return False
        
    email_clean = email.strip().lower()
    
    # Layer 1: Check exact junk email blacklist
    if email_clean in JUNK_EMAILS_BLACKSET:
        return False
        
    # Layer 2: Check junk domain blacklist
    domain = email_clean.split('@')[-1]
    if domain in JUNK_DOMAINS_BLACKSET:
        return False
        
    # Layer 3: Check junk prefix regex (local-part)
    local_part = email_clean.split('@')[0]
    if JUNK_PREFIX_RE.match(local_part):
        return False
        
    # Layer 4: Avoid highly suspect extensions that aren't real mailboxes usually
    if domain.endswith(('.png', '.jpg', '.jpeg', '.gif', '.webp', '.svg')):
        return False
        
    return True


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
