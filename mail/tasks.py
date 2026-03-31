import logging
import uuid
import imaplib
import email
from email.header import decode_header
from datetime import timedelta
from django.core.mail import get_connection, EmailMessage
from django.utils import timezone
from .models import EmailCampaign, Recipient, SMTPCredential, CampaignStep, SentEmailLog
from core.models import UserProfile
from django.template import Template, Context
from django.conf import settings
from django.urls import reverse
from django.db import transaction
from django.db.models import Q, F
from django.core.cache import cache
from celery import shared_task, group

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3)
def send_single_email_task(self, recipient_id, step_number, cred_id=None):
    """
    Three-phase email delivery task.

    PHASE 1 (atomic): Pre-flight checks — validate recipient state, business hours,
                      quota, resolve step/creds, render body. NO email sent yet.
                      Business-hours deferral uses apply_async (NOT self.retry)
                      so it never consumes the error retry counter.

    PHASE 2 (outside transaction): email_obj.send()
                      SMTP is external/irreversible. We deliberately keep this
                      outside any DB transaction so a DB hiccup in Phase 3/4 can
                      NEVER roll back a sent email or cause a 'failed' status.

    PHASE 3 (new atomic): Immediately after a successful send update recipient
                      status to 'active'. This is a tiny fast write — isolated
                      from stats so nothing can revert it.

    PHASE 4 (best-effort): Stats / logs / cache. Failures here are logged but
                      DO NOT affect the recipient status — the email is already
                      delivered and the recipient is already 'active'.
    """

    # ─────────────────────────────────────────────────────────────────────────
    # PHASE 1 — Pre-flight (reads + validation, zero DB writes)
    # ─────────────────────────────────────────────────────────────────────────
    try:
        # We still use select_for_update to prevent double-sending between
        # concurrent workers, but the lock is released as soon as Phase 1 exits.
        with transaction.atomic():
            recipient = Recipient.objects.select_for_update().get(id=recipient_id)
            campaign = recipient.campaign

            # Guard: already processed or in a terminal state for this step
            if recipient.is_replied or recipient.is_unsubscribed or campaign.status == 'paused':
                return f"Skipped: {recipient.email} (Replied, Unsubscribed, or Paused)"

            # Business Hours Check — use apply_async NOT self.retry so we
            # don't burn the precious max_retries=3 SMTP error budget.
            now = timezone.now()
            local_now = timezone.localtime(now)

            if campaign.work_days and str(local_now.isoweekday()) not in campaign.work_days.split(','):
                send_single_email_task.apply_async(
                    args=[recipient_id, step_number, cred_id],
                    countdown=14400  # retry in 4 hours
                )
                return f"Deferred: {recipient.email} — not a configured work day"

            if campaign.send_window_start and campaign.send_window_end:
                current_time = local_now.time()
                if not (campaign.send_window_start <= current_time <= campaign.send_window_end):
                    send_single_email_task.apply_async(
                        args=[recipient_id, step_number, cred_id],
                        countdown=3600  # retry in 1 hour
                    )
                    return f"Deferred: {recipient.email} — outside send window"

            # Step & A/B Logic
            step = CampaignStep.objects.filter(campaign=campaign, step_number=step_number).first()
            variant = 'A'
            if not step and step_number == 1:
                step_subject = campaign.subject
                step_body = campaign.body
                step = None
            elif not step:
                return f"Error: No step {step_number} found for campaign {campaign.id}"
            else:
                if step.subject_b and recipient.id % 2 == 0:
                    step_subject = step.subject_b
                    step_body = step.body_b or step.body
                    variant = 'B'
                else:
                    step_subject = step.subject
                    step_body = step.body
                    variant = 'A'

            # Monthly Quota Guard
            profile = campaign.user.profile
            if not profile.can_send_email():
                logger.warning(f"Quota exceeded for {campaign.user.username}, skipping {recipient.email}")
                return f"Skipped: {recipient.email} (Monthly email quota exceeded)"

            # SMTP Selection
            if cred_id:
                creds = SMTPCredential.objects.filter(id=cred_id, is_active=True).first()
            else:
                creds = SMTPCredential.objects.filter(user=campaign.user, is_active=True).order_by('?').first()

            if not creds:
                return f"Failed: No active SMTP account available for {recipient.email}"

            # Render body template and convert to professional HTML
            from django.utils.html import linebreaks
            
            tmpl = Template(step_body)
            context_data = {
                'name': recipient.name or recipient.email.split('@')[0],
                'email': recipient.email,
            }
            context_data.update(recipient.custom_data)
            
            # Step 1: Substitution
            interim_body = tmpl.render(Context(context_data))
            # Step 2: SaaS-level Text to HTML (Spacing, Paragraphs, Gaps)
            rendered_body = linebreaks(interim_body)

            # Tracking Pixel
            # Logic: Use user's tracking_domain if set, otherwise fallback to SITE_URL.
            # Ensure the domain ends up with a valid protocol (https preferred) and no trailing slash.
            profile = campaign.user.profile
            tracking_base = profile.tracking_domain or settings.SITE_URL
            
            if tracking_base:
                tracking_base = tracking_base.strip()
                # 1. Ensure protocol exists
                if not tracking_base.startswith(('http://', 'https://')):
                    tracking_base = f"https://{tracking_base}"
                
                # 2. If it's http and SSL is required, upgrade to https
                elif tracking_base.startswith('http://') and getattr(settings, 'SECURE_SSL_REDIRECT', False):
                    tracking_base = 'https://' + tracking_base[7:]
                
                # 3. Remove trailing slash for reverse suffixing
                tracking_base = tracking_base.rstrip('/')
            
            # Unsubscribe Link
            unsub_url = f"{tracking_base.rstrip('/')}{reverse('unsubscribe', args=[recipient.id])}"
            unsub_footer = f'<br><br><div style="font-size: 11px; color: #666; border-top: 1px dashed #eee; padding-top: 10px;">' \
                           f'Too many emails? <a href="{unsub_url}" style="color: #8b5cf6; text-decoration: underline;">Unsubscribe from this campaign</a>' \
                           f'</div>'
            rendered_body += f"\n{unsub_footer}"

            # Tracking Pixel
            tracking_url = f"{tracking_base}{reverse('track-open', args=[recipient.id])}"
            pixel_tag = f'<img src="{tracking_url}" width="1" height="1" style="display:none !important;" />'
            rendered_body += f"\n{pixel_tag}"

            # Build connection & headers (no side effects yet)
            connection = get_connection(
                host=creds.host, port=creds.port,
                username=creds.username, password=creds.decrypted_password,
                use_tls=creds.use_tls, use_ssl=creds.use_ssl
            )
            domain = creds.from_email.split('@')[-1]
            custom_msg_id = f"<{uuid.uuid4()}@{domain}>"
            headers = {'Message-ID': custom_msg_id}
            previous_log = recipient.delivery_logs.order_by('-sent_at').first()
            if previous_log:
                headers.update({
                    'In-Reply-To': previous_log.message_id,
                    'References': previous_log.message_id,
                })
            from_email = f"{creds.from_name} <{creds.from_email}>" if creds.from_name else creds.from_email

            # Build the email object (not sent yet)
            email_obj = EmailMessage(
                subject=step_subject, body=rendered_body,
                from_email=from_email, to=[recipient.email],
                connection=connection, headers=headers
            )
            email_obj.content_subtype = "html"

            # Capture IDs we need after the transaction closes
            campaign_id = campaign.id
            creds_id = creds.id
            step_id = step.id if step else None
            user_id = campaign.user.id

        # ── End of Phase 1 atomic block ───────────────────────────────────────
        # The select_for_update lock is released here. All variables above
        # (email_obj, creds, step_subject, rendered_body, ...) are in memory.

    except Exception as preflight_error:
        # Pre-flight DB error (e.g. recipient not found, DB connection lost).
        # Safe to retry — no email has been sent yet.
        logger.error(f"Pre-flight error for recipient {recipient_id}: {preflight_error}")
        try:
            raise self.retry(exc=preflight_error, countdown=30)
        except self.MaxRetriesExceededError:
            logger.error(f"Pre-flight max retries exhausted for recipient {recipient_id}.")
            _mark_failed(recipient_id, f"Pre-flight error: {preflight_error}")

        return  # stop execution after handling

    # ─────────────────────────────────────────────────────────────────────────
    # PHASE 2 — Send email (OUTSIDE any DB transaction)
    # SMTP is external and irreversible. Keeping this outside any atomic block
    # means no DB rollback can ever "un-send" a delivered email or trigger
    # a false 'failed' status due to a subsequent DB error.
    # ─────────────────────────────────────────────────────────────────────────
    try:
        email_obj.send()
    except Exception as smtp_error:
        # Genuine SMTP failure — safe to retry (email was NOT sent)
        logger.error(f"SMTP error for {recipient_id}: {smtp_error}")
        try:
            raise self.retry(exc=smtp_error, countdown=60)
        except self.MaxRetriesExceededError:
            logger.error(f"SMTP max retries exhausted for recipient {recipient_id}.")
            _mark_failed(recipient_id, f"SMTP delivery failed: {smtp_error}")

        return  # stop execution after handling

    # ─────────────────────────────────────────────────────────────────────────
    # PHASE 3 — Mark recipient as 'active' or 'completed' (new, tiny atomic block)
    # This is the ONLY critical DB write. It is completely isolated from stats.
    # Nothing can revert this status once the email has been successfully sent.
    # ─────────────────────────────────────────────────────────────────────────
    try:
        with transaction.atomic():
            r = Recipient.objects.select_for_update().get(id=recipient_id)
            r.current_step_index = step_number
            r.last_sent_at = timezone.now()
            
            total_steps = CampaignStep.objects.filter(campaign_id=campaign_id).count() or 1
            if step_number >= total_steps:
                r.status = 'completed'
            else:
                r.status = 'active'
                
            r.smtp_email = creds.from_email  # record which account sent it
            r.save(update_fields=['current_step_index', 'last_sent_at', 'status', 'smtp_email'])
    except Exception as status_error:
        # Email was sent but we couldn't save the status update.
        # Log it but do NOT mark as failed — the email was delivered.
        logger.error(
            f"Could not update recipient {recipient_id} status to 'active' after successful send: {status_error}. "
            f"Email was delivered. Manual DB fix may be needed."
        )

    # ─────────────────────────────────────────────────────────────────────────
    # PHASE 4 — Best-effort stats & logging
    # Failures here are logged and swallowed — they CANNOT affect recipient status.
    # ─────────────────────────────────────────────────────────────────────────
    try:
        # Re-fetch creds and profile fresh to avoid stale data
        creds_obj = SMTPCredential.objects.get(id=creds_id)
        creds_obj.increment_usage()
    except Exception as e:
        logger.warning(f"Could not increment SMTP usage for cred {creds_id}: {e}")

    try:
        profile_obj = UserProfile.objects.get(user_id=user_id)
        profile_obj.increment_email_usage()
    except Exception as e:
        logger.warning(f"Could not increment email usage for user {user_id}: {e}")

    try:
        SentEmailLog.objects.create(
            recipient_id=recipient_id,
            step_id=step_id,
            smtp_used_id=creds_id,
            subject=step_subject,
            body_sent=rendered_body,
            message_id=custom_msg_id,
            variant_used=variant,
        )
    except Exception as e:
        logger.warning(f"Could not create SentEmailLog for recipient {recipient_id}: {e}")

    try:
        EmailCampaign.objects.filter(id=campaign_id).update(sent_count=F('sent_count') + 1)
        
        # Check if ALL recipients are in terminal states
        has_active_or_pending = Recipient.objects.filter(
            campaign_id=campaign_id,
            status__in=['active', 'pending']
        ).exists()
        
        if not has_active_or_pending:
            EmailCampaign.objects.filter(id=campaign_id).update(status='completed')
            
        cache.delete(f"campaign_stats_{campaign_id}")
    except Exception as e:
        logger.warning(f"Could not update campaign sent_count for campaign {campaign_id}: {e}")

    return f"Success: {recipient_id}"


def _mark_failed(recipient_id, reason):
    """Helper: safely mark a recipient as failed and increment campaign counter."""
    try:
        r = Recipient.objects.get(id=recipient_id)
        r.status = 'failed'
        r.error_message = reason
        r.save(update_fields=['status', 'error_message'])
        EmailCampaign.objects.filter(id=r.campaign_id).update(failed_count=F('failed_count') + 1)
        
        has_active_or_pending = Recipient.objects.filter(
            campaign_id=r.campaign_id,
            status__in=['active', 'pending']
        ).exists()
        
        if not has_active_or_pending:
            EmailCampaign.objects.filter(id=r.campaign_id).update(status='completed')
            
        cache.delete(f"campaign_stats_{r.campaign_id}")
    except Exception as e:
        logger.error(f"Could not mark recipient {recipient_id} as failed: {e}")


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
        recipients = campaign.recipients.filter(
            current_step_index=step_number - 1,
            is_replied=False,
            status='active'
        )

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
    recipients_list = list(recipients)
    for i, recipient in enumerate(recipients_list):
        target_creds = active_smtp[i % len(active_smtp)]
        send_single_email_task.apply_async(
            args=[recipient.id, step_number, target_creds.id],
            countdown=i * gap
        )

    return f"Campaign {campaign.name} Dispatched: {len(recipients_list)} tasks queued with {gap}s gap."


def trigger_followup_task(campaign_id, step_number):
    send_campaign_emails.delay(campaign_id, step_number)


@shared_task
def check_single_account_replies(cred_id):
    """Distributed worker to check IMAP for a single account."""
    try:
        cred = SMTPCredential.objects.get(id=cred_id)
        imap_host = cred.host.replace('smtp', 'imap')
        mail = imaplib.IMAP4_SSL(imap_host)
        mail.login(cred.username, cred.decrypted_password)
        mail.select("inbox")

        date_since = (timezone.now() - timedelta(days=7)).strftime("%d-%b-%Y")
        _, messages = mail.search(None, f'(SINCE "{date_since}")')

        for msg_num in messages[0].split():
            _, data = mail.fetch(msg_num, '(RFC822)')
            if not data or not data[0]:
                continue

            raw_email = data[0][1]
            msg = email.message_from_bytes(raw_email)
            from_header = msg.get('From', '').lower()
            in_reply_to = msg.get('In-Reply-To')
            references = msg.get('References', '')

            log = SentEmailLog.objects.filter(
                Q(message_id=in_reply_to) | Q(message_id__in=references.split())
            ).select_related('recipient').first()

            # CRITICAL SECURITY FIX: Ensure the reply is actually FROM the lead.
            # If the IMAP inbox contains sent emails (Steps 2, 3 etc.), they will match the message_id
            # of previous steps, but the 'From' address will be our own account.
            if not log or log.recipient.is_replied or log.recipient.is_unsubscribed:
                continue

            lead_email = log.recipient.email.lower()
            from_addr = email.utils.parseaddr(from_header)[1].lower()
            
            if from_addr != lead_email:
                # If the 'From' address doesn't exactly match the lead's email,
                # it's either our own follow-up (Sent mail in Inbox) or a notification.
                continue

            # Process the body
            body_lower = ""
            if msg.is_multipart():
                for part in msg.walk():
                    if part.get_content_type() == "text/plain":
                        try:
                            body_lower = part.get_payload(decode=True).decode().lower()
                        except:
                            body_lower = ""
                        break
            else:
                try:
                    body_lower = msg.get_payload(decode=True).decode().lower()
                except:
                    body_lower = ""

            # Specific keywords that indicate an manual unsubscription request.
            # We EXCLUDE 'unsubscribe' itself because it appears in our own footer
            # which is often included in the quoted history of a real reply.
            unsub_keywords = ['remove me', 'opt out', 'take me off your list', 'stop emails', 'don\'t email', 'unsubscribe me']
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
                    EmailCampaign.objects.filter(id=r.campaign.id).update(reply_count=F('reply_count') + 1)
                    logger.info(f"Reply detected: {r.email}")

                r.save()
                cache.delete(f"campaign_stats_{r.campaign.id}")

        mail.close()
        mail.logout()
        return f"Checked: {cred.from_email}"

    except Exception as e:
        logger.error(f"IMAP check failed for cred {cred_id}: {e}")
        return f"Error: {str(e)}"


@shared_task
def check_for_replies():
    """Master Dispatcher: Parallelizes reply checks across multiple workers."""
    creds = SMTPCredential.objects.filter(is_active=True).values_list('id', flat=True)
    if not creds:
        return "No active accounts"

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
        campaign.save(update_fields=['status'])
        send_campaign_emails.delay(campaign.id, 1)
        logger.info(f"Automatically started scheduled campaign: {campaign.name}")

@shared_task
def send_followup_reminder_notifications():
    """
    SaaS Feature: Scans for campaigns where follow-up steps are due.
    Sends a professional summary email to the user with stats and a call to action.
    """
    now = timezone.now()
    # Find active recipients who are due for their next step
    # We group by campaign and step to send one clean email per user/campaign step
    campaigns = EmailCampaign.objects.filter(status__in=['running', 'active'])
    
    for campaign in campaigns:
        user = campaign.user
        profile = user.profile
        
        # Check all possible next steps
        steps = campaign.steps.all().order_by('step_number')
        for step in steps:
            if step.step_number <= 1: continue # Skip initial outreach
            
            wait_threshold = now - timedelta(days=step.wait_days)
            
            # Count recipients who finished the previous step and are now due for THIS step
            due_recipients = campaign.recipients.filter(
                current_step_index=step.step_number - 1,
                last_sent_at__lte=wait_threshold,
                status='active',
                is_replied=False,
                is_unsubscribed=False
            ).count()
            
            if due_recipients > 0:
                # Prepare Stats for the reminder email
                stats = campaign.stats
                
                # Quota Check
                quota_warning = ""
                if not profile.can_send_email():
                    quota_warning = "<p style='color: #ef4444;'><b>⚠️ Warning:</b> Your monthly email quota is currently empty. Please upgrade to resume sending.</p>"
                
                subject = f"🚀 Follow-up Required: {campaign.name}"
                
                html_message = f"""
                <div style="font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px; border: 1px solid #e5e7eb; border-radius: 12px; color: #1f2937;">
                    <h2 style="color: #8b5cf6; margin-top: 0;">Follow-up Logic Triggered</h2>
                    <p>Hello <b>{user.username}</b>,</p>
                    <p>Your campaign <b>"{campaign.name}"</b> has <b>{due_recipients} leads</b> waiting for <b>Step {step.step_number}</b>.</p>
                    
                    <div style="background: #f9fafb; padding: 15px; border-radius: 8px; margin: 20px 0;">
                        <h4 style="margin-top: 0; margin-bottom: 10px; color: #4b5563;">Current Campaign Pulse:</h4>
                        <table style="width: 100%; border-collapse: collapse;">
                            <tr>
                                <td style="padding: 5px 0; color: #6b7280;">Total Outreach Sent:</td>
                                <td style="text-align: right; font-weight: bold; color: #111827;">{stats['sent_count']}</td>
                            </tr>
                            <tr>
                                <td style="padding: 5px 0; color: #6b7280;">Total Opens:</td>
                                <td style="text-align: right; font-weight: bold; color: #10b981;">{stats['open_count']} ({stats['open_rate']}%)</td>
                            </tr>
                            <tr>
                                <td style="padding: 5px 0; color: #6b7280;">Total Replies:</td>
                                <td style="text-align: right; font-weight: bold; color: #8b5cf6;">{stats['reply_count']} ({stats['reply_rate']}%)</td>
                            </tr>
                        </table>
                    </div>

                    {quota_warning}

                    <p style="line-height: 1.6;">Leads are ready for the follow-up set for <b>{step.wait_days} days</b> after the previous message. Log in to your dashboard to trigger the next sequence.</p>
                    
                    <div style="text-align: center; margin-top: 30px;">
                        <a href="{settings.SITE_URL}/mail/campaign/{campaign.id}/" 
                           style="background: #8b5cf6; color: white; padding: 12px 24px; border-radius: 8px; text-decoration: none; font-weight: bold; display: inline-block;">
                           Review & Send Follow-up #{step.step_number}
                        </a>
                    </div>
                    
                    <p style="font-size: 12px; color: #9ca3af; margin-top: 40px; text-align: center;">
                        LeadNexus — Your own Campaign Engine
                    </p>
                </div>
                """
                
                # Send the reminder to the USER (not the leads)
                reminder_email = EmailMessage(
                    subject=subject,
                    body=html_message,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    to=[user.email]
                )
                reminder_email.content_subtype = "html"
                reminder_email.send()
                
                logger.info(f"Sent follow-up reminder for campaign {campaign.id} to {user.email}")
                break # Send only one reminder per campaign per run to avoid spamming the user
