import imaplib
import email as email_lib
import email.utils
import random
import uuid
import logging
import time
from datetime import date, timedelta

from django.utils import timezone
from django.core.mail import get_connection, EmailMultiAlternatives
from celery import shared_task

from django.db import models, transaction
from .models import WarmupAccount, WarmupEmail, WarmupDailyScore, WarmupPool

logger = logging.getLogger(__name__)

# ── Content bank for natural-sounding warmup emails ──────────────────────────

WARMUP_SUBJECTS = [
    "Quick check-in",
    "Following up",
    "Hope this finds you well",
    "Just wanted to touch base",
    "A quick thought",
    "How's everything going?",
    "Catching up",
    "Quick note",
    "Reaching out",
    "How have you been?",
    "Wanted to share something",
    "Checking in briefly",
    "Brief update",
    "One thing I wanted to mention",
    "Circling back",
    "Any updates on your end?",
    "Thought of you today",
    "A quick hello",
]

WARMUP_BODIES = [
    """Hi,

Just wanted to reach out and say hello. Hope everything is going well on your end.

Let me know if there's anything I can help with.

Best regards""",

    """Hello,

Hope you're having a great week. I was thinking about our last conversation and wanted to follow up.

Looking forward to hearing from you.

Warm regards""",

    """Hi there,

Just a quick note to check in. Things have been busy on my end but wanted to make sure we stay in touch.

Hope all is well with you.

Best""",

    """Hello,

I hope this message finds you well. I've been meaning to reach out for a while now.

Would love to catch up when you have a moment.

Cheers""",

    """Hi,

Hope you're doing well. I had a few thoughts I wanted to share but also just wanted to check in.

Let's connect soon.

Kind regards""",

    """Hey,

Just a quick message to say hello and hope things are going smoothly. 

Don't hesitate to reach out if you need anything.

All the best""",

    """Hello,

I wanted to follow up on something we discussed earlier. Hope you've had a chance to think it over.

Let me know your thoughts when you get a chance.

Thanks""",
]

WARMUP_REPLIES = [
    "Thanks for reaching out! Everything is going well here. Hope the same for you.",
    "Good to hear from you! Yes, things have been busy but going well. Let's definitely catch up soon.",
    "Hi! Thanks for the message. All good here — hope you're doing well too.",
    "Great to hear from you! Yes, let's definitely stay in touch. Things are going great on my end.",
    "Thanks for checking in! Things are going great. Looking forward to catching up.",
    "Hey, thanks for the note! All is well on my end. Hope you're having a great week.",
    "Hi! Yes, absolutely — things have been great. Thanks for thinking of me!",
]


# ── Placement & Send helpers (SMTP vs Gmail API) ─────────────────────────────

def _send_email_generalized(account, creds, to_email, subject, body_text, headers=None):
    """Abstraction to send via SMTP or Gmail API."""
    from mail.utils import send_gmail_api_email

    domain = creds.from_email.split('@')[-1]
    msg_id = headers.get('Message-ID') if headers else f"<wm-{uuid.uuid4()}@{domain}>"

    # Digital Fingerprint for tracking (hidden in body)
    fingerprint = f"\n\n--\nLN-WU-ID:[{msg_id}]"
    body_with_id = body_text + fingerprint

    from_email = f"{creds.from_name} <{creds.from_email}>" if creds.from_name else creds.from_email
    html_body = f"<p style='font-family:Arial,sans-serif;line-height:1.6'>{body_text.replace(chr(10), '<br>')}</p>"
    html_body += f"<div style='display:none;color:transparent;opacity:0'>Fingerprint: {msg_id}</div>"

    msg = EmailMultiAlternatives(
        subject=subject,
        body=body_with_id,
        from_email=from_email,
        to=[to_email],
        headers=headers or {'Message-ID': msg_id, 'X-Mailer': 'LeadNexus-Warmup/1.0'},
    )
    msg.attach_alternative(html_body, 'text/html')

    if creds.auth_type == 'oauth':
        # Ensure we return the Header ID, not the Gmail Internal ID
        send_gmail_api_email(creds, msg)
        return msg_id
    else:
        connection = get_connection(
            host=creds.host, port=creds.port,
            username=creds.username, password=creds.decrypted_password,
            use_tls=creds.use_tls, use_ssl=creds.use_ssl,
        )
        msg.connection = connection
        msg.send()
        return msg_id


# ── Ramp-up schedule ─────────────────────────────────────────────────────────

def calculate_daily_volume(day: int, max_volume: int = 50) -> int:
    """Gradual ramp-up: low start → steady build over 30 days."""
    if day <= 2:
        return 3
    elif day <= 5:
        return 6
    elif day <= 9:
        return 12
    elif day <= 14:
        return 20
    elif day <= 20:
        return 30
    elif day <= 25:
        return min(max_volume, 40)
    else:
        return min(max_volume, 50)


# ── IMAP helpers ─────────────────────────────────────────────────────────────

def _imap_host_for(creds):
    """Derive IMAP host from SMTP host or email domain."""
    if creds.host:
        # Common: smtp.gmail.com → imap.gmail.com
        derived = creds.host.replace('smtp.', 'imap.').replace('smtp-', 'imap.')
        if derived != creds.host:
            return derived
    email_domain = creds.from_email.split('@')[-1].lower()
    if 'gmail' in email_domain:
        return 'imap.gmail.com'
    if 'outlook' in email_domain or 'hotmail' in email_domain or 'live' in email_domain:
        return 'outlook.office365.com'
    if 'yahoo' in email_domain:
        return 'imap.mail.yahoo.com'
    return None


def get_imap_conn(creds):
    """Open an authenticated IMAP4_SSL connection or return None on failure."""
    host = _imap_host_for(creds)
    if not host:
        logger.warning(f"Cannot derive IMAP host for {creds.from_email}")
        return None
    try:
        mail = imaplib.IMAP4_SSL(host, 993)
        mail.login(creds.username or creds.from_email, creds.decrypted_password)
        return mail
    except Exception as exc:
        logger.error(f"IMAP login failed for {creds.from_email}: {exc}")
        return None


def _detect_spam_folder(mail):
    """Return the spam/junk folder name or None."""
    candidates = [
        '[Gmail]/Spam', 'Spam', 'Junk', 'Junk E-mail',
        'INBOX.Spam', 'INBOX.Junk', '[Gmail]/Junk',
        'Junk Mail', 'Bulk Mail',
    ]
    try:
        _, folder_list = mail.list()
        names = [f.decode() if isinstance(f, bytes) else f for f in (folder_list or [])]
        for candidate in candidates:
            for name in names:
                if candidate.lower() in name.lower():
                    return candidate
    except Exception:
        pass
    return None


# ── Celery tasks ──────────────────────────────────────────────────────────────

@shared_task
def run_warmup_cycle():
    """Master task: runs once daily, fans out to per-account workers."""
    accounts = WarmupAccount.objects.filter(status='warming').select_related('smtp_credential')
    queued = 0
    for acc in accounts:
        run_single_account_warmup.delay(acc.id)
        queued += 1
    return f"Queued warmup for {queued} accounts"


@shared_task
def run_single_account_warmup(account_id: int):
    """Full warmup cycle for one account: check → reply → send → score."""
    try:
        account = WarmupAccount.objects.select_related(
            'smtp_credential', 'user'
        ).get(id=account_id)
    except WarmupAccount.DoesNotExist:
        return f"Account {account_id} not found"

    if account.status != 'warming':
        return f"Skipped {account_id}: status={account.status}"

    creds = account.smtp_credential

    # Step 1: Check Placements (Inbox vs Spam)
    if creds.auth_type == 'oauth':
        _check_placements_gmail_api(account, creds)
    else:
        _check_placements_imap(account, creds)

    # Step 2: Auto-reply
    if creds.auth_type == 'oauth':
        _send_auto_replies_gmail_api(account, creds)
    else:
        _send_auto_replies_imap(account, creds)

    # Step 3: Calculate today's volume and targets
    day = account.day_number + 1
    volume = calculate_daily_volume(day, account.max_daily_volume)
    targets = _get_targets(account)

    # Step 4: Send warmup emails
    sent_count = 0
    if targets:
        for i in range(min(volume, len(targets) * 5)):
            target = targets[i % len(targets)]
            if target.lower() == creds.from_email.lower():
                continue
            try:
                subject = random.choice(WARMUP_SUBJECTS)
                body = random.choice(WARMUP_BODIES)
                msg_id = _send_email_generalized(account, creds, target, subject, body)

                # Robust creation: save immediately and update counter
                WarmupEmail.objects.create(
                    account=account, to_email=target, subject=subject, message_id=msg_id
                )
                WarmupAccount.objects.filter(pk=account.pk).update(
                    total_sent=models.F('total_sent') + 1,
                    last_run_at=timezone.now()
                )
                sent_count += 1
                time.sleep(random.uniform(10, 30))
            except Exception as exc:
                logger.error(f"Warmup send failed ({creds.from_email}→{target}): {exc}")

    # Final sync
    account.refresh_from_db()
    account.day_number = day
    account.current_daily_volume = volume
    if day >= account.target_days:
        account.status = 'warmed'
    account.warmup_score = account.calculate_score()
    account.save()

    # Step 6: Daily snapshot
    WarmupDailyScore.objects.update_or_create(
        account=account, date=date.today(),
        defaults={
            'day_number': day, 'score': account.warmup_score,
            'inbox_rate': account.inbox_rate, 'spam_rate': account.spam_rate,
            'reply_rate': account.reply_rate, 'emails_sent': sent_count,
            'volume': volume,
        },
    )

    return (
        f"Warmup complete: {creds.from_email} | Day {day} | "
        f"Sent {sent_count} | Score {account.warmup_score}"
    )


def _get_targets(account) -> list:
    """Collect warmup target emails (other user accounts + pool)."""
    from mail.models import SMTPCredential
    targets = list(
        SMTPCredential.objects
        .filter(user=account.user)
        .exclude(id=account.smtp_credential_id)
        .values_list('from_email', flat=True)
    )
    pool_emails = list(
        WarmupPool.objects
        .filter(user=account.user, is_active=True)
        .exclude(email__in=targets)
        .values_list('email', flat=True)
    )
    targets.extend(pool_emails)
    random.shuffle(targets)
    return targets


def _send_warmup_email(account, creds, to_email: str):
    """Send one warmup email and log it."""
    subject = random.choice(WARMUP_SUBJECTS)
    body_text = random.choice(WARMUP_BODIES)
    domain = creds.from_email.split('@')[-1]
    msg_id = f"<wm-{uuid.uuid4()}@{domain}>"

    connection = get_connection(
        host=creds.host, port=creds.port,
        username=creds.username, password=creds.decrypted_password,
        use_tls=creds.use_tls, use_ssl=creds.use_ssl,
    )
    from_email = f"{creds.from_name} <{creds.from_email}>" if creds.from_name else creds.from_email
    html_body = f"<p style='font-family:Arial,sans-serif;line-height:1.6'>{body_text.replace(chr(10), '<br>')}</p>"

    msg = EmailMultiAlternatives(
        subject=subject,
        body=body_text,
        from_email=from_email,
        to=[to_email],
        connection=connection,
        headers={
            'Message-ID': msg_id,
            'X-Mailer': 'LeadNexus-Warmup/1.0',
        },
    )
    msg.attach_alternative(html_body, 'text/html')
    msg.send()

    WarmupEmail.objects.create(
        account=account,
        to_email=to_email,
        subject=subject,
        message_id=msg_id,
    )
    account.total_sent = WarmupEmail.objects.filter(account=account).count()
    account.save(update_fields=['total_sent'])


# ── IMAP Implementation (Standard SMTP) ───────────────────────────────────────

def _check_placements_imap(account, creds):
    mail = get_imap_conn(creds)
    if not mail: return
    try:
        # Check Inbox
        mail.select('INBOX')
        # Broad search for the fingerprint
        _, data = mail.search(None, '(BODY "LN-WU-ID:[")')
        for mid in (data[0].split() if data[0] else []):
            _verify_and_update_sender(mail, mid, is_spam=False)

        # Fallback search for the header
        _, hdata = mail.search(None, '(HEADER X-Mailer LeadNexus-Warmup/1.0)')
        for mid in (hdata[0].split() if hdata[0] else []):
            _verify_and_update_sender(mail, mid, is_spam=False)

        # Check Spam
        spam_folder = _detect_spam_folder(mail)
        if spam_folder:
            mail.select(spam_folder)
            _, sdata = mail.search(None, '(OR BODY "LN-WU-ID:[" HEADER X-Mailer LeadNexus-Warmup/1.0)')
            for mid in (sdata[0].split() if sdata[0] else []):
                _verify_and_update_sender(mail, mid, is_spam=True)
                # Move to inbox
                mail.copy(mid, 'INBOX')
                mail.store(mid, '+FLAGS', '\\Deleted')
            if sdata[0]: mail.expunge()
    except Exception as e: logger.error(f"IMAP check error for {creds.from_email}: {e}")
    finally:
        try: mail.logout()
        except: pass

def _verify_and_update_sender(mail_conn, imap_mid, is_spam=False):
    """Helper to extract ID from email and update SENDER's stats."""
    import re
    try:
        _, raw = mail_conn.fetch(imap_mid, '(BODY.PEEK[])')
        parsed = email_lib.message_from_bytes(raw[0][1])
        
        body_text = ""
        for part in parsed.walk():
            if part.get_content_type() in ["text/plain", "text/html"]:
                payload = part.get_payload(decode=True)
                if payload:
                    body_text += payload.decode(errors='ignore')

        # Find fingerprint LN-WU-ID:[...]
        match = re.search(r'LN-WU-ID:\[(.*?)\]', body_text)
        if match:
            fingerprint_id = match.group(1).strip('<>')
            # Search for the fingerprint ID anywhere in the message_id field
            # Use Q to handle both full ID and UUID prefix
            w_email = WarmupEmail.objects.filter(
                models.Q(message_id__icontains=fingerprint_id) | 
                models.Q(message_id__icontains=fingerprint_id.split('@')[0])
            ).first()
            
            if w_email and w_email.placement == 'unknown':
                w_email.placement = 'spam' if is_spam else 'inbox'
                w_email.checked_at = timezone.now()
                w_email.save()
                # Update the SENDER's account stats
                w_email.account.add_placement_result(is_spam=is_spam)
                logger.info(f"Verified placement for {w_email.account.smtp_credential.from_email}: {w_email.placement}")
    except Exception as e:
        logger.error(f"Error in _verify_and_update_sender: {e}")

def _send_auto_replies_imap(account, creds):
    mail = get_imap_conn(creds)
    if not mail: return
    try:
        mail.select('INBOX')
        # Search for unseen warmup emails using fingerprint
        _, data = mail.search(None, '(UNSEEN BODY "LN-WU-ID:[")')
        msg_ids = data[0].split() if data[0] else []
        for mid in msg_ids[:5]:
            _, raw = mail.fetch(mid, '(BODY.PEEK[])')
            parsed = email_lib.message_from_bytes(raw[0][1])
            from_addr = email_lib.utils.parseaddr(parsed.get('From', ''))[1]
            orig_msg_id = parsed.get('Message-ID', '')
            if not from_addr or from_addr.lower() == creds.from_email.lower(): continue
            
            _send_email_generalized(account, creds, from_addr, f"Re: {parsed.get('Subject','')}", 
                                    random.choice(WARMUP_REPLIES), 
                                    headers={'In-Reply-To': orig_msg_id, 'References': orig_msg_id, 'X-Mailer': 'LeadNexus-Warmup/1.0'})
            mail.store(mid, '+FLAGS', '\\Seen')
            WarmupAccount.objects.filter(pk=account.pk).update(reply_count=account.reply_count + 1)
    except Exception as e: logger.error(f"IMAP reply error for {creds.from_email}: {e}")
    finally:
        try: mail.logout()
        except: pass


# ── Gmail API Implementation (OAuth) ──────────────────────────────────────────

def _check_placements_gmail_api(account, creds):
    from mail.utils import get_gmail_service
    service = get_gmail_service(creds)
    if not service: return
    try:
        # Search for any emails containing our fingerprint ID
        query = '"LN-WU-ID:["'
        results = service.users().messages().list(userId='me', q=query).execute()
        
        for msg_info in results.get('messages', []):
            msg = service.users().messages().get(userId='me', id=msg_info['id'], format='full').execute()
            
            # Check if it's in SPAM
            is_spam = 'SPAM' in msg.get('labelIds', [])
            
            # Look for fingerprint in snippet or body parts
            import re
            full_text = msg.get('snippet', '')
            
            # Deep search in parts
            def get_parts_text(parts):
                text = ""
                for p in parts:
                    if p.get('mimeType') in ['text/plain', 'text/html']:
                        data = p.get('body', {}).get('data', '')
                        if data:
                            import base64
                            text += base64.urlsafe_b64decode(data).decode(errors='ignore')
                    if 'parts' in p:
                        text += get_parts_text(p['parts'])
                return text

            full_text += get_parts_text(msg.get('payload', {}).get('parts', []))
            
            match = re.search(r'LN-WU-ID:\[(.*?)\]', full_text)
            if match:
                fingerprint_id = match.group(1).strip('<>')
                w_email = WarmupEmail.objects.filter(
                    models.Q(message_id__icontains=fingerprint_id) |
                    models.Q(message_id__icontains=fingerprint_id.split('@')[0])
                ).first()
                
                if w_email and w_email.placement == 'unknown':
                    w_email.placement = 'spam' if is_spam else 'inbox'
                    w_email.checked_at = timezone.now()
                    w_email.save()
                    w_email.account.add_placement_result(is_spam=is_spam)
                    
                    if is_spam:
                        # Move to inbox (The core warmup action)
                        service.users().messages().modify(userId='me', id=msg_info['id'], body={
                            'removeLabelIds': ['SPAM'],
                            'addLabelIds': ['INBOX']
                        }).execute()
    except Exception as e: 
        logger.error(f"Gmail API check error for {creds.from_email}: {e}")

def _send_auto_replies_gmail_api(account, creds):
    from mail.utils import get_gmail_service
    service = get_gmail_service(creds)
    if not service: return
    try:
        # Search for unread fingerprints
        query = 'is:unread "LN-WU-ID:["'
        results = service.users().messages().list(userId='me', q=query).execute()
        msgs = results.get('messages', [])[:5]

        for m in msgs:
            msg = service.users().messages().get(userId='me', id=m['id']).execute()
            headers = msg.get('payload', {}).get('headers', [])
            from_addr = next((h['value'] for h in headers if h['name'].lower() == 'from'), '')
            orig_id = next((h['value'] for h in headers if h['name'].lower() == 'message-id'), '')
            subj = next((h['value'] for h in headers if h['name'].lower() == 'subject'), '')
            
            if creds.from_email.lower() in from_addr.lower(): continue

            _send_email_generalized(account, creds, from_addr, f"Re: {subj}", 
                                    random.choice(WARMUP_REPLIES),
                                    headers={'In-Reply-To': orig_id, 'References': orig_id, 'X-Mailer': 'LeadNexus-Warmup/1.0'})
            
            # Mark as read
            service.users().messages().modify(userId='me', id=m['id'], body={'removeLabelIds': ['UNREAD']}).execute()
            WarmupAccount.objects.filter(pk=account.pk).update(reply_count=account.reply_count + 1)
    except Exception as e: logger.error(f"Gmail API reply error for {creds.from_email}: {e}")
