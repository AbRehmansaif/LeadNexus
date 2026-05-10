from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone


class WarmupAccount(models.Model):
    STATUS_CHOICES = [
        ('inactive', 'Not Started'),
        ('warming', 'Warming Up'),
        ('warmed', 'Fully Warmed'),
        ('paused', 'Paused'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='warmup_accounts')
    # Link to existing SMTP credential from the mail app
    smtp_credential = models.OneToOneField(
        'mail.SMTPCredential', on_delete=models.CASCADE, related_name='warmup_profile'
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='inactive')

    # Progress
    day_number = models.IntegerField(default=0, help_text="Current warmup day")
    target_days = models.IntegerField(default=30, help_text="Total days to warm up")
    current_daily_volume = models.IntegerField(default=3)
    max_daily_volume = models.IntegerField(default=50, help_text="Max emails/day at full warmup")

    # Lifetime counters
    total_sent = models.IntegerField(default=0)
    inbox_count = models.IntegerField(default=0)
    spam_count = models.IntegerField(default=0)
    reply_count = models.IntegerField(default=0)

    # Score (0–100)
    warmup_score = models.IntegerField(default=0)

    started_at = models.DateTimeField(null=True, blank=True)
    last_run_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    # ── Derived metrics ──────────────────────────────────────

    @property
    def checked_total(self):
        return self.inbox_count + self.spam_count

    @property
    def inbox_rate(self):
        total = self.checked_total
        return round((self.inbox_count / total) * 100, 1) if total > 0 else 0.0

    @property
    def spam_rate(self):
        total = self.checked_total
        return round((self.spam_count / total) * 100, 1) if total > 0 else 0.0

    @property
    def reply_rate(self):
        return round((self.reply_count / self.total_sent) * 100, 1) if self.total_sent > 0 else 0.0

    def add_placement_result(self, is_spam=False):
        """Update stats when one of our sent emails is found by a recipient."""
        if is_spam:
            self.spam_count += 1
        else:
            self.inbox_count += 1
        self.warmup_score = self.calculate_score()
        self.save(update_fields=['inbox_count', 'spam_count', 'warmup_score'])

    @property
    def progress_percentage(self):
        return min(100, int((self.day_number / max(1, self.target_days)) * 100))

    @property
    def score_label(self):
        s = self.warmup_score
        if s >= 85:
            return ('Excellent', 'success')
        elif s >= 65:
            return ('Good', 'info')
        elif s >= 40:
            return ('Fair', 'warning')
        else:
            return ('Poor', 'danger')

    def calculate_score(self):
        """Score 0–100 based on inbox rate, reply rate, spam rate, and progress."""
        score = 0
        ct = self.checked_total

        # Inbox rate — 40 pts
        ir = (self.inbox_count / ct) if ct > 0 else 0
        if ir >= 0.95:
            score += 40
        elif ir >= 0.80:
            score += 28
        elif ir >= 0.60:
            score += 16
        elif ir > 0:
            score += 8

        # Reply rate — 30 pts
        rr = (self.reply_count / self.total_sent) if self.total_sent > 0 else 0
        if rr >= 0.20:
            score += 30
        elif rr >= 0.10:
            score += 22
        elif rr >= 0.05:
            score += 14
        elif rr > 0:
            score += 6

        # Low spam — 20 pts (penalty if high)
        if ct > 0:
            sr = self.spam_count / ct
            if sr <= 0.02:
                score += 20
            elif sr <= 0.05:
                score += 12
            elif sr <= 0.10:
                score += 5
            else:
                score -= 15

        # Day progress — 10 pts
        if self.day_number >= 30:
            score += 10
        elif self.day_number >= 21:
            score += 7
        elif self.day_number >= 14:
            score += 4
        elif self.day_number >= 7:
            score += 2

        return max(0, min(100, score))

    def __str__(self):
        return f"Warmup: {self.smtp_credential.from_email} (Day {self.day_number})"


class WarmupPool(models.Model):
    """Extra email addresses that join the warmup exchange pool."""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='warmup_pool')
    email = models.EmailField()
    smtp_host = models.CharField(max_length=255)
    smtp_port = models.IntegerField(default=587)
    imap_host = models.CharField(max_length=255, blank=True, help_text="Leave blank to auto-detect")
    username = models.CharField(max_length=255)
    password = models.CharField(max_length=500)  # encrypted via core.encryption
    use_tls = models.BooleanField(default=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'email')

    @property
    def decrypted_password(self):
        from core.encryption import decrypt_password
        return decrypt_password(self.password)

    def __str__(self):
        return self.email


class WarmupEmail(models.Model):
    """Log of every warmup email sent."""
    PLACEMENT_CHOICES = [
        ('unknown', 'Not Checked Yet'),
        ('inbox', 'Landed in Inbox ✅'),
        ('spam', 'Went to Spam ⚠️'),
    ]

    account = models.ForeignKey(WarmupAccount, on_delete=models.CASCADE, related_name='warmup_emails')
    to_email = models.EmailField()
    subject = models.CharField(max_length=255)
    message_id = models.CharField(max_length=255, blank=True, db_index=True)

    sent_at = models.DateTimeField(auto_now_add=True)
    placement = models.CharField(max_length=10, choices=PLACEMENT_CHOICES, default='unknown')
    checked_at = models.DateTimeField(null=True, blank=True)
    is_replied = models.BooleanField(default=False)
    replied_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-sent_at']

    def __str__(self):
        return f"{self.account.smtp_credential.from_email} → {self.to_email} [{self.placement}]"


class WarmupDailyScore(models.Model):
    """Daily snapshot saved once per account per day."""
    account = models.ForeignKey(WarmupAccount, on_delete=models.CASCADE, related_name='daily_scores')
    date = models.DateField()
    day_number = models.IntegerField(default=0)
    score = models.IntegerField(default=0)
    inbox_rate = models.FloatField(default=0)
    spam_rate = models.FloatField(default=0)
    reply_rate = models.FloatField(default=0)
    emails_sent = models.IntegerField(default=0)
    volume = models.IntegerField(default=0)

    class Meta:
        unique_together = ('account', 'date')
        ordering = ['date']

    def __str__(self):
        return f"Score {self.score} — {self.account.smtp_credential.from_email} on {self.date}"
