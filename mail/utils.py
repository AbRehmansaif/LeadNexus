import json
import base64
import logging
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)

def get_gmail_flow(redirect_uri=None):
    """Returns a Google OAuth Flow object."""
    flow = Flow.from_client_config(
        {
            "web": {
                "client_id": settings.GOOGLE_CLIENT_ID,
                "client_secret": settings.GOOGLE_CLIENT_SECRET,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": [redirect_uri or settings.GOOGLE_REDIRECT_URI],
            }
        },
        scopes=[
            'https://www.googleapis.com/auth/gmail.send',
            'https://www.googleapis.com/auth/gmail.readonly',
            'https://www.googleapis.com/auth/userinfo.email',
            'openid'
        ],
        redirect_uri=redirect_uri or settings.GOOGLE_REDIRECT_URI
    )
    return flow

def get_credentials_from_model(cred_model):
    """Converts a SMTPCredential model instance to Google OAuth Credentials."""
    if cred_model.auth_type != 'oauth':
        return None
        
    creds = Credentials(
        token=cred_model.decrypted_access_token,
        refresh_token=cred_model.decrypted_refresh_token,
        token_uri=cred_model.token_uri,
        client_id=cred_model.client_id,
        client_secret=cred_model.client_secret,
        scopes=json.loads(cred_model.scopes) if cred_model.scopes else []
    )
    
    # Check if expired and refresh
    if creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
            # Update the model with new token
            cred_model.access_token = creds.token
            cred_model.expiry = creds.expiry
            cred_model.save(update_fields=['access_token', 'expiry'])
        except Exception as e:
            logger.error(f"Failed to refresh Gmail token for {cred_model.from_email}: {e}")
            
    return creds

def get_gmail_service(cred_model):
    """Returns a Gmail API service object."""
    credentials = get_credentials_from_model(cred_model)
    if not credentials:
        return None
    return build('gmail', 'v1', credentials=credentials)

def send_gmail_api_email(cred_model, email_obj):
    """Sends an email using the Gmail API."""
    service = get_gmail_service(cred_model)
    if not service:
        raise ValueError("Could not initialize Gmail API service.")
        
    # Get the raw message from the Django EmailMessage object
    # We need to include the MultiAlternatives content (HTML)
    raw_message = base64.urlsafe_b64encode(email_obj.message().as_bytes()).decode('utf-8')
    
    try:
        sent_message = service.users().messages().send(
            userId='me',
            body={'raw': raw_message}
        ).execute()
        return sent_message.get('id')
    except Exception as e:
        logger.error(f"Gmail API send failed for {cred_model.from_email}: {e}")
        raise e

def check_gmail_replies(cred_model):
    """Checks for replies using the Gmail API."""
    service = get_gmail_service(cred_model)
    if not service:
        return []
        
    replies = []
    try:
        # Search for messages in the last 7 days
        # We look for messages that are NOT from us
        query = f"after:{int((timezone.now() - timezone.timedelta(days=7)).timestamp())} -from:me"
        results = service.users().messages().list(userId='me', q=query).execute()
        messages = results.get('messages', [])
        
        for msg_info in messages:
            msg = service.users().messages().get(userId='me', id=msg_info['id']).execute()
            
            headers = msg.get('payload', {}).get('headers', [])
            subject = next((h['value'] for h in headers if h['name'].lower() == 'subject'), '')
            from_header = next((h['value'] for h in headers if h['name'].lower() == 'from'), '')
            msg_id = next((h['value'] for h in headers if h['name'].lower() == 'message-id'), '')
            in_reply_to = next((h['value'] for h in headers if h['name'].lower() == 'in-reply-to'), '')
            references = next((h['value'] for h in headers if h['name'].lower() == 'references'), '')
            
            # Extract body
            body = ""
            parts = msg.get('payload', {}).get('parts', [])
            if not parts:
                data = msg.get('payload', {}).get('body', {}).get('data', '')
                if data:
                    body = base64.urlsafe_b64decode(data).decode()
            else:
                for part in parts:
                    if part.get('mimeType') == 'text/plain':
                        data = part.get('body', {}).get('data', '')
                        if data:
                            body = base64.urlsafe_b64decode(data).decode()
                            break
            
            replies.append({
                'from': from_header,
                'subject': subject,
                'message_id': msg_id,
                'in_reply_to': in_reply_to,
                'references': references,
                'body': body
            })
            
    except Exception as e:
        logger.error(f"Gmail API check replies failed for {cred_model.from_email}: {e}")
        
    return replies

def render_spintax(text):
    """
    Randomly chooses options from spintax format {option1|option2|option3}.
    Works recursively for nested spintax.
    """
    import re
    import random
    
    pattern = re.compile(r'\{([^{}]*)\}')
    while True:
        match = pattern.search(text)
        if not match:
            break
        options = match.group(1).split('|')
        text = text[:match.start()] + random.choice(options) + text[match.end():]
    return text
