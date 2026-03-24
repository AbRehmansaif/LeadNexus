import time
import logging
import uuid
import imaplib
import email
from email.header import decode_header
from datetime import datetime, timedelta
from django.core.mail import get_connection, EmailMessage
from django.utils import timezone
from .models import EmailCampaign, Recipient, SMTPCredential, CampaignStep, SentEmailLog
from django.template import Template, Context
from django.conf import settings
from django.urls import reverse
from django.db import transaction
from django.db.models import Q, F
from django.core.cache import cache
from celery import shared_task, group
from admintask.utils.alerts import send_admin_alert

logger = logging.getLogger(__name__)

@shared_task(bind=True, max_retries=3)
def send_single_email_task(self, recipient_id, step_number, cred_id=None):
    """
    Atomic worker task that handles the delivery of ONE single email.
    Using transaction.atomic to ensure status and logs are updated safely.
    """
    try:
        with transaction.atomic():
            # select_for_update prevents double-sending if two workers pick up the same recipient
            recipient = Recipient.objects.select_for_update().get(id=recipient_id)
            campaign = recipient.campaign
            
            # 1. SaaS Safeguards: Skip if Replied, Paused, or Unsubscribed
            if recipient.is_replied or recipient.is_unsubscribed or campaign.status == 'paused':
                return f"Skipped: {recipient.email} (Replied, Unsubscribed, or Paused)"

            # 2. Business Hours Control (SaaS Scheduler)
            now = timezone.now()
            local_now = timezone.localtime(now)
            
            # Day Check (1=Mon...7=Sun)
            if campaign.work_days and str(local_now.isoweekday()) not in campaign.work_days.split(','):
                # Try again in 4 hours
                self.retry(countdown=14400) 

            # Hour window check
            if campaign.send_window_start and campaign.send_window_end:
                current_time = local_now.time()
                if not (campaign.send_window_start <= current_time <= campaign.send_window_end):
                    # Try again in 1 hour
                    self.retry(countdown=3600)

            # 3. Step & A/B Testing Logic
            step = CampaignStep.objects.filter(campaign=campaign, step_number=step_number).first()
            variant = 'A'
            if not step and step_number == 1:
                # Use basic campaign defaults
                step_subject = campaign.subject
                step_body = campaign.body
            elif not step:
                return f"Error: No step {step_number} found"
            else:
                # A/B Testing Selection (Simple 50/50 split)
                if step.subject_b and recipient.id % 2 == 0:
                    step_subject = step.subject_b
                    step_body = step.body_b or step.body
                    variant = 'B'
                else:
                    step_subject = step.subject
                    step_body = step.body
                    variant = 'A'

            # Use specifically assigned creds or fallback to rotation
            if cred_id:
                creds = SMTPCredential.objects.filter(id=cred_id, is_active=True).first()
            else:
                creds = SMTPCredential.objects.filter(user=campaign.user, is_active=True).order_by('?').first()

            if not creds:
                return f"Failed: No active SMTP for {recipient.email}"

            # Render content
            template = Template(step_body)
            context_data = {'name': recipient.name or recipient.email.split('@')[0], 'email': recipient.email}
            context_data.update(recipient.custom_data)
            rendered_body = template.render(Context(context_data))

            # Tracking Pixel (SaaS Feature: Custom Tracking Domain)
            profile = campaign.user.profile
            tracking_base = profile.tracking_domain or settings.SITE_URL
            if tracking_base and not tracking_base.startswith('http'):
                tracking_base = f"https://{tracking_base}"
            
            tracking_url = f"{tracking_base}{reverse('track-open', args=[recipient.id])}"
            pixel_tag = f'<img src="{tracking_url}" width="1" height="1" style="display:none !important;" />'
            rendered_body += f"\n{pixel_tag}"

            # SMTP Connection
            connection = get_connection(
                host=creds.host, port=creds.port, 
                username=creds.username, password=creds.password,
                use_tls=creds.use_tls, use_ssl=creds.use_ssl
            )

            # Headers for threading
            domain = creds.from_email.split('@')[-1]
            custom_msg_id = f"<{uuid.uuid4()}@{domain}>"
            headers = {'Message-ID': custom_msg_id}
            previous_log = recipient.delivery_logs.order_by('-sent_at').first()
            if previous_log:
                headers.update({'In-Reply-To': previous_log.message_id, 'References': previous_log.message_id})

            from_email = f"{creds.from_name} <{creds.from_email}>" if creds.from_name else creds.from_email

            # SENDING
            email_obj = EmailMessage(
                subject=step_subject, body=rendered_body,
                from_email=from_email, to=[recipient.email],
                connection=connection, headers=headers
            )
            email_obj.content_subtype = "html"
            email_obj.send()

            # Update Stats & Logs
            creds.increment_usage()
            campaign.user.profile.increment_email_usage()
            
            SentEmailLog.objects.create(
                recipient=recipient, step=step, smtp_used=creds,
                subject=step_subject, body_sent=rendered_body, message_id=custom_msg_id,
                variant_used=variant
            )

            recipient.current_step_index = step_number
            recipient.last_sent_at = timezone.now()
            recipient.status = 'active'
            recipient.save()

            # HIGH SCALE: Atomically increment campaign sent_count
            EmailCampaign.objects.filter(id=campaign.id).update(sent_count=F('sent_count') + 1)
            
            # Invalidate cache
            cache.delete(f"campaign_stats_{campaign.id}")
            
            return f"Success: {recipient.email}"

    except Exception as e:
        logger.error(f"Task Failed for {recipient_id}: {str(e)}")
        # Optional: retry on temporary SMTP network errors
        self.retry(exc=e, countdown=60, max_retries=3)

@shared_task
def send_campaign_emails(campaign_id, step_number=1):
    """
    Dispatcher: Calculates the schedule and pre-assigns accounts.
    Packs everything into Redis as small, fast, independent tasks.
    """
    campaign = EmailCampaign.objects.get(pk=campaign_id)
    
    # 1. Get eligible recipients
    if step_number == 1:
        recipients = campaign.recipients.filter(status='pending', current_step_index=0)
    else:
        recipients = campaign.recipients.filter(current_step_index=step_number - 1, is_replied=False, status='active')

    if not recipients.exists():
        if step_number == 1:
            campaign.status = 'completed'
            campaign.save(update_fields=['status'])
        return "No recipients found"

    campaign.status = 'running'
    campaign.save(update_fields=['status'])

    # 2. Setup Rotation Pool
    active_smtp = list(SMTPCredential.objects.filter(user=campaign.user, is_active=True))
    if not active_smtp:
        return "No active SMTP accounts"

    gap = max(1, campaign.gap_seconds)
    
    # 3. Dispatch independent tasks with Countdown
    for i, recipient in enumerate(recipients):
        target_creds = active_smtp[i % len(active_smtp)]
        
        send_single_email_task.apply_async(
            args=[recipient.id, step_number, target_creds.id],
            countdown=i * gap
        )
    
    return f"Campaign {campaign.name} Dispatched: {len(recipients)} tasks queued with {gap}s gap."

def trigger_followup_task(campaign_id, step_number):
    send_campaign_emails.delay(campaign_id, step_number)

@shared_task
def check_single_account_replies(cred_id):
    """Distributed worker to check IMAP for a single account."""
    try:
        cred = SMTPCredential.objects.get(id=cred_id)
        # Professional IMAP guessing
        imap_host = cred.host.replace('smtp', 'imap')
        mail = imaplib.IMAP4_SSL(imap_host)
        mail.login(cred.username, cred.password)
        mail.select("inbox")

        # Search for emails in the last 7 days
        date_since = (timezone.now() - timedelta(days=7)).strftime("%d-%b-%Y")
        _, messages = mail.search(None, f'(SINCE "{date_since}")')

        for msg_num in messages[0].split():
            _, data = mail.fetch(msg_num, '(RFC822)')
            if not data or not data[0]: continue
            
            raw_email = data[0][1]
            msg = email.message_from_bytes(raw_email)
            in_reply_to = msg.get('In-Reply-To')
            references = msg.get('References', '')
            
            # Match reply to our logs
            log = SentEmailLog.objects.filter(
                Q(message_id=in_reply_to) | Q(message_id__in=references.split())
            ).first()

            if log and not log.recipient.is_replied:
                # Detect Unsubscribe Keywords
                body_lower = ""
                if msg.is_multipart():
                    for part in msg.walk():
                        if part.get_content_type() == "text/plain":
                            body_lower = part.get_payload(decode=True).decode().lower()
                            break
                else:
                    body_lower = msg.get_payload(decode=True).decode().lower()

                unsub_keywords = ['unsubscribe', 'stop', 'remove', 'take me off', 'no thanks']
                is_unsub_request = any(kw in body_lower for kw in unsub_keywords)

                with transaction.atomic():
                    r = Recipient.objects.select_for_update().get(id=log.recipient.id)
                    
                    if is_unsub_request:
                        r.is_unsubscribed = True
                        r.unsubscribed_at = timezone.now()
                        r.status = 'unsubscribed'
                        logger.info(f"Unsubscribe detected: {r.email}")
                    else:
                        r.is_replied = True
                        r.replied_at = timezone.now()
                        r.status = 'replied'
                        # Atomic increment for reply_count
                        EmailCampaign.objects.filter(id=r.campaign.id).update(reply_count=F('reply_count') + 1)
                        logger.info(f"Reply detected: {r.email}")
                        
                    r.save()
                    cache.delete(f"campaign_stats_{r.campaign.id}")
                    
        mail.close()
        mail.logout()
        return f"Checked: {cred.from_email}"
    except Exception as e:
        logger.error(f"IMAP check failed: {e}")
        return f"Error: {str(e)}"

@shared_task
def check_for_replies():
    """Master Dispatcher: Parallelizes reply checks across multiple workers."""
    creds = SMTPCredential.objects.filter(is_active=True).values_list('id', flat=True)
    if not creds:
        return "No active accounts"
        
    from celery import group
    job = group(check_single_account_replies.s(cid) for cid in creds)
    job.apply_async()
    return f"Dispatched {len(creds)} parallel checks"

@shared_task
def start_scheduled_campaigns():
    """Background task to start campaigns that have reached their scheduled time."""
    now = timezone.now()
    campaigns = EmailCampaign.objects.filter(status='scheduled', scheduled_at__lte=now)
    for campaign in campaigns:
        campaign.status = 'running'
        campaign.save()
        send_campaign_emails.delay(campaign.id, 1)
        logger.info(f"Automatically started scheduled campaign: {campaign.name}")
