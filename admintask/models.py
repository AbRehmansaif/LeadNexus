from django.db import models
from django.contrib.auth.models import User

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
