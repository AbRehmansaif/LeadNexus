import uuid
import random
import string
import base64
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from django.conf import settings as django_settings


def generate_referral_code():
    """Generate a unique 8-character alphanumeric referral code."""
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))


# ─── Field Encryption (Fernet / AES-128-CBC) ───────────────────────────────
def _get_fernet():
    """Lazy-import Fernet to avoid import errors if cryptography not installed."""
    try:
        from cryptography.fernet import Fernet
        key = django_settings.SECRET_KEY.encode()
        # Fernet requires 32 url-safe base64 bytes; derive from SECRET_KEY
        padded = (key * 4)[:32]
        b64_key = base64.urlsafe_b64encode(padded)
        return Fernet(b64_key)
    except Exception:
        return None


def encrypt_field(value: str) -> str:
    """Encrypt a string value. Returns original if encryption unavailable."""
    if not value:
        return value
    f = _get_fernet()
    if f is None:
        return value
    try:
        return f.encrypt(value.encode()).decode()
    except Exception:
        return value


def decrypt_field(value: str) -> str:
    """Decrypt a string value. Returns original if decryption fails."""
    if not value:
        return value
    f = _get_fernet()
    if f is None:
        return value
    try:
        return f.decrypt(value.encode()).decode()
    except Exception:
        return value  # Return as-is if not encrypted (migration fallback)


class AffiliateSettings(models.Model):
    """Global admin-controlled settings for the affiliate program."""
    commission_rate = models.DecimalField(
        max_digits=5, decimal_places=2, default=20.00,
        help_text="Affiliate commission % of the plan price (e.g. 20 = 20%)"
    )
    referral_discount_rate = models.DecimalField(
        max_digits=5, decimal_places=2, default=10.00,
        help_text="Discount % off plan price for users referred by an affiliate (e.g. 10 = 10%)"
    )
    auto_approve_affiliates = models.BooleanField(
        default=False,
        help_text="If True, affiliates are approved instantly on registration"
    )
    minimum_payout = models.DecimalField(
        max_digits=10, decimal_places=2, default=50.00,
        help_text="Minimum balance required before affiliate can request a payout"
    )
    cookie_duration_days = models.PositiveIntegerField(
        default=30,
        help_text="How many days the referral cookie/session is valid"
    )

    class Meta:
        verbose_name = 'Affiliate Program Settings'
        verbose_name_plural = 'Affiliate Program Settings'

    def __str__(self):
        return f"Affiliate Settings — {self.commission_rate}% commission / {self.referral_discount_rate}% discount"

    @classmethod
    def get_settings(cls):
        try:
            obj, _ = cls.objects.get_or_create(id=1)
            return obj
        except Exception:
            class MockSettings:
                commission_rate = 20.0
                referral_discount_rate = 10.0
                auto_approve_affiliates = False
                minimum_payout = 50.0
                cookie_duration_days = 30
            return MockSettings()


class Affiliate(models.Model):
    """An affiliate partner who promotes the platform and earns commissions."""

    STATUS_CHOICES = [
        ('pending',   'Under Review'),
        ('active',    'Active'),
        ('suspended', 'Suspended'),
        ('rejected',  'Rejected'),
    ]

    PAYOUT_METHOD_CHOICES = [
        ('easypaisa', 'EasyPaisa (Pakistan)'),
        ('paypal',    'PayPal'),
        ('bank',      'Bank Transfer'),
    ]

    PROMOTION_CHOICES = [
        ('blog',       'Blog / Website'),
        ('youtube',    'YouTube Channel'),
        ('social',     'Social Media (Instagram/TikTok/X)'),
        ('newsletter', 'Newsletter / Email List'),
        ('agency',     'Agency / Consulting Firm'),
        ('community',  'Online Community / Forum'),
        ('other',      'Other'),
    ]

    user           = models.OneToOneField(User, on_delete=models.CASCADE, related_name='affiliate_profile')
    referral_code  = models.CharField(max_length=20, unique=True, default=generate_referral_code)
    status         = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')

    # ── Identity & Verification ──────────────────────────────────────────────
    full_name      = models.CharField(max_length=200, blank=True)
    phone_number   = models.CharField(max_length=20, blank=True)
    country        = models.CharField(max_length=100, blank=True, default='Pakistan')

    # ── Promotion Profile ────────────────────────────────────────────────────
    website_url       = models.URLField(blank=True)
    promotion_method  = models.CharField(max_length=30, choices=PROMOTION_CHOICES, default='blog')
    audience_size     = models.CharField(max_length=50, blank=True)
    bio               = models.TextField(blank=True)

    # ── Payout Configuration ─────────────────────────────────────────────────
    payout_method = models.CharField(max_length=20, choices=PAYOUT_METHOD_CHOICES, default='easypaisa')

    # EasyPaisa (encrypted at rest)
    easypaisa_name   = models.CharField(max_length=500, blank=True, help_text="Encrypted EasyPaisa account holder name")
    easypaisa_number = models.CharField(max_length=500, blank=True, help_text="Encrypted EasyPaisa mobile number")

    # PayPal (encrypted at rest)
    paypal_email     = models.CharField(max_length=500, blank=True, help_text="Encrypted PayPal email")

    # Bank Transfer (encrypted at rest)
    bank_account_name   = models.CharField(max_length=500, blank=True, help_text="Encrypted bank account holder name")
    bank_account_number = models.CharField(max_length=500, blank=True, help_text="Encrypted account number/IBAN")
    bank_name           = models.CharField(max_length=500, blank=True, help_text="Encrypted bank/branch name")
    bank_swift_code     = models.CharField(max_length=500, blank=True, help_text="Encrypted SWIFT/BIC code (optional)")

    # ── Balance Tracking ─────────────────────────────────────────────────────
    total_earnings         = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    paid_out               = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_signups          = models.PositiveIntegerField(default=0)
    total_paid_conversions = models.PositiveIntegerField(default=0)
    total_revenue          = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    # ── Admin ────────────────────────────────────────────────────────────────
    admin_notes      = models.TextField(blank=True)
    rejection_reason = models.TextField(blank=True)
    reviewed_at      = models.DateTimeField(null=True, blank=True)
    reviewed_by      = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name='reviewed_affiliates'
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Affiliate'

    def __str__(self):
        return f"Affiliate: {self.user.username} [{self.referral_code}] — {self.get_status_display()}"

    def get_referral_url(self):
        from django.conf import settings
        base = getattr(settings, 'SITE_URL', 'http://127.0.0.1:8000')
        return f"{base}/register/?ref={self.referral_code}"

    # ── Encrypted field accessors ─────────────────────────────────────────────
    def get_easypaisa_name(self):   return decrypt_field(self.easypaisa_name)
    def get_easypaisa_number(self): return decrypt_field(self.easypaisa_number)
    def get_paypal_email(self):     return decrypt_field(self.paypal_email)
    def get_bank_account_name(self):    return decrypt_field(self.bank_account_name)
    def get_bank_account_number(self):  return decrypt_field(self.bank_account_number)
    def get_bank_name(self):            return decrypt_field(self.bank_name)
    def get_bank_swift_code(self):      return decrypt_field(self.bank_swift_code)

    def set_payout_details(self, method, data: dict):
        """Encrypt and save payout details for the given method."""
        self.payout_method = method
        if method == 'easypaisa':
            self.easypaisa_name   = encrypt_field(data.get('easypaisa_name', ''))
            self.easypaisa_number = encrypt_field(data.get('easypaisa_number', ''))
        elif method == 'paypal':
            self.paypal_email = encrypt_field(data.get('paypal_email', ''))
        elif method == 'bank':
            self.bank_account_name   = encrypt_field(data.get('bank_account_name', ''))
            self.bank_account_number = encrypt_field(data.get('bank_account_number', ''))
            self.bank_name           = encrypt_field(data.get('bank_name', ''))
            self.bank_swift_code     = encrypt_field(data.get('bank_swift_code', ''))

    def clear_payout_details(self):
        """Wipe all payment account data."""
        self.easypaisa_name = self.easypaisa_number = ''
        self.paypal_email = ''
        self.bank_account_name = self.bank_account_number = self.bank_name = self.bank_swift_code = ''

    @property
    def available_balance(self):
        return self.total_earnings - self.paid_out

    @property
    def has_payout_configured(self):
        if self.payout_method == 'easypaisa':
            return bool(self.easypaisa_name and self.easypaisa_number)
        elif self.payout_method == 'paypal':
            return bool(self.paypal_email)
        elif self.payout_method == 'bank':
            return bool(self.bank_account_name and self.bank_account_number and self.bank_name)
        return False

    def get_payout_summary(self):
        """Return masked payout details for display."""
        if self.payout_method == 'easypaisa':
            name = self.get_easypaisa_name()
            num  = self.get_easypaisa_number()
            masked = f"****{num[-4:]}" if num and len(num) >= 4 else num
            return {'method': 'EasyPaisa', 'primary': name, 'secondary': masked}
        elif self.payout_method == 'paypal':
            email = self.get_paypal_email()
            parts = email.split('@') if email and '@' in email else ['', '']
            masked = f"{parts[0][:2]}***@{parts[1]}" if parts[0] else email
            return {'method': 'PayPal', 'primary': masked, 'secondary': 'PayPal Account'}
        elif self.payout_method == 'bank':
            name   = self.get_bank_account_name()
            number = self.get_bank_account_number()
            bank   = self.get_bank_name()
            masked = f"****{number[-4:]}" if number and len(number) >= 4 else number
            return {'method': 'Bank Transfer', 'primary': name, 'secondary': f"{bank} • {masked}"}
        return {}


class AffiliateEarning(models.Model):
    """Logs every commission earned by an affiliate when a referred user pays."""
    affiliate    = models.ForeignKey(Affiliate, on_delete=models.CASCADE, related_name='earnings')
    referred_user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='affiliate_earnings')
    plan_name        = models.CharField(max_length=100, default='Pro')
    plan_price       = models.DecimalField(max_digits=10, decimal_places=2)
    commission_rate  = models.DecimalField(max_digits=5, decimal_places=2)
    commission_amount = models.DecimalField(max_digits=10, decimal_places=2)
    is_paid_out = models.BooleanField(default=False)
    created_at  = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Affiliate Earning'

    def __str__(self):
        return f"${self.commission_amount} for {self.affiliate.user.username}"


class PayoutRequest(models.Model):
    """Affiliate withdrawal requests managed by admin."""
    STATUS_CHOICES = [
        ('pending',  'Pending'),
        ('approved', 'Approved'),
        ('paid',     'Paid'),
        ('rejected', 'Rejected'),
    ]

    affiliate     = models.ForeignKey(Affiliate, on_delete=models.CASCADE, related_name='payout_requests')
    amount        = models.DecimalField(max_digits=10, decimal_places=2)
    status        = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    payout_method = models.CharField(max_length=20, default='easypaisa')

    # Snapshot of payout details at time of request (encrypted)
    payout_snapshot = models.TextField(blank=True, help_text="Encrypted JSON snapshot of payout account details")

    admin_notes  = models.TextField(blank=True)
    requested_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-requested_at']
        verbose_name = 'Payout Request'

    def __str__(self):
        return f"${self.amount} payout for {self.affiliate.user.username} [{self.get_status_display()}]"

    def get_snapshot(self):
        import json
        if not self.payout_snapshot:
            return {}
        try:
            return json.loads(decrypt_field(self.payout_snapshot))
        except Exception:
            return {}

    def mark_paid(self):
        self.status = 'paid'
        self.processed_at = timezone.now()
        self.save()
        self.affiliate.paid_out += self.amount
        self.affiliate.save(update_fields=['paid_out'])
