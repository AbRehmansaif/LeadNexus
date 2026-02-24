"""
Django models for the Scraper app.

Two job types:
1. ScrapeJob        — Give a URL, extract contact data from that website.
2. LinkedInScrapeJob — Give a niche, search LinkedIn, scrape companies + websites.
"""
from django.db import models
from django.utils import timezone
from django.contrib.auth.models import User

class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    avatar = models.ImageField(upload_to='avatars/', null=True, blank=True)
    bio = models.TextField(max_length=500, blank=True)
    
    def __str__(self):
        return f"Profile for {self.user.username}"


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  1.  Website Scrape Job  (give a URL → extract data)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class ScrapeJob(models.Model):
    """A single website-scraping job."""

    STATUS_CHOICES = [
        ('pending',   'Pending'),
        ('running',   'Running'),
        ('completed', 'Completed'),
        ('failed',    'Failed'),
        ('cancelled', 'Cancelled'),
    ]

    # Config
    url               = models.URLField(max_length=2000, help_text="Target website URL")
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
        return f"WebJob #{self.pk} — {self.url} [{self.status}]"

    @property
    def duration_seconds(self):
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return None


class ScrapedWebsite(models.Model):
    """Data extracted from a single website (result of a ScrapeJob)."""

    job = models.OneToOneField(ScrapeJob, on_delete=models.CASCADE, related_name='result')

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
        ('completed', 'Completed'),
        ('failed',    'Failed'),
        ('cancelled', 'Cancelled'),
    ]

    # Config
    niche           = models.CharField(max_length=500, help_text="Search niche / keywords")
    max_profiles    = models.PositiveIntegerField(default=50, help_text="Max profiles to scrape")
    scrape_websites = models.BooleanField(default=True, help_text="Also visit & scrape company websites")
    headless        = models.BooleanField(default=False, help_text="Run Chrome in headless mode")

    # LinkedIn credentials (optional — stored only if provided)
    linkedin_email    = models.CharField(max_length=255, blank=True, default='')
    linkedin_password = models.CharField(max_length=255, blank=True, default='')

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
