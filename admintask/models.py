from django.db import models
from django.contrib.auth.models import User

class GlobalSettings(models.Model):
    """Singleton model for system-wide configurations."""
    registrations_enabled = models.BooleanField(default=True, help_text="If disabled, new users cannot register accounts.")
    maintenance_mode = models.BooleanField(default=False, help_text="If enabled, shows a maintenance notice.")
    
    # Contact Information for Landing Page
    contact_email = models.EmailField(default="sales@leadnexus.ai", help_text="Public contact email displayed on the landing page.")
    whatsapp_number = models.CharField(max_length=20, default="+1234567890", help_text="WhatsApp number with country code (e.g. +1234567890) for the chat button.")

    # Dashboard Monthly Targets
    mrr_target = models.DecimalField(max_digits=12, decimal_places=2, default=55000.00, help_text="Monthly Revenue target for the dashboard.")
    registrations_target = models.PositiveIntegerField(default=1000, help_text="Monthly New Registrations target for the dashboard.")

    class Meta:
        verbose_name = "Global System Setting"
        verbose_name_plural = "Global System Settings"

    def __str__(self):
        return "Global System Configuration"

    def save(self, *args, **kwargs):
        # Ensure only one instance exists
        if not self.pk and GlobalSettings.objects.exists():
            return
        return super().save(*args, **kwargs)

class ServerPerformanceLog(models.Model):
    """Tracks latency of every request for the Admin Matrix Dashboard."""
    path = models.CharField(max_length=500)
    method = models.CharField(max_length=10)
    latency_seconds = models.FloatField()
    status_code = models.IntegerField()
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ['-timestamp']

    def __str__(self):
        return f"{self.method} {self.path} - {self.latency_seconds}s"

class ErrorNotification(models.Model):
    """History of automated alerts sent to the admin."""
    TYPE_CHOICES = [
        ('campaign_fail', 'Campaign Failure'),
        ('server_error', '500 Server Error'),
        ('security_breach', 'Security Alert'),
        ('quota_exhausted', 'Quota Exhaustion'),
    ]
    type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    message = models.TextField()
    context_data = models.JSONField(default=dict, blank=True)
    sent_to_telegram = models.BooleanField(default=False)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-timestamp']

    def __str__(self):
        return f"[{self.type}] {self.message[:50]}..."

class AdminTaskSettings(models.Model):
    """Singleton model for admintask configurations."""
    telegram_bot_token = models.CharField(max_length=255, blank=True, null=True, help_text="Bot token for admin notifications.")
    admin_chat_id = models.CharField(max_length=255, blank=True, null=True, help_text="Telegram Chat ID for receiving alerts.")
    enable_error_alerts = models.BooleanField(default=False, help_text="If enabled, sends telegram alerts on critical errors.")

    # Performance Tracking Settings
    enable_performance_logging = models.BooleanField(default=True, help_text="Record system-wide latency.")
    slow_request_threshold = models.FloatField(default=0.5, help_text="Only log requests that take longer than this (in seconds). Set to 0 to log everything.")
    retention_days = models.PositiveIntegerField(default=7, help_text="Automatically delete logs older than this number of days.")

    class Meta:
        verbose_name = "Admin Intelligence Setting"
        verbose_name_plural = "Admin Intelligence Settings"

    def __str__(self):
        return "Admin Intelligence Configuration"

    def save(self, *args, **kwargs):
        # Ensure only one instance exists
        if not self.pk and AdminTaskSettings.objects.exists():
            return
        return super().save(*args, **kwargs)
