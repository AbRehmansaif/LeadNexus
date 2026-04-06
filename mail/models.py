from django.db import models
from django.utils import timezone
from django.contrib.auth.models import User

class SMTPCredential(models.Model):
    PROVIDER_CHOICES = [
        ('gmail', 'Gmail'),
        ('outlook', 'Outlook/Hotmail'),
        ('google_workspace', 'Google Workspace'),
        ('microsoft_365', 'Microsoft 365'),
        ('custom', 'Custom SMTP'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='smtp_credentials', null=True, blank=True)

    name = models.CharField(max_length=100)
    provider = models.CharField(max_length=50, choices=PROVIDER_CHOICES, default='custom')
    host = models.CharField(max_length=255)
    port = models.IntegerField(default=587)
    username = models.CharField(max_length=255)
    password = models.CharField(max_length=255)
    use_tls = models.BooleanField(default=True)
    use_ssl = models.BooleanField(default=False)
    from_email = models.EmailField()
    from_name = models.CharField(max_length=255, blank=True, null=True, help_text="e.g. Cristina from LeadNexus")
    is_active = models.BooleanField(default=True)
    daily_limit = models.IntegerField(default=50, help_text="Max emails per 24h")
    emails_sent_today = models.IntegerField(default=0)
    last_reset_at = models.DateTimeField(default=timezone.now)
    created_at = models.DateTimeField(auto_now_add=True)

    def check_and_reset_limit(self):
        """
        Resets the daily count when a new calendar day starts (12:00 AM).
        Also re-activates the account if it was deactivated due to limit.
        """
        now = timezone.now()
        # Checks if today's date is greater than the date of the last reset
        if now.date() > self.last_reset_at.date():
            self.emails_sent_today = 0
            self.last_reset_at = now
            if not self.is_active:
                self.is_active = True
            self.save()
            return True
        return False

    def increment_usage(self):
        """
        Increments the usage count and deactivates if limit reached.
        """
        self.emails_sent_today += 1
        if self.emails_sent_today >= self.daily_limit:
            self.is_active = False
        self.save()

    def save(self, *args, **kwargs):
        """Automatically encrypt the password before saving to DB."""
        from core.encryption import encrypt_password
        if self.password and not self.password.startswith('gAAAA'):
            self.password = encrypt_password(self.password)
        super().save(*args, **kwargs)

    @property
    def decrypted_password(self):
        """Securely retrieves the decrypted password for SMTP connection."""
        from core.encryption import decrypt_password
        return decrypt_password(self.password)

    def __str__(self):
        return f"{self.name} ({self.from_email})"

class EmailCampaign(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('scheduled', 'Scheduled'),
        ('running', 'Running'),
        ('paused', 'Paused'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='email_campaigns', null=True, blank=True)
    name = models.CharField(max_length=255, default="Untitled Campaign", help_text="A friendly name for your campaign")
    subject = models.CharField(max_length=255)
    body = models.TextField(help_text="Use {{ name }} for placeholders")
    gap_seconds = models.IntegerField(default=2, help_text="Wait time between each email (seconds)")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    scheduled_at = models.DateTimeField(null=True, blank=True, help_text="Set a time to start this campaign automatically", db_index=True)
    # SaaS Control: Business Hours & Days
    send_window_start = models.TimeField(null=True, blank=True, help_text="Starting hour (e.g., 09:00)")
    send_window_end = models.TimeField(null=True, blank=True, help_text="Ending hour (e.g., 17:00)")
    work_days = models.CharField(max_length=20, default='1,2,3,4,5', help_text="Comma separated days (1=Mon, 7=Sun)")
    
    # Attachment Support (Step 1 Fallback)
    attachment = models.FileField(upload_to='campaign_attachments/', null=True, blank=True)
    attachment_name = models.CharField(max_length=255, null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    total_recipients = models.IntegerField(default=0)
    sent_count = models.IntegerField(default=0)
    failed_count = models.IntegerField(default=0)
    open_count = models.IntegerField(default=0)
    reply_count = models.IntegerField(default=0, help_text="Total recipients who have replied")

    @property
    def pending_count(self):
        return max(0, self.total_recipients - self.sent_count - self.failed_count)

    @property
    def open_rate(self):
        if self.sent_count == 0:
            return 0
        return int((self.open_count / self.sent_count) * 100)
    
    @property
    def reply_rate(self):
        if self.sent_count == 0:
            return 0
        return int((self.reply_count / self.sent_count) * 100)

    @property
    def progress_percentage(self):
        if self.total_recipients == 0:
            return 0
        return int(((self.sent_count + self.failed_count) / self.total_recipients) * 100)

    @property
    def stats(self):
        """High-performance cached stats for both API and Templates."""
        from django.core.cache import cache
        cache_key = f"campaign_stats_{self.id}"
        cached_stats = cache.get(cache_key)
        
        if cached_stats:
            return cached_stats
            
        stats = {
            'total_recipients': self.total_recipients,
            'sent_count': self.sent_count,
            'open_count': self.open_count,
            'reply_count': self.reply_count,
            'open_rate': self.open_rate,
            'reply_rate': self.reply_rate,
            'pending_count': self.pending_count,
            'progress_percentage': self.progress_percentage,
        }
        
        cache.set(cache_key, stats, timeout=10)
        return stats

    def sync_stats_from_db(self):
        """Force a one-time sync of all stats from the Recipient table."""
        self.total_recipients = self.recipients.count()
        # Only count recipients that were actually sent to (not failed/unsubscribed/pending)
        self.sent_count = self.recipients.filter(status__in=['active', 'replied', 'completed']).count()
        self.open_count = self.recipients.filter(is_opened=True).count()
        self.reply_count = self.recipients.filter(is_replied=True).count()
        self.failed_count = self.recipients.filter(status='failed').count()
        self.save()

        # Clear cache after sync
        from django.core.cache import cache
        cache.delete(f"campaign_stats_{self.id}")

    def __str__(self):
        return self.name

class CampaignStep(models.Model):
    """Stores sequences for a campaign (e.g. Day 1 Intro, Day 3 Follow-up)."""
    campaign = models.ForeignKey(EmailCampaign, related_name='steps', on_delete=models.CASCADE)
    step_number = models.IntegerField(default=1, help_text="1 for first mail, 2 for first follow-up, etc.")
    wait_days = models.IntegerField(default=3, help_text="Days to wait after previous step")
    subject = models.CharField(max_length=255)
    body = models.TextField(help_text="Template body. Supports {{ name }}")
    
    # A/B Testing Variants
    subject_b = models.CharField(max_length=255, null=True, blank=True, help_text="Alternate subject for A/B testing")
    body_b = models.TextField(null=True, blank=True, help_text="Alternate body for A/B testing")
    
    # Step-specific Attachment
    attachment = models.FileField(upload_to='step_attachments/', null=True, blank=True)
    attachment_name = models.CharField(max_length=255, null=True, blank=True)

    class Meta:
        ordering = ['step_number']
        unique_together = ('campaign', 'step_number')

    def __str__(self):
        return f"Step {self.step_number} for {self.campaign.name}"

class Recipient(models.Model):
    """Tracks a lead's journey through a campaign."""
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('active', 'Active'),
        ('replied', 'Replied'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('unsubscribed', 'Unsubscribed'),
        ('sending', 'Sending...'),
    ]

    campaign = models.ForeignKey(EmailCampaign, related_name='recipients', on_delete=models.CASCADE)
    email = models.EmailField(db_index=True)
    name = models.CharField(max_length=255, blank=True, null=True)
    custom_data = models.JSONField(default=dict, blank=True)
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', db_index=True)
    error_message = models.TextField(blank=True, null=True)
    
    # Sequence Tracking
    current_step_index = models.IntegerField(default=0, help_text="Last successfully sent step number", db_index=True)
    last_sent_at = models.DateTimeField(blank=True, null=True, db_index=True)
    smtp_email = models.EmailField(blank=True, null=True, help_text="SMTP email used for last send")
    
    # Interaction Tracking
    is_opened = models.BooleanField(default=False, db_index=True)
    opened_at = models.DateTimeField(blank=True, null=True)
    open_count = models.IntegerField(default=0)
    
    is_replied = models.BooleanField(default=False, db_index=True)
    replied_at = models.DateTimeField(blank=True, null=True)

    is_unsubscribed = models.BooleanField(default=False, db_index=True)
    unsubscribed_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        unique_together = ('campaign', 'email')

    def __str__(self):
        return f"{self.email} ({self.campaign.name})"

class SentEmailLog(models.Model):
    """The 'Evidence' log: Exactly which account sent which message to which user."""
    recipient = models.ForeignKey(Recipient, related_name='delivery_logs', on_delete=models.CASCADE)
    step = models.ForeignKey(CampaignStep, on_delete=models.SET_NULL, null=True, blank=True)
    smtp_used = models.ForeignKey(SMTPCredential, on_delete=models.SET_NULL, null=True, blank=True)
    
    subject = models.CharField(max_length=255)
    body_sent = models.TextField()
    variant_used = models.CharField(max_length=1, default='A', help_text="A or B variant used for this send")
    
    message_id = models.CharField(max_length=255, db_index=True, help_text="SMTP Message-ID for reply threading")
    sent_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Log: Step {self.step.step_number if self.step else 'N/A'} to {self.recipient.email}"
