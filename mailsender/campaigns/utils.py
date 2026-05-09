import base64
from email.mime.text import MIMEText
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from accounts.utils import decrypt_value
from .models import Campaign, Lead, EmailLog
from accounts.models import GmailAccount
from django.utils import timezone
import json

def get_gmail_service(account):
    creds = Credentials(
        token=decrypt_value(account.access_token),
        refresh_token=decrypt_value(account.refresh_token),
        token_uri=account.token_uri,
        client_id=account.client_id,
        client_secret=account.client_secret,
        scopes=json.loads(account.scopes)
    )
    return build('gmail', 'v1', credentials=creds)

def send_gmail_email(service, to, subject, body):
    message = MIMEText(body)
    message['to'] = to
    message['subject'] = subject
    
    raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
    
    try:
        sent_message = service.users().messages().send(userId='me', body={'raw': raw}).execute()
        return sent_message['id'], None
    except Exception as e:
        return None, str(e)

def run_campaign(campaign_id):
    campaign = Campaign.objects.get(id=campaign_id)
    leads = Lead.objects.filter(campaign=campaign, status='pending')
    accounts = list(GmailAccount.objects.filter(user=campaign.user))
    
    if not accounts:
        return "No Gmail accounts connected."

    account_index = 0
    total_sent = 0
    
    for lead in leads:
        account = accounts[account_index]
        service = get_gmail_service(account)
        
        # Simple body replacement for customization
        body = campaign.body.replace("{{first_name}}", lead.first_name)
        
        msg_id, error = send_gmail_email(service, lead.email, campaign.subject, body)
        
        if msg_id:
            lead.status = 'sent'
            lead.save()
            EmailLog.objects.create(
                campaign=campaign,
                gmail_account=account,
                lead=lead,
                status='sent',
                message_id=msg_id
            )
            total_sent += 1
        else:
            lead.status = 'failed'
            lead.error_message = error
            lead.save()
            EmailLog.objects.create(
                campaign=campaign,
                gmail_account=account,
                lead=lead,
                status='failed'
            )

        # Rotate account
        account_index = (account_index + 1) % len(accounts)
    
    return f"Campaign finished. Sent {total_sent} emails."
