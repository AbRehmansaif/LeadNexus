from django.db import models


class SubscriptionPlan(models.Model):
    name = models.CharField(max_length=100, help_text="e.g. 'INITIATE', 'PROFESSIONAL'")
    badge = models.CharField(max_length=100, blank=True, null=True, help_text="e.g. 'MOST POWERFUL'")
    short_description = models.CharField(max_length=200, blank=True, null=True, default="For growing teams", help_text="Text below the price")
    monthly_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    yearly_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, help_text="Price per month when billed annually")
    is_custom_pricing = models.BooleanField(default=False, help_text="Check if price should just say CUSTOM")
    features = models.TextField(help_text="Enter one feature per line")
    btn_text = models.CharField(max_length=100, default="Initiate Growth")
    btn_url_name = models.CharField(max_length=100, default="login")
    is_featured = models.BooleanField(default=False, help_text="Highlights the card and makes it larger")
    order = models.PositiveIntegerField(default=0, help_text="Display order")

    # Specific Quotas for Comparison Table & Logic
    job_limit = models.PositiveIntegerField(default=100, help_text="Web Scrape Jobs / mo (use 99999 for unlimited)")
    linkedin_limit = models.PositiveIntegerField(default=50, help_text="LinkedIn Searches / mo (use 99999 for unlimited)")
    outreach_limit = models.PositiveIntegerField(default=500, help_text="Email Outreach / mo (use 99999 for unlimited)")
    smtp_limit = models.PositiveIntegerField(default=2, help_text="Max SMTP Accounts")
    max_websites_per_search = models.PositiveIntegerField(default=100, help_text="Max results per search job")
    
    # Feature Toggles
    has_multi_thread = models.BooleanField(default=True, help_text="Multi-thread Extraction enabled?")
    has_csv_export = models.BooleanField(default=True, help_text="CSV Export enabled?")
    has_priority_execution = models.BooleanField(default=False, help_text="Priority Execution Core enabled?")
    has_dedicated_ip = models.BooleanField(default=False, help_text="Dedicated IP Rotation enabled?")
    
    support_level = models.CharField(max_length=100, default="Community", help_text="e.g. 'Community', 'Priority Email', 'Dedicated Manager'")

    class Meta:
        ordering = ['order']

    def __str__(self):
        return self.name

    @property
    def yearly_price_per_month(self):
        """Returns the monthly cost equivalent when billed annually."""
        if self.yearly_price and self.monthly_price and self.yearly_price > self.monthly_price:
            return round(self.yearly_price / 12)
        return int(self.yearly_price) if self.yearly_price else 0

    @property
    def billed_annually_text(self):
        """Returns the text showing the total annual billing amount."""
        if self.yearly_price and self.monthly_price and self.yearly_price > self.monthly_price:
            return f"Billed annually at ${int(self.yearly_price)}"
        if self.yearly_price:
            return f"Billed annually at ${int(self.yearly_price)}"
        return ""

    def get_features_list(self):
        return [f.strip() for f in self.features.split('\n') if f.strip()]

    def get_discount_pct(self):
        """Calculates discount percentage when billed annually."""
        monthly = self.monthly_price
        yearly_monthly = self.yearly_price_per_month
        if monthly and yearly_monthly and monthly > yearly_monthly:
            return int(((monthly - yearly_monthly) / monthly) * 100)
        return 0


# ── Signals ───────────────────────────────────────────
from django.db.models.signals import post_save
from django.dispatch import receiver

@receiver(post_save, sender=SubscriptionPlan)
def update_user_limits_on_plan_change(sender, instance, **kwargs):
    """When a global plan quota is updated, propagate changes to all users on that plan."""
    from core.models import UserProfile
    users_on_plan = UserProfile.objects.filter(plan=instance)
    for profile in users_on_plan:
        profile.apply_plan_limits()
        # Update specific fields to avoid triggering a full recalculation if unnecessary
        profile.save(update_fields=['job_limit_monthly', 'linkedin_limit_monthly', 'smtp_limit', 'email_outreach_limit_monthly', 'max_websites_per_search', 'membership_status', 'is_paid'])
