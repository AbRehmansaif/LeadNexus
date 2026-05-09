from django.db import models
from django.contrib.auth.models import User

class GmailAccount(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='gmail_accounts')
    email = models.EmailField()
    access_token = models.TextField()
    refresh_token = models.TextField(null=True, blank=True)
    token_uri = models.CharField(max_length=255)
    client_id = models.CharField(max_length=255)
    client_secret = models.CharField(max_length=255)
    scopes = models.TextField()
    expiry = models.DateTimeField()
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.email
