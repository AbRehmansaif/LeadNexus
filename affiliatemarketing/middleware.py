"""
Middleware to capture affiliate referral codes from URL params.
When someone visits /register/?ref=ABC123, this middleware:
1. Reads the `ref` parameter
2. Validates it against the Affiliate table
3. Saves it in the session for the duration of the cookie window
"""


class AffiliateReferralMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        ref_code = request.GET.get('ref', '').strip().upper()
        if ref_code:
            try:
                from affiliatemarketing.models import Affiliate, AffiliateSettings
                Affiliate.objects.get(referral_code=ref_code, status='active')
                # Store in session — session will expire per Django session settings
                request.session['affiliate_ref'] = ref_code
                # Also track expiry
                from affiliatemarketing.models import AffiliateSettings
                settings_obj = AffiliateSettings.get_settings()
                request.session.set_expiry(settings_obj.cookie_duration_days * 86400)
            except Exception:
                pass

        response = self.get_response(request)
        return response
