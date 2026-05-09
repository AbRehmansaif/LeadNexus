import logging
import uuid
import imaplib
import email
from email.header import decode_header
from datetime import timedelta
from django.core.mail import get_connection, EmailMessage, EmailMultiAlternatives
from django.utils import timezone
from .models import EmailCampaign, Recipient, SMTPCredential, CampaignStep, SentEmailLog
from .utils import send_gmail_api_email, render_spintax
from core.models import UserProfile
from django.template import Template, Context
from django.conf import settings
from django.urls import reverse
from django.db import transaction
from django.db.models import Q, F, Max
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
            creds = None

            # Guard: already processed or in a terminal state for this step
            if recipient.is_replied or recipient.is_unsubscribed or campaign.status == 'paused':
                return f"Skipped: {recipient.email} (Replied, Unsubscribed, or Paused)"
                
            # CRITICAL GUARD: Prevent duplicate transmissions at the ADDRESS level (not just row level)
            # We check if ANY row with this email address has already reached this step OR is currently sending.
            address_already_sent = Recipient.objects.filter(
                campaign_id=campaign.id, 
                email__iexact=recipient.email
            ).filter(
                Q(current_step_index__gte=step_number) | Q(status='sending')
            ).exclude(id=recipient.id).exists()

            # Transient Cache Lock (Phase 2 protection)
            # Since Phase 2 (SMTP) happens outside the DB transaction, we use a 10-minute 
            # atomic cache lock to prevent multiple workers from processing the same 
            # recipient/step ID simultaneously.
            lock_key = f"send_lock_{recipient.id}_{step_number}"
            is_locked = not cache.add(lock_key, "locked", timeout=600)

            # Skip if already processed, already sending (DB status), or locked (Cache status)
            if recipient.current_step_index >= step_number or address_already_sent or is_locked:
                # Special Case: If we skipped because it's ALREADY 'sending' from a DISPATCHER
                # but THIS specific task doesn't have the cache lock yet, it might be the
                # legitimate worker for this recipient. 
                # If we have the lock, we proceed even if DB says 'sending'.
                if is_locked:
                    return f"Skipped: {recipient.email} (Task for Step {step_number} already in progress)"
                
                # If we skipped because of a different row, mark THIS row as completed/active too
                # to stop it from appearing in future dispatcher loops.
                if address_already_sent and recipient.status == 'pending':
                    max_step = CampaignStep.objects.filter(campaign_id=campaign.id).aggregate(Max('step_number'))['step_number__max'] or 1
                    recipient.status = 'completed' if step_number >= max_step else 'active'
                    recipient.current_step_index = step_number
                    recipient.save(update_fields=['status', 'current_step_index'])
                
                return f"Skipped: {recipient.email} (Already reached Step {step_number} or address duplicated)"

            # Business Hours Check — use apply_async NOT self.retry so we
            # don't burn the precious max_retries=3 SMTP error budget.
            now = timezone.now()
            local_now = timezone.localtime(now)

            if campaign.work_days and str(local_now.isoweekday()) not in campaign.work_days.split(','):
                # Release lock if we defer
                cache.delete(lock_key)
                send_single_email_task.apply_async(
                    args=[recipient_id, step_number, cred_id],
                    countdown=14400  # retry in 4 hours
                )
                return f"Deferred: {recipient.email} — not a configured work day"

            if campaign.send_window_start and campaign.send_window_end:
                current_time = local_now.time()
                start_time = campaign.send_window_start
                end_time = campaign.send_window_end
                
                if start_time <= end_time:
                    in_window = start_time <= current_time <= end_time
                else:
                    in_window = current_time >= start_time or current_time <= end_time
                    
                if not in_window:
                    # Release lock if we defer
                    cache.delete(lock_key)
                    send_single_email_task.apply_async(
                        args=[recipient_id, step_number, cred_id],
                        countdown=3600  # retry in 1 hour
                    )
                    return f"Deferred: {recipient.email} — outside send window"

            # Pre-send Lockdown (Commit this before releasing lock)
            recipient.status = 'sending'
            recipient.save(update_fields=['status'])

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
                recipient.status = 'failed'
                recipient.error_message = "Monthly email quota exceeded"
                recipient.save(update_fields=['status', 'error_message'])
                
                # Sync totals so the 0/1 progress bar actually updates in the UI
                # This also clears the status cache automatically.
                campaign.sync_stats_from_db()
                
                return f"Failed: {recipient.email} (Monthly email quota exceeded)"

            # SMTP Selection
            if cred_id:
                creds = SMTPCredential.objects.filter(id=cred_id).first()
                if creds:
                    creds.check_and_reset_limit()
                if creds and not creds.is_active:
                    creds = None
            
            if not creds:
                all_creds = SMTPCredential.objects.filter(user=campaign.user)
                for c in all_creds:
                    c.check_and_reset_limit()
                creds = all_creds.filter(is_active=True).order_by('?').first()

            if not creds:
                from datetime import datetime, time as dt_time, timedelta
                now_time = timezone.now()
                tomorrow = now_time.date() + timedelta(days=1)
                midnight = timezone.make_aware(datetime.combine(tomorrow, dt_time.min))
                wait_seconds = max(60, (midnight - now_time).total_seconds() + 300)
                
                # Release lock if we defer
                cache.delete(lock_key)
                send_single_email_task.apply_async(
                    args=[recipient_id, step_number, None],
                    countdown=wait_seconds
                )
                return f"Deferred: {recipient.email} — SMTP daily limit hit, retrying tomorrow"

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
            # CRITICAL: If the user has provided a professional HTML layout (tables, divs),
            # we skip linebreaks() to avoid mangling the structure with <br> tags.
            if '<table>' in interim_body.lower() or '<div' in interim_body.lower():
                rendered_body = render_spintax(interim_body)
            else:
                rendered_body = linebreaks(render_spintax(interim_body))
                
            # Randomize Subject as well if it contains spintax
            step_subject = render_spintax(step_subject)

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
            
            # Check if using a free email provider (Domain mismatch risk)
            free_providers = ['@gmail.com', '@yahoo.com', '@hotmail.com', '@outlook.com', '@icloud.com', '@aol.com']
            is_free_provider = any(creds.from_email.lower().endswith(provider) for provider in free_providers)

            # Unsubscribe Link
            if campaign.add_unsubscribe_link:
                unsub_url = f"{tracking_base.rstrip('/')}{reverse('unsubscribe', args=[recipient.id])}"
                # Only add HTTP unsubscribe link to body if not a free provider, or if we must, keep it simple
                unsub_footer = f'<br><br><div style="font-size: 11px; color: #666; border-top: 1px dashed #eee; padding-top: 10px;">' \
                               f'Too many emails? <a href="{unsub_url}" style="color: #8b5cf6; text-decoration: underline;">Unsubscribe from this campaign</a>' \
                               f'</div>'
                rendered_body += f"\n{unsub_footer}"
            else:
                unsub_url = None

            # Tracking Pixel - The user requested open tracking even for free providers
            if campaign.track_opens:
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
            
            # List-Unsubscribe header for bulk mail requirements (RFC 8058)
            unsub_mailto = f"mailto:unsubscribe@{domain}?subject=Unsubscribe%20{recipient.email}"
            if is_free_provider:
                # Omit HTTP link for free providers to avoid severe domain mismatch penalty
                headers['List-Unsubscribe'] = f"<{unsub_mailto}>"
            elif unsub_url:
                headers['List-Unsubscribe'] = f"<{unsub_url}>, <{unsub_mailto}>"
                headers['List-Unsubscribe-Post'] = "List-Unsubscribe=One-Click"
            else:
                headers['List-Unsubscribe'] = f"<{unsub_mailto}>"

            previous_log = recipient.delivery_logs.order_by('-sent_at').first()
            if previous_log:
                headers.update({
                    'In-Reply-To': previous_log.message_id,
                    'References': previous_log.message_id,
                })
            from_email = f"{creds.from_name} <{creds.from_email}>" if creds.from_name else creds.from_email

            import re
            # Preserve newlines by replacing common block/break tags with \n before stripping
            text_prep = re.sub(r'<(br|/p|/div|/tr|/h\d)[^>]*>', '\n', rendered_body, flags=re.IGNORECASE)
            from django.utils.html import strip_tags
            plain_text_body = strip_tags(text_prep).strip()

            # Ensure the HTML body is structurally valid (prevents HTML_MISSING_HEAD spam penalties)
            html_body = f"<!DOCTYPE html>\n<html>\n<head><meta charset=\"utf-8\"></head>\n<body style=\"font-family: Arial, sans-serif; line-height: 1.5; color: #333;\">\n{rendered_body}\n</body>\n</html>"

            # Build the email object (not sent yet) using MultiAlternatives
            # This sends both text/plain and text/html parts, critical for avoiding spam filters
            email_obj = EmailMultiAlternatives(
                subject=step_subject, body=plain_text_body,
                from_email=from_email, to=[recipient.email],
                connection=connection, headers=headers
            )
            email_obj.attach_alternative(html_body, "text/html")
            
            # ATTACHMENT PREREQUISITE: Ensure we have the right attachment from Step or Campaign
            attachment_obj = None
            if step and step.attachment:
                attachment_obj = step.attachment
                attachment_name = step.attachment_name
            elif not step and campaign.attachment:
                attachment_obj = campaign.attachment
                attachment_name = campaign.attachment_name
            
            if attachment_obj:
                try:
                    # Professional attachment logic: reads binary content to support S3/Local uniformly
                    f_name = attachment_name or attachment_obj.name.split('/')[-1]
                    email_obj.attach(f_name, attachment_obj.read())
                except Exception as e:
                    logger.warning(f"Could not attach file for recipient {recipient_id}: {e}")

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
        
        # Ensure lock is released so retry can pick it up
        try:
            cache.delete(f"send_lock_{recipient_id}_{step_number}")
        except:
            pass

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
        if creds.auth_type == 'oauth':
            message_id = send_gmail_api_email(creds, email_obj)
            if message_id:
                custom_msg_id = message_id # Use Gmail's message ID
        else:
            email_obj.send()
    except Exception as smtp_error:
        # Genuine SMTP failure — safe to retry (email was NOT sent)
        logger.error(f"SMTP error for {recipient_id}: {smtp_error}")
        
        # Release lock so retry can proceed
        try:
            cache.delete(f"send_lock_{recipient_id}_{step_number}")
        except:
            pass

        try:
            # RESET status so the retry (Phase 1) doesn't skip itself due to the 'sending' lockdown
            Recipient.objects.filter(id=recipient_id).update(status='pending')
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
            
            # Get the maximum step number defined in the campaign sequence
            max_step = CampaignStep.objects.filter(campaign_id=campaign_id).aggregate(Max('step_number'))['step_number__max'] or 1
            
            if step_number >= max_step:
                r.status = 'completed'
            else:
                r.status = 'active'
                
            r.smtp_email = creds.from_email  # record which account sent it
            r.save(update_fields=['current_step_index', 'last_sent_at', 'status', 'smtp_email'])
            
            # Phase 3 success: we can release the transient lock now
            cache.delete(f"send_lock_{recipient_id}_{step_number}")
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
    # Dispatcher Lock: Prevent multiple dispatchers from running for the same step/campaign
    # This is the primary defense against "Double Start" or Celery Beat overlaps.
    dispatcher_lock = f"dispatcher_lock_{campaign_id}_{step_number}"
    if not cache.add(dispatcher_lock, "active", timeout=600):
        return f"Dispatcher for campaign {campaign_id} step {step_number} is already running."

    try:
        campaign = EmailCampaign.objects.get(pk=campaign_id)

        # 1. Get eligible recipients and mark them as 'sending' ATOMICALLY
        # This prevents a second dispatcher from seeing the same recipients as 'pending'.
        with transaction.atomic():
            if step_number == 1:
                recipients = campaign.recipients.select_for_update().filter(status='pending', current_step_index=0)
            else:
                recipients = campaign.recipients.select_for_update().filter(
                    current_step_index=step_number - 1,
                    is_replied=False,
                    status='active'
                )
            
            recipients_list = list(recipients)
            if not recipients_list:
                cache.delete(dispatcher_lock)
                if step_number == 1:
                    has_active_or_pending = Recipient.objects.filter(campaign_id=campaign_id, status__in=['active', 'pending']).exists()
                    if not has_active_or_pending:
                        campaign.status = 'completed'
                    else:
                        campaign.status = 'running'
                    campaign.save(update_fields=['status'])
                return "No recipients found"

            # Lockdown: Mark all as 'sending' before even queueing the tasks
            campaign.recipients.filter(id__in=[r.id for r in recipients_list]).update(status='sending')

        campaign.status = 'running'
        campaign.save(update_fields=['status'])

        # 2. Setup Rotation Pool
        all_smtp = list(SMTPCredential.objects.filter(user=campaign.user))
        if not all_smtp:
            campaign.recipients.filter(id__in=[r.id for r in recipients_list]).update(status='failed', error_message='No SMTP accounts configured')
            campaign.sync_stats_from_db()
            campaign.refresh_from_db()
            if not Recipient.objects.filter(campaign_id=campaign_id, status__in=['active', 'pending']).exists():
                campaign.status = 'completed'
                campaign.save(update_fields=['status'])
            cache.delete(dispatcher_lock)
            return "No SMTP accounts configured"

        for c in all_smtp:
            c.check_and_reset_limit()
            
        active_smtp = [c for c in all_smtp if c.is_active]

        gap = max(1, campaign.gap_seconds)

        # 3. Dispatch independent tasks with Countdown
        for i, recipient in enumerate(recipients_list):
            target_creds_id = active_smtp[i % len(active_smtp)].id if active_smtp else None
            send_single_email_task.apply_async(
                args=[recipient.id, step_number, target_creds_id],
                countdown=i * gap
            )

        return f"Campaign {campaign.name} Dispatched: {len(recipients_list)} tasks queued with {gap}s gap."
    
    except Exception as e:
        logger.error(f"Dispatcher failed for campaign {campaign_id}: {e}")
        return f"Error: {str(e)}"
    finally:
        # Release the dispatcher lock
        cache.delete(dispatcher_lock)


def trigger_followup_task(campaign_id, step_number):
    send_campaign_emails.delay(campaign_id, step_number)


def _process_reply(log, from_addr, body_lower):
    """Common logic to process a detected reply."""
    if not log or log.recipient.is_replied or log.recipient.is_unsubscribed:
        return False

    lead_email = log.recipient.email.lower()
    if from_addr.lower() != lead_email:
        return False

    # Specific keywords that indicate an manual unsubscription request.
    unsub_keywords = ['remove me', 'opt out', 'take me off your list', 'stop emails', 'don\'t email', 'unsubscribe me']
    is_unsub_request = any(kw in body_lower.lower() for kw in unsub_keywords)

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
    return True

@shared_task
def check_single_account_replies(cred_id):
    """Distributed worker to check for replies for a single account (IMAP or Gmail API)."""
    try:
        cred = SMTPCredential.objects.get(id=cred_id)
        
        if cred.auth_type == 'oauth':
            from .utils import check_gmail_replies
            replies = check_gmail_replies(cred)
            for reply in replies:
                log = SentEmailLog.objects.filter(
                    Q(message_id=reply['in_reply_to']) | Q(message_id__in=reply['references'].split())
                ).select_related('recipient').first()
                
                from_addr = email.utils.parseaddr(reply['from'])[1].lower()
                _process_reply(log, from_addr, reply['body'])
            return f"Checked Gmail API: {cred.from_email}"
        else:
            # IMAP Logic
            imap_host = cred.host.replace('smtp', 'imap')
            mail = imaplib.IMAP4_SSL(imap_host)
            mail.login(cred.username, cred.decrypted_password)
            mail.select("inbox")
    
            date_since = (timezone.now() - timedelta(days=7)).strftime("%d-%b-%Y")
            _, messages = mail.search(None, f'(SINCE "{date_since}")')
    
            for msg_num in messages[0].split():
                _, data = mail.fetch(msg_num, '(BODY.PEEK[])')
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
    
                from_addr = email.utils.parseaddr(from_header)[1].lower()
                
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
                
                _process_reply(log, from_addr, body_lower)
    
            mail.close()
            mail.logout()
            return f"Checked IMAP: {cred.from_email}"

    except Exception as e:
        logger.error(f"Reply check failed for cred {cred_id}: {e}")
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
