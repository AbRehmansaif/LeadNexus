import time
import logging
import threading
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
from django.db.models import Q

logger = logging.getLogger(__name__)

def send_campaign_emails(campaign_id, step_number=1):
    """
    Background task to send emails for a specific campaign step.
    Supports initial launch (Step 1) and manual follow-ups (Step 2+).
    Rotates through active SMTP credentials and logs message-IDs for tracking.
    """
    try:
        campaign = EmailCampaign.objects.get(pk=campaign_id)
        
        # Determine the step to send
        step = campaign.steps.filter(step_number=step_number).first()
        
        # Fallback if no CampaignStep exists, use Campaign's default subject/body
        step_subject = step.subject if step else campaign.subject
        step_body = step.body if step else campaign.body

        # Get eligible recipients for THIS specific step
        if step_number == 1:
            # Step 1: Any pending recipient
            recipients = campaign.recipients.filter(status='pending', current_step_index=0)
        else:
            # Step 2+: Must have completed previous step, not replied, and wait time passed
            # Note: Since it's a manual trigger, we assume the user already checked wait time,
            # but we still filter for those who haven't replied.
            recipients = campaign.recipients.filter(
                current_step_index=step_number - 1,
                is_replied=False,
                status='active'
            )

        if not recipients.exists():
            logger.info(f"No eligible recipients for step {step_number} in campaign {campaign_id}")
            # Mark as completed if all step-1 recipients are done
            if step_number == 1:
                campaign.status = 'completed'
                campaign.save(update_fields=['status'])
            return

        # Mark campaign as running
        campaign.status = 'running'
        campaign.save(update_fields=['status'])

        # Get all SMTP credentials for THIS user
        all_smtp_credentials = list(SMTPCredential.objects.filter(user=campaign.user, is_active=True))
        if not all_smtp_credentials:
            logger.error(f"No active SMTP credentials for campaign {campaign_id}")
            return

        # Pre-check limits
        for cred in all_smtp_credentials:
            cred.check_and_reset_limit()

        smtp_index = 0
        user_profile = campaign.user.profile

        for recipient in recipients:
            # Check Global Quota
            if not user_profile.can_send_email():
                logger.error(f"User {campaign.user.username} reached monthly quota.")
                break

            # Check SMTP rotation
            active_smtp = [c for c in all_smtp_credentials if c.is_active]
            if not active_smtp:
                logger.error(f"All SMTP accounts reached daily limits.")
                break

            creds = active_smtp[smtp_index % len(active_smtp)]
            smtp_index += 1

            try:
                # Render content
                template = Template(step_body)
                context_data = {
                    'name': recipient.name or recipient.email.split('@')[0],
                    'email': recipient.email,
                }
                context_data.update(recipient.custom_data)
                rendered_body = template.render(Context(context_data))

                # Tracking Pixel
                tracking_url = f"{settings.SITE_URL}{reverse('track-open', args=[recipient.id])}"
                pixel_tag = f'<img src="{tracking_url}" width="1" height="1" style="display:none !important;" />'
                rendered_body += f"\n{pixel_tag}"

                # Connection
                connection = get_connection(
                    host=creds.host, port=creds.port, 
                    username=creds.username, password=creds.password,
                    use_tls=creds.use_tls, use_ssl=creds.use_ssl
                )

                # Custom Message-ID for threading and reply detection
                domain = creds.from_email.split('@')[-1]
                custom_msg_id = f"<{uuid.uuid4()}@{domain}>"
                
                # Headers for threading: If it's a follow-up, reference the previous log
                headers = {'Message-ID': custom_msg_id}
                previous_log = recipient.delivery_logs.order_by('-sent_at').first()
                if previous_log:
                    headers['In-Reply-To'] = previous_log.message_id
                    headers['References'] = previous_log.message_id

                from_email = f"{creds.from_name} <{creds.from_email}>" if creds.from_name else creds.from_email

                email_obj = EmailMessage(
                    subject=step_subject,
                    body=rendered_body,
                    from_email=from_email,
                    to=[recipient.email],
                    connection=connection,
                    headers=headers
                )
                email_obj.content_subtype = "html"
                email_obj.send()

                # Update Stats
                creds.increment_usage()
                user_profile.increment_email_usage()

                # Save Log
                SentEmailLog.objects.create(
                    recipient=recipient,
                    step=step,
                    smtp_used=creds,
                    subject=step_subject,
                    body_sent=rendered_body,
                    message_id=custom_msg_id
                )

                # Update Recipient State
                recipient.current_step_index = step_number
                recipient.last_sent_at = timezone.now()
                recipient.status = 'active'
                recipient.smtp_email = creds.from_email  # track which account sent
                recipient.save()

                campaign.sent_count += 1
                campaign.save(update_fields=['sent_count'])

                if campaign.gap_seconds > 0:
                    time.sleep(campaign.gap_seconds)

            except Exception as e:
                logger.exception(f"Failed to send to {recipient.email}")
                recipient.status = 'failed'
                recipient.error_message = str(e)
                recipient.save()

        # After loop: mark campaign as completed
        campaign.refresh_from_db()
        campaign.status = 'completed'
        campaign.save(update_fields=['status'])

    except Exception as e:
        logger.exception(f"Error in campaign task: {e}")

def trigger_followup_task(campaign_id, step_number):
    """Entry point for manual follow-up triggers."""
    t = threading.Thread(target=send_campaign_emails, args=(campaign_id, step_number), daemon=True)
    t.start()

def check_for_replies():
    """
    Poller to check all active SMTP/IMAP accounts for replies.
    Match replies to recipients using In-Reply-To headers.
    """
    credentials = SMTPCredential.objects.filter(is_active=True).distinct()
    for cred in credentials:
        try:
            # Guessing IMAP host (usually imap.gmail.com if host is smtp.gmail.com)
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
                
                # Look for matching Message-ID in our logs
                log = SentEmailLog.objects.filter(
                    Q(message_id=in_reply_to) | Q(message_id__in=references.split())
                ).first()

                if log:
                    recipient = log.recipient
                    if not recipient.is_replied:
                        recipient.is_replied = True
                        recipient.replied_at = timezone.now()
                        recipient.status = 'replied'
                        recipient.save()
                        logger.info(f"Reply detected for {recipient.email} in {recipient.campaign.name}")

            mail.close()
            mail.logout()
        except Exception as e:
            logger.error(f"Reply check failed for {cred.from_email}: {e}")
