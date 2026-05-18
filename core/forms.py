from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm
from django.core.exceptions import ValidationError
from django.contrib.auth import authenticate # Added this import for authenticate function

class ProfessionalRegisterForm(UserCreationForm):
    email = forms.EmailField(required=True, help_text="Used for account identity verification.")

    class Meta(UserCreationForm.Meta):
        fields = ("username", "email")

    def clean_email(self):
        email = self.cleaned_data.get('email', '').strip().lower()
        if not email:
            return email

        # ── 1. Check for Duplicate Emails ──
        if User.objects.filter(email=email).exists():
            raise ValidationError("This email identity is already registered in the Nexus.")

        # ── 2. Comprehensive Disposable Email Prevention ──
        disposable_domains = {
            # Classic / Most Popular
            'mailinator.com', 'tempmail.com', 'temp-mail.org', 'temp-mail.io', 'temp-mail.net',
            'guerrillamail.com', 'guerrillamail.net', 'guerrillamail.org', 'guerrillamail.biz',
            'grr.la', 'guerrillamailblock.com', 'sharklasers.com', '10minutemail.com',
            'yopmail.com', 'dispostable.com', 'maildrop.cc', 'trashmail.com', 'generator.email',
            'emailondeck.com', 'tempail.com', 'fakeinbox.com', 'mintemail.com', 'mytemp.email',
            'throwawaymail.com', 'mailnesia.com', 'mailcatch.com', 'burnermail.io', 'mohmal.com',
            'tempmailo.com', 'crazymailing.com', 'boun.cr', 'mail.tm', 'mail.gw', 'secmail.pro',
            'inboxkitten.com', 'getairmail.com', 'disposable.com', 'tempmailo.com', 'pokemail.net',
            'maildu.de', 'dropmail.me', 'getnada.com', 'nada.ltd', 'tempmail.plus', 'temp-mail.com',
            'incognitomail.com', 'discard.email', 'spamex.com', 'spambox.us', 'zillamail.com',
            'deadaddress.com', 'tempinbox.com', 'mailnull.com', 'hmamail.com', 'blockspam.com',
            'tempmail.net', 'tempmailaddress.com', 'quickemail.info', 'shortmail.com',
            'fakeaddressgenerator.com', 'mytrashmail.com', 'disposableinbox.com', 'tempmail.us.com',
        }

        domain = email.split('@')[-1]
        domain_parts = domain.split('.')

        # Check all possible parent domain levels (e.g. test.sub.mailinator.com -> mailinator.com)
        for i in range(len(domain_parts) - 1):
            parent_domain = '.'.join(domain_parts[i:])
            if parent_domain in disposable_domains:
                raise ValidationError(
                    "Disposable, temporary, or burner email addresses are not permitted in the LeadNexus network. "
                    "Please use a professional email identity."
                )

        return email

    def clean_username(self):
        username = self.cleaned_data.get('username')
        if User.objects.filter(username=username).exists():
            raise ValidationError("This OPERATOR ID is already taken. Choose another.")
        return username

    def clean_password1(self):
        password = self.cleaned_data.get('password1')
        if len(password) < 8:
            raise ValidationError("Security Key must be at least 8 characters long.")
        # Additional complexity can be added here
        return password
from django.contrib.auth.forms import AuthenticationForm
class EmailAuthenticationForm(AuthenticationForm):
    username = forms.EmailField(label="Email Address", widget=forms.EmailInput(attrs={'class': 'auth-input', 'placeholder': 'operator@leadnexus.pro', 'autofocus': True}))

    def clean(self):
        from django.core.cache import cache

        email = self.cleaned_data.get('username', '').strip().lower()
        password = self.cleaned_data.get('password')

        # Robust IP extraction helper
        def get_client_ip(request):
            if not request:
                return "unknown"
            x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
            if x_forwarded_for:
                return x_forwarded_for.split(',')[0].strip()
            return request.META.get('REMOTE_ADDR', 'unknown')

        ip = get_client_ip(self.request)

        # Define high-end cache tracking keys
        ip_cache_key = f"login_attempts_ip_{ip}"
        email_cache_key = f"login_attempts_email_{email}"

        # Fetch current attempts
        ip_attempts = cache.get(ip_cache_key, 0)
        email_attempts = cache.get(email_cache_key, 0)

        # Enforce Rate Limiting before doing expensive authentication/hashing
        if ip_attempts >= 5:
            raise ValidationError(
                "Too many login attempts from this network. Operator access suspended for 15 minutes.",
                code='rate_limited'
            )

        if email and email_attempts >= 5:
            raise ValidationError(
                "Too many login attempts for this account. Operator access suspended for 15 minutes.",
                code='rate_limited'
            )

        if email and password:
            self.user_cache = authenticate(self.request, username=email, password=password)
            if self.user_cache is None:
                # Try to find user by email since username might be different
                user = User.objects.filter(email=email).first()
                if user:
                    self.user_cache = authenticate(self.request, username=user.username, password=password)
                
                if self.user_cache is None:
                    # Increment failed login attempts on authentication failure
                    cache.set(ip_cache_key, ip_attempts + 1, timeout=900) # 15 minutes
                    if email:
                        cache.set(email_cache_key, email_attempts + 1, timeout=900)
                    raise self.get_invalid_login_error()
            
            # Clear historical failed attempts immediately on successful login
            if self.user_cache is not None:
                cache.delete(ip_cache_key)
                cache.delete(email_cache_key)
                self.confirm_login_allowed(self.user_cache)

        return self.cleaned_data

    def confirm_login_allowed(self, user):
        if not user.is_active:
            raise ValidationError(
                "This operator account is currently in 'Inactive' status. If you haven't verified your identity yet, please visit the Verify Identity portal to complete your onboarding.",
                code='inactive',
            )
