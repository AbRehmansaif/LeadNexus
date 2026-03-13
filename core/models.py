"""
Django models for the Scraper app.

Two job types:
1. ScrapeJob        — Give a URL, extract contact data from that website.
2. LinkedInScrapeJob — Give a niche, search LinkedIn, scrape companies + websites.
"""
from django.db import models
from django.utils import timezone
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver

class GlobalSettings(models.Model):
    """Singleton model for system-wide configurations."""
    registrations_enabled = models.BooleanField(default=True, help_text="If disabled, new users cannot register accounts.")
    maintenance_mode = models.BooleanField(default=False, help_text="If enabled, shows a maintenance notice.")
    
    # Contact Information for Landing Page
    contact_email = models.EmailField(default="sales@leadnexus.ai", help_text="Public contact email displayed on the landing page.")
    whatsapp_number = models.CharField(max_length=20, default="+1234567890", help_text="WhatsApp number with country code (e.g. +1234567890) for the chat button.")

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

class UserProfile(models.Model):
    MEMBERSHIP_CHOICES = [
        ('free', 'Free Operative'),
        ('pro', 'Pro Operative'),
        ('enterprise', 'Enterprise'),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    membership_status = models.CharField(max_length=20, choices=MEMBERSHIP_CHOICES, default='free')
    is_verified = models.BooleanField(default=False)
    
    # SaaS Quotas (Credit System)
    job_limit_monthly = models.PositiveIntegerField(default=100, help_text="Max domains scanned per month")
    linkedin_limit_monthly = models.PositiveIntegerField(default=50, help_text="Max LinkedIn profiles scraped per month")
    smtp_limit = models.PositiveIntegerField(default=1, help_text="Max SMTP accounts allowed")
    email_outreach_limit_monthly = models.PositiveIntegerField(default=100, help_text="Max individual emails sent per month")
    
    # Usage Tracking (Current Month)
    jobs_this_month_count = models.PositiveIntegerField(default=0, verbose_name="Domains Scanned This Month")
    linkedin_this_month_count = models.PositiveIntegerField(default=0, verbose_name="Profiles Scraped This Month")
    emails_this_month_count = models.PositiveIntegerField(default=0, verbose_name="Emails Sent This Month")
    last_action_date = models.DateField(auto_now=True)
    
    # Lifetime Stats
    total_emails_sent = models.PositiveIntegerField(default=0)
    total_websites_scraped = models.PositiveIntegerField(default=0)
    total_linkedin_scraped = models.PositiveIntegerField(default=0)
    total_records_scraped = models.PositiveIntegerField(default=0, help_text="Total verified contacts found across all origins")
    
    # Payment & Subscription Status
    is_paid = models.BooleanField(default=False, help_text="True if user has an active paid subscription")
    last_payment_date = models.DateTimeField(null=True, blank=True)
    subscription_end_date = models.DateTimeField(null=True, blank=True)
    
    admin_notes = models.TextField(blank=True, help_text="Internal notes regarding this user (billing, support, etc)")
    
    avatar = models.ImageField(upload_to='avatars/', null=True, blank=True)
    bio = models.TextField(max_length=500, blank=True)
    
    def __str__(self):
        return f"Profile for {self.user.username} ({self.get_membership_status_display()})"

    def check_and_reset_quotas(self):
        """Reset all usage counters if a new month has started."""
        today = timezone.localdate()
        needs_save = False

        # Check if we switched to a new month or year
        if self.last_action_date.month != today.month or self.last_action_date.year != today.year:
            self.jobs_this_month_count = 0
            self.linkedin_this_month_count = 0
            self.emails_this_month_count = 0
            needs_save = True
        
        if needs_save:
            self.last_action_date = today
            self.save(update_fields=['jobs_this_month_count', 'linkedin_this_month_count', 'emails_this_month_count', 'last_action_date'])
            return True
        return False

    def can_scrape_website(self):
        self.check_and_reset_quotas()
        return self.jobs_this_month_count < self.job_limit_monthly

    def can_scrape_linkedin(self):
        self.check_and_reset_quotas()
        return self.linkedin_this_month_count < self.linkedin_limit_monthly

    def can_send_email(self, count=1):
        self.check_and_reset_quotas()
        return (self.emails_this_month_count + count) <= self.email_outreach_limit_monthly

    def can_add_smtp(self):
        current_count = self.user.smtp_credentials.count()
        return current_count < self.smtp_limit

    def increment_web_usage(self):
        self.check_and_reset_quotas()
        self.jobs_this_month_count += 1
        self.total_websites_scraped += 1
        self.save(update_fields=['jobs_this_month_count', 'total_websites_scraped', 'last_action_date'])

    def increment_linkedin_usage(self):
        self.check_and_reset_quotas()
        self.linkedin_this_month_count += 1
        self.total_linkedin_scraped += 1
        self.save(update_fields=['linkedin_this_month_count', 'total_linkedin_scraped', 'last_action_date'])

    def increment_email_usage(self, count=1):
        self.check_and_reset_quotas()
        self.emails_this_month_count += count
        self.total_emails_sent += count
        self.save(update_fields=['emails_this_month_count', 'total_emails_sent', 'last_action_date'])

    def increment_records_found(self, count=1):
        self.total_records_scraped += count
        self.save(update_fields=['total_records_scraped'])

    @property
    def subscription_is_active(self):
        """Returns True only if is_paid=True AND subscription_end_date is in the future (or not set)."""
        if not self.is_paid:
            return False
        if self.subscription_end_date and timezone.now() > self.subscription_end_date:
            return False
        return True


class PasswordResetCode(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    code = models.CharField(max_length=6)
    created_at = models.DateTimeField(auto_now_add=True)
    is_used = models.BooleanField(default=False)

    def is_valid(self):
        # Code valid for 15 minutes
        expiration_time = self.created_at + timezone.timedelta(minutes=15)
        return not self.is_used and timezone.now() <= expiration_time


class LinkedInAccount(models.Model):
    """Stores LinkedIn credentials for a user."""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='linkedin_accounts')
    email = models.CharField(max_length=255)
    password = models.CharField(max_length=255)
    name = models.CharField(max_length=255, blank=True, help_text="Optional nickname for this account")
    is_active = models.BooleanField(default=True, help_text="Whether this account is currently usable")
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'LinkedIn Account'

    def __str__(self):
        return f"{self.email} ({self.user.username})"


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  1.  Website Scrape Job  (give a URL → extract data)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class ScrapeJob(models.Model):
    """A single website-scraping job."""
    STATUS_CHOICES = [
        ('pending',   'Pending'),
        ('running',   'Running'),
        ('paused',    'Paused'),
        ('completed', 'Completed'),
        ('failed',    'Failed'),
        ('cancelled', 'Cancelled'),
    ]

    # Owner
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='website_jobs', null=True, blank=True)

    # Config
    name              = models.CharField(max_length=255, blank=True, help_text="Name of the job (e.g., Bulk Upload CSV)")
    url               = models.URLField(max_length=2000, blank=True, null=True, help_text="Target website URL")
    urls_to_scrape    = models.JSONField(default=list, blank=True, help_text="List of URLs for bulk scraping")
    scrape_contact    = models.BooleanField(default=True, help_text="Also scrape contact/about pages")
    max_contact_pages = models.PositiveSmallIntegerField(default=3)

    # Status
    status        = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', db_index=True)
    error_message = models.TextField(blank=True, default='')

    # Timestamps
    created_at   = models.DateTimeField(auto_now_add=True)
    started_at   = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Website Scrape Job'

    def __str__(self):
        if self.name:
            return f"WebJob #{self.pk} — {self.name} [{self.status}]"
        return f"WebJob #{self.pk} — {self.url} [{self.status}]"

    @property
    def duration_seconds(self):
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return None

class ScrapedWebsite(models.Model):
    """Data extracted from a single website (result of a ScrapeJob)."""

    job = models.ForeignKey(ScrapeJob, on_delete=models.CASCADE, related_name='results')

    website_url = models.URLField(max_length=2000)
    email       = models.EmailField(blank=True, null=True)
    phone       = models.CharField(max_length=50, blank=True, null=True)
    address     = models.TextField(blank=True, null=True)

    facebook  = models.URLField(blank=True, null=True)
    twitter   = models.URLField(blank=True, null=True)
    instagram = models.URLField(blank=True, null=True)
    linkedin  = models.URLField(blank=True, null=True)

    pages_scraped = models.JSONField(default=list, blank=True)
    scraped_at    = models.DateTimeField(default=timezone.now)

    class Meta:
        verbose_name = 'Scraped Website'

    def __str__(self):
        return f"Result for WebJob #{self.job_id} — {self.website_url}"


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  2.  LinkedIn Scrape Job  (niche search → profiles + websites)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class LinkedInScrapeJob(models.Model):

    """
    A LinkedIn scraping job.
    - Opens Chrome, navigates to LinkedIn
    - Searches for companies matching *niche*
    - Scrapes profiles one-by-one (with delays)
    - Optionally visits associated websites and scrapes them
    - Saves results
    """

    STATUS_CHOICES = [
        ('pending',   'Pending'),
        ('running',   'Running'),
        ('paused',    'Paused'),
        ('completed', 'Completed'),
        ('failed',    'Failed'),
        ('cancelled', 'Cancelled'),
    ]

    # Owner
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='linkedin_jobs', null=True, blank=True)

    # Config
    niche           = models.CharField(max_length=500, help_text="Search niche / keywords")
    max_profiles    = models.PositiveIntegerField(default=50, help_text="Max profiles to scrape")
    scrape_websites = models.BooleanField(default=True, help_text="Also visit & scrape company websites")
    headless        = models.BooleanField(default=False, help_text="Run Chrome in headless mode")

    # Filter Options (Optional)
    location      = models.CharField(max_length=255, blank=True, default='', help_text="Filter by location (e.g., London, USA)")
    company_size  = models.CharField(max_length=100, blank=True, default='', help_text="Filter by company size (e.g., 51-200 employees)")

    # LinkedIn credentials (optional — can use a stored account or manual entry)
    account = models.ForeignKey(
        LinkedInAccount, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='jobs',
        help_text="Stored LinkedIn account to use for this job"
    )
    linkedin_email    = models.CharField(max_length=255, blank=True, default='', help_text="Manual email (overridden if account selected)")
    linkedin_password = models.CharField(max_length=255, blank=True, default='', help_text="Manual password (overridden if account selected)")

    # Status
    status        = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', db_index=True)
    error_message = models.TextField(blank=True, default='')
    progress      = models.PositiveIntegerField(default=0, help_text="Profiles scraped so far")

    # Timestamps
    created_at   = models.DateTimeField(auto_now_add=True)
    started_at   = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'LinkedIn Scrape Job'

    def __str__(self):
        return f"LinkedInJob #{self.pk} - \"{self.niche}\" [{self.status}] ({self.progress}/{self.max_profiles})"

    @property
    def duration_seconds(self):
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return None



class ScrapedLinkedInProfile(models.Model):
    """A single company profile scraped from LinkedIn (child of LinkedInScrapeJob)."""

    job = models.ForeignKey(LinkedInScrapeJob, on_delete=models.CASCADE, related_name='profiles')

    # LinkedIn data
    profile_url  = models.URLField(max_length=2000)
    name         = models.CharField(max_length=500, blank=True, default='N/A')
    headline     = models.TextField(blank=True, default='N/A')
    location     = models.CharField(max_length=500, blank=True, default='N/A')
    about        = models.TextField(blank=True, default='N/A')
    company_size = models.CharField(max_length=200, blank=True, default='N/A')
    company_type = models.CharField(max_length=200, blank=True, default='N/A')
    industry     = models.CharField(max_length=300, blank=True, default='N/A')
    founded      = models.CharField(max_length=100, blank=True, default='N/A')
    website      = models.URLField(max_length=2000, blank=True, null=True)

    # Website-scraped contact data
    website_email     = models.EmailField(blank=True, null=True)
    website_phone     = models.CharField(max_length=50, blank=True, null=True)
    website_address   = models.TextField(blank=True, null=True)
    website_facebook  = models.URLField(blank=True, null=True)
    website_twitter   = models.URLField(blank=True, null=True)
    website_instagram = models.URLField(blank=True, null=True)
    website_linkedin  = models.URLField(blank=True, null=True)

    scraped_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ['id']
        verbose_name = 'Scraped LinkedIn Profile'

    def __str__(self):
        return f"{self.name} — {self.profile_url}"


# ── Signals ───────────────────────────────────────────

@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    """Automatically create a profile for every new user."""
    if created:
        UserProfile.objects.get_or_create(user=instance)

@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    """Save the profile whenever the user object is saved."""
    if hasattr(instance, 'profile'):
        instance.profile.save()
