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
        if self.monthly_price and self.yearly_price and self.monthly_price > self.yearly_price:
            return int(((self.monthly_price - self.yearly_price) / self.monthly_price) * 100)
        return 0
