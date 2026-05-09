from django.db import models
from django.contrib.auth.models import User
from accounts.models import GmailAccount

class Campaign(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    name = models.CharField(max_length=255)
    subject = models.CharField(max_length=255)
    body = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

    @property
    def status_sent_count(self):
        return self.leads.filter(status='sent').count()

    @property
    def status_pending_count(self):
        return self.leads.filter(status='pending').count()

class Lead(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('sent', 'Sent'),
        ('failed', 'Failed'),
    ]
    campaign = models.ForeignKey(Campaign, on_delete=models.CASCADE, related_name='leads')
    email = models.EmailField()
    first_name = models.CharField(max_length=100, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    error_message = models.TextField(blank=True, null=True)

    def __str__(self):
        return self.email

class EmailLog(models.Model):
    campaign = models.ForeignKey(Campaign, on_delete=models.CASCADE)
    gmail_account = models.ForeignKey(GmailAccount, on_delete=models.SET_NULL, null=True)
    lead = models.ForeignKey(Lead, on_delete=models.CASCADE)
    sent_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20)
    message_id = models.CharField(max_length=255, blank=True, null=True)
