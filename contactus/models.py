from django.db import models

class ContactMessage(models.Model):
    name = models.CharField(max_length=255)
    email = models.EmailField()
    subject = models.CharField(max_length=255, blank=True, null=True)
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField(default=False)

    def __str__(self):
        return f"Message from {self.name} - {self.email}"

    class Meta:
        ordering = ['-created_at']
        verbose_name = "Contact Message"
        verbose_name_plural = "Contact Messages"


class ContactSettings(models.Model):
    """Singleton model for contact-form specific configurations."""
    notification_email = models.EmailField(default="admin@leadnexus.ai", help_text="Email where notifications for new contact requests will be sent.")
    notification_smtp = models.ForeignKey('mail.SMTPCredential', on_delete=models.SET_NULL, null=True, blank=True, help_text="The SMTP account to use for sending these specific system notifications.")

    class Meta:
        verbose_name = "Contact System Setting"
        verbose_name_plural = "Contact System Settings"

    def __str__(self):
        return "Contact System Configuration"

    def save(self, *args, **kwargs):
        # Ensure only one instance exists
        if not self.pk and ContactSettings.objects.exists():
            return
        return super().save(*args, **kwargs)
