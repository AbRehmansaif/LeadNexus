import time
import logging
import threading
from datetime import datetime
from django.core.mail import get_connection, EmailMessage
from django.utils import timezone
from .models import EmailCampaign, Recipient, SMTPCredential
from django.template import Template, Context

logger = logging.getLogger(__name__)

def send_campaign_emails(campaign_id):
    """
    Background task to send emails for a campaign.
    Rotates through active SMTP credentials.
    Respects the gap_minutes setting.
    """
    try:
        campaign = EmailCampaign.objects.get(pk=campaign_id)
        if campaign.status == 'running':
            logger.info(f"Campaign {campaign_id} is already running.")
            return
        
        campaign.status = 'running'
        campaign.save(update_fields=['status'])

        # Get all pending recipients
        recipients = campaign.recipients.filter(status='pending')
        
        # Get all active SMTP credentials
        smtp_credentials = list(SMTPCredential.objects.filter(is_active=True))
        if not smtp_credentials:
            campaign.status = 'failed'
            campaign.save(update_fields=['status'])
            logger.error(f"No active SMTP credentials found for campaign {campaign_id}")
            return

        smtp_count = len(smtp_credentials)
        smtp_index = 0

        for recipient in recipients:
            # Re-fetch campaign status to allow pausing/stopping
            campaign.refresh_from_db()
            if campaign.status != 'running':
                logger.info(f"Campaign {campaign_id} stopped or paused.")
                break

            # Select SMTP credential (rotate)
            creds = smtp_credentials[smtp_index % smtp_count]
            smtp_index += 1

            try:
                # Prepare email content with placeholders
                template = Template(campaign.body)
                context_data = {
                    'name': recipient.name or recipient.email.split('@')[0],
                    'email': recipient.email,
                }
                if recipient.custom_data:
                    context_data.update(recipient.custom_data)
                
                context = Context(context_data)
                rendered_body = template.render(context)

                # Setup connection
                connection = get_connection(
                    host=creds.host,
                    port=creds.port,
                    username=creds.username,
                    password=creds.password,
                    use_tls=creds.use_tls,
                    use_ssl=creds.use_ssl,
                )

                # Create email
                email = EmailMessage(
                    subject=campaign.subject,
                    body=rendered_body,
                    from_email=creds.from_email,
                    to=[recipient.email],
                    connection=connection,
                )
                
                # Send
                email.send()

                # Update recipient
                recipient.status = 'sent'
                recipient.sent_at = timezone.now()
                recipient.save()

                # Update campaign counts
                campaign.sent_count += 1
                campaign.save(update_fields=['sent_count'])

            except Exception as e:
                logger.exception(f"Failed to send email to {recipient.email} using {creds.name}")
                recipient.status = 'failed'
                recipient.error_message = str(e)
                recipient.save()
                
                campaign.failed_count += 1
                campaign.save(update_fields=['failed_count'])

            # Gap between emails
            if campaign.gap_minutes > 0:
                time.sleep(campaign.gap_minutes * 60)

        # Mark campaign as completed if all done
        if not campaign.recipients.filter(status='pending').exists():
            campaign.status = 'completed'
            campaign.save(update_fields=['status'])

    except Exception as e:
        logger.exception(f"Critical error in campaign {campaign_id}")
        EmailCampaign.objects.filter(pk=campaign_id).update(status='failed')

def start_campaign_async(campaign_id):
    """Start the campaign in a background thread."""
    t = threading.Thread(target=send_campaign_emails, args=(campaign_id,), daemon=True)
    t.start()
