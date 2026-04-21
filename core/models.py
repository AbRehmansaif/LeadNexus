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



class UserProfile(models.Model):
    MEMBERSHIP_CHOICES = [
        ('free', 'Free Operative'),
        ('pro', 'Pro Operative'),
        ('enterprise', 'Enterprise'),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    plan = models.ForeignKey('subscriptions.SubscriptionPlan', on_delete=models.SET_NULL, null=True, blank=True, help_text="The active dynamic plan for this user")
    membership_status = models.CharField(max_length=20, default='free', help_text="Legacy status field - synchronized with plan name")
    is_verified = models.BooleanField(default=False)
    
    # SaaS Quotas (Credit System)
    job_limit_monthly = models.PositiveIntegerField(default=100, help_text="Max domains scanned per month")
    linkedin_limit_monthly = models.PositiveIntegerField(default=0, help_text="Max LinkedIn profiles scraped per month")
    smtp_limit = models.PositiveIntegerField(default=1, help_text="Max SMTP accounts allowed")
    email_outreach_limit_monthly = models.PositiveIntegerField(default=100, help_text="Max individual emails sent per month")
    max_websites_per_search = models.PositiveIntegerField(default=100, help_text="Max websites allowed per single search job")
    
    # Usage Tracking (Current Month)
    jobs_this_month_count = models.PositiveIntegerField(default=0, verbose_name="Domains Scanned This Month")
    linkedin_this_month_count = models.PositiveIntegerField(default=0, verbose_name="Profiles Scraped This Month")
    emails_this_month_count = models.PositiveIntegerField(default=0, verbose_name="Emails Sent This Month")
    last_action_date = models.DateField(auto_now=True)
    has_sent_80_percent_alert = models.BooleanField(default=False, help_text="Prevents duplicate quota alerts in the same month")
    
    # Lifetime Stats
    total_emails_sent = models.PositiveIntegerField(default=0)
    total_websites_scraped = models.PositiveIntegerField(default=0)
    total_linkedin_scraped = models.PositiveIntegerField(default=0)
    total_records_scraped = models.PositiveIntegerField(default=0, help_text="Total verified contacts found across all origins")
    
    # Affiliate / Referral
    referred_by = models.CharField(max_length=20, blank=True, null=True, help_text="Affiliate referral code used during signup")

    # Payment & Subscription Status
    is_paid = models.BooleanField(default=False, help_text="True if user has an active paid subscription")
    last_payment_date = models.DateTimeField(null=True, blank=True)
    subscription_end_date = models.DateTimeField(null=True, blank=True)

    def apply_plan_limits(self):
        """Sets the quota fields according to the current linked plan."""
        plan = self.plan
        
        # Fallback if no plan is linked yet
        if not plan:
            from subscriptions.models import SubscriptionPlan
            # Try to get the first plan (likely Free) as default
            plan = SubscriptionPlan.objects.filter(order=0).first()
            if plan:
                self.plan = plan
        
        if plan:
            self.job_limit_monthly = plan.job_limit
            self.linkedin_limit_monthly = plan.linkedin_limit
            self.smtp_limit = plan.smtp_limit
            self.email_outreach_limit_monthly = plan.outreach_limit
            self.max_websites_per_search = plan.max_websites_per_search
            
            # Sync membership_status string for legacy compatibility
            self.membership_status = plan.name.lower()
            
            # Sync is_paid flag for convenience
            # We assume anything with a price > 0 is a paid plan
            if plan.monthly_price and plan.monthly_price > 0:
                self.is_paid = True
            else:
                self.is_paid = False

    def save(self, *args, **kwargs):
        # If this is a new profile OR the plan has changed
        if not self.pk:
            self.apply_plan_limits()
        else:
            try:
                old_instance = UserProfile.objects.get(pk=self.pk)
                if old_instance.plan != self.plan:
                    self.apply_plan_limits()
            except UserProfile.DoesNotExist:
                self.apply_plan_limits()
        
        super().save(*args, **kwargs)
    
    admin_notes = models.TextField(blank=True, help_text="Internal notes regarding this user (billing, support, etc)")
    
    avatar = models.ImageField(upload_to='avatars/', null=True, blank=True)
    bio = models.TextField(max_length=500, blank=True)
    tracking_domain = models.CharField(max_length=255, blank=True, null=True, help_text="Custom domain for tracking pixel (e.g., link.yourdomain.com)")
    
    # Global Outreach Schedule Defaults
    default_send_window_start = models.TimeField(null=True, blank=True, default="09:00")
    default_send_window_end = models.TimeField(null=True, blank=True, default="17:00")
    default_work_days = models.JSONField(default=list, blank=True)
    
    def get_membership_status_display(self):
        """Returns the display name for the current membership status."""
        if self.plan:
            return self.plan.name
        status_map = dict(self.MEMBERSHIP_CHOICES)
        return status_map.get(self.membership_status, self.membership_status.title() if self.membership_status else 'Unknown')

    def __str__(self):
        return f"Profile for {self.user.username} ({self.get_membership_status_display()})"

    def check_subscription_expiry(self):
        """Checks if the paid subscription has expired and reverts to free plan if so."""
        if self.membership_status != 'free' and self.subscription_end_date:
            if timezone.now() > self.subscription_end_date:
                self.membership_status = 'free'
                self.is_paid = False
                self.apply_plan_limits()
                self.save(update_fields=['membership_status', 'is_paid', 'job_limit_monthly', 'linkedin_limit_monthly', 'smtp_limit', 'email_outreach_limit_monthly'])
                return True
        return False

    def check_and_reset_quotas(self):
        """Reset all usage counters if a new month has started and handle base expiration."""
        today = timezone.localdate()
        needs_save = False

        # 1. First check if the subscription itself has expired
        self.check_subscription_expiry()

        # 2. Check if we switched to a new month or year for usage reset
        if self.last_action_date.month != today.month or self.last_action_date.year != today.year:
            self.jobs_this_month_count = 0
            self.linkedin_this_month_count = 0
            self.emails_this_month_count = 0
            self.has_sent_80_percent_alert = False
            needs_save = True
        
        if needs_save:
            self.last_action_date = today
            self.save(update_fields=['jobs_this_month_count', 'linkedin_this_month_count', 'emails_this_month_count', 'last_action_date', 'has_sent_80_percent_alert'])
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
        self.check_quota_thresholds()

    def increment_linkedin_usage(self):
        self.check_and_reset_quotas()
        self.linkedin_this_month_count += 1
        self.total_linkedin_scraped += 1
        self.save(update_fields=['linkedin_this_month_count', 'total_linkedin_scraped', 'last_action_date'])
        self.check_quota_thresholds()

    def increment_email_usage(self, count=1):
        self.check_and_reset_quotas()
        self.emails_this_month_count += count
        self.total_emails_sent += count
        self.save(update_fields=['emails_this_month_count', 'total_emails_sent', 'last_action_date'])
        self.check_quota_thresholds()

    def increment_records_found(self, count=1):
        self.total_records_scraped += count
        self.save(update_fields=['total_records_scraped'])

    def check_quota_thresholds(self):
        """Monitors for usage spikes and dispatches psychological upgrade nudges."""
        if self.membership_status != 'free' or self.has_sent_80_percent_alert:
            return

        # Check if 80% threshold is reached for Web Scraper or Outreach
        web_usage_pct = (self.jobs_this_month_count / self.job_limit_monthly) * 100 if self.job_limit_monthly > 0 else 0
        email_usage_pct = (self.emails_this_month_count / self.email_outreach_limit_monthly) * 100 if self.email_outreach_limit_monthly > 0 else 0

        if web_usage_pct >= 80 or email_usage_pct >= 80:
            self.has_sent_80_percent_alert = True
            self.save(update_fields=['has_sent_80_percent_alert'])
            
            # Dispatch Async Psychological Email
            from threading import Thread
            from django.core.mail import send_mail
            from django.conf import settings

            def send_quota_nudge(u_email, u_username, u_usage):
                try:
                    subject = "Critical Intelligence Alert: Capacity Near 80%"
                    html_message = f"""
                    <html>
                    <body style="font-family: 'Segoe UI', Arial, sans-serif; background-color: #0d1117; color: #ffffff; padding: 40px;">
                        <div style="max-width: 600px; margin: 0 auto; background: #161b22; border: 1px solid #30363d; border-radius: 16px; overflow: hidden; box-shadow: 0 10px 30px rgba(0,0,0,0.5);">
                            <div style="background: #f59e0b; padding: 25px; text-align: center;">
                                <h1 style="color: #ffffff; margin: 0; font-size: 22px; letter-spacing: 1px;">QUOTA ALERT</h1>
                            </div>
                            
                            <div style="padding: 40px;">
                                <h2 style="color: #ffffff; font-size: 20px;">Hello {u_username},</h2>
                                <p style="line-height: 1.6; color: #8b949e;">Scale warning initiated. Your autonomous scraper and outreach cycles have reached <b>80% capacity</b> for this month.</p>
                                
                                <div style="margin: 25px 0; background: rgba(245, 158, 11, 0.05); border-left: 4px solid #f59e0b; padding: 15px; border-radius: 4px;">
                                    <p style="color: #ffffff; margin: 0;">Once you hit 100%, your <b>Identity Extraction</b> and <b>Cold Outreach</b> protocols will pause until next month. Your growth shouldn't have to wait.</p>
                                </div>

                                <h3 style="color: #ffffff; font-size: 18px; margin-top: 30px;">Why Operators Upgrade to Pro:</h3>
                                <table style="width: 100%; border-collapse: collapse; margin-top: 15px;">
                                    <tr>
                                        <td style="padding: 10px 0; color: #8b949e; border-bottom: 1px solid #30363d;">🔒 <b>LinkedIn Discovery:</b></td>
                                        <td style="padding: 10px 0; text-align: right; color: #10b981; border-bottom: 1px solid #30363d;">UNLOCKED</td>
                                    </tr>
                                    <tr>
                                        <td style="padding: 10px 0; color: #8b949e; border-bottom: 10px solid transparent;">🚀 <b>Scraping Velocity:</b></td>
                                        <td style="padding: 10px 0; text-align: right; color: #ffffff; border-bottom: 10px solid transparent;"><b>10X INCREASE</b></td>
                                    </tr>
                                    <tr>
                                        <td style="padding: 10px 0; color: #8b949e; border-top: 1px solid #30363d;">📧 <b>Outreach Limit:</b></td>
                                        <td style="padding: 10px 0; text-align: right; color: #ffffff; border-top: 1px solid #30363d;"><b>10,000 Monthly</b></td>
                                    </tr>
                                </table>

                                <div style="text-align: center; margin: 40px 0;">
                                    <a href="https://getleadnexus.com/subscription/" 
                                       style="background-color: #8b5cf6; color: #ffffff; padding: 15px 35px; text-decoration: none; border-radius: 8px; font-weight: bold; display: inline-block;">
                                        Scale My Infrastructure
                                    </a>
                                    <p style="margin-top: 15px; font-size: 12px; color: #484f58;">Don't let your revenue hit a hard limit. Go Pro today.</p>
                                </div>
                            </div>
                            
                            <div style="background: #21262d; padding: 20px; text-align: center; font-size: 11px; color: #484f58; border-top: 1px solid #30363d;">
                                &copy; 2026 LeadNexus. All rights reserved.
                            </div>
                        </div>
                    </body>
                    </html>
                    """
                    send_mail(subject, "Your LeadNexus quota is at 80%. Upgrade now to avoid interruption: https://getleadnexus.com/subscription/", settings.DEFAULT_FROM_EMAIL, [u_email], html_message=html_message, fail_silently=True)
                except Exception:
                    pass

            Thread(target=send_quota_nudge, args=(self.user.email, self.user.username, web_usage_pct)).start()

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


class EmailVerificationCode(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    code = models.CharField(max_length=6)
    created_at = models.DateTimeField(auto_now_add=True)
    is_used = models.BooleanField(default=False)

    def is_valid(self):
        # Code valid for 24 hours
        expiration_time = self.created_at + timezone.timedelta(hours=24)
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
    max_contact_pages = models.PositiveSmallIntegerField(default=8)

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
    email       = models.TextField(blank=True, null=True, help_text="Comma-separated verified emails")
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
    website_email     = models.TextField(blank=True, null=True, help_text="Comma-separated verified emails")
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



# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  3.  Keyword Scrape Job  (niche search → websites → contacts)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class KeywordScrapeJob(models.Model):
    """
    A Keyword-based scraping job.
    - Searches various search engines for a niche/keyword
    - Extracts a list of matching website domains
    - Scrapes each domain for contact data
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
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='keyword_jobs', null=True, blank=True)

    # Config
    niche               = models.CharField(max_length=500, help_text="Search niche / keywords")
    max_results         = models.PositiveIntegerField(default=50, help_text="Max websites to find and scrape")
    scrape_contact      = models.BooleanField(default=True, help_text="Also scrape contact/about pages")
    max_contact_pages   = models.PositiveSmallIntegerField(default=8)

    # Status
    status        = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', db_index=True)
    error_message = models.TextField(blank=True, default='')
    progress      = models.PositiveIntegerField(default=0, help_text="Websites scraped so far")

    # Timestamps
    created_at   = models.DateTimeField(auto_now_add=True)
    started_at   = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Keyword Scrape Job'

    def __str__(self):
        return f"KeywordJob #{self.pk} - \"{self.niche}\" [{self.status}] ({self.progress}/{self.max_results})"

    @property
    def duration_seconds(self):
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return None


class ScrapedKeywordWebsite(models.Model):
    """Data extracted from a website found via KeywordScrapeJob."""

    job = models.ForeignKey(KeywordScrapeJob, on_delete=models.CASCADE, related_name='results')

    website_url = models.URLField(max_length=2000)
    email       = models.TextField(blank=True, null=True, help_text="Comma-separated verified emails")
    phone       = models.CharField(max_length=50, blank=True, null=True)
    address     = models.TextField(blank=True, null=True)

    facebook  = models.URLField(blank=True, null=True)
    twitter   = models.URLField(blank=True, null=True)
    instagram = models.URLField(blank=True, null=True)
    linkedin  = models.URLField(blank=True, null=True)

    pages_scraped = models.JSONField(default=list, blank=True)
    scraped_at    = models.DateTimeField(default=timezone.now)

    class Meta:
        verbose_name = 'Scraped Keyword Website'

    def __str__(self):
        return f"Result for KeywordJob #{self.job_id} — {self.website_url}"


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
