from django.db import models
from django.utils import timezone

class SMTPCredential(models.Model):
    PROVIDER_CHOICES = [
        ('gmail', 'Gmail'),
        ('outlook', 'Outlook/Hotmail'),
        ('google_workspace', 'Google Workspace'),
        ('microsoft_365', 'Microsoft 365'),
        ('custom', 'Custom SMTP'),
    ]

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
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} ({self.from_email})"

class EmailCampaign(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('running', 'Running'),
        ('paused', 'Paused'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    ]

    name = models.CharField(max_length=255, default="Untitled Campaign", help_text="A friendly name for your campaign")
    subject = models.CharField(max_length=255)
    body = models.TextField(help_text="Use {{ name }} for placeholders")
    gap_minutes = models.IntegerField(default=1, help_text="Wait time between each email")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    total_recipients = models.IntegerField(default=0)
    sent_count = models.IntegerField(default=0)
    failed_count = models.IntegerField(default=0)

    @property
    def pending_count(self):
        return max(0, self.total_recipients - self.sent_count - self.failed_count)

    @property
    def progress_percentage(self):
        if self.total_recipients == 0:
            return 0
        return int(((self.sent_count + self.failed_count) / self.total_recipients) * 100)

    def __str__(self):
        return self.name

class Recipient(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('sent', 'Sent'),
        ('failed', 'Failed'),
    ]

    campaign = models.ForeignKey(EmailCampaign, related_name='recipients', on_delete=models.CASCADE)
    email = models.EmailField()
    name = models.CharField(max_length=255, blank=True, null=True)
    custom_data = models.JSONField(default=dict, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    error_message = models.TextField(blank=True, null=True)
    sent_at = models.DateTimeField(blank=True, null=True)

    def __str__(self):
        return f"{self.email} for {self.campaign.name}"
