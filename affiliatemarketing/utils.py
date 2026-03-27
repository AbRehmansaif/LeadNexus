"""
Affiliate Marketing Utilities
Called when a user upgrades to a paid plan to log commissions.
"""
from decimal import Decimal


def log_affiliate_earning(user, plan_name: str, plan_price: float):
    """
    Call this whenever a referred user pays for a plan.
    
    Usage (e.g. when admin saves UserProfile with is_paid=True,
    or from a Stripe webhook):
    
        from affiliatemarketing.utils import log_affiliate_earning
        log_affiliate_earning(user, plan_name='Pro', plan_price=99.00)
    """
    try:
        from .models import Affiliate, AffiliateEarning, AffiliateSettings
        
        ref_code = getattr(user, 'profile', None) and user.profile.referred_by
        if not ref_code:
            return  # User was not referred by any affiliate

        affiliate = Affiliate.objects.get(referral_code=ref_code, status='active')
        settings_obj = AffiliateSettings.get_settings()

        price = Decimal(str(plan_price))
        rate  = settings_obj.commission_rate
        commission = (price * rate / Decimal('100')).quantize(Decimal('0.01'))

        # Log the earning
        AffiliateEarning.objects.create(
            affiliate=affiliate,
            referred_user=user,
            plan_name=plan_name,
            plan_price=price,
            commission_rate=rate,
            commission_amount=commission,
        )

        # Update affiliate totals
        affiliate.total_earnings    += commission
        affiliate.total_paid_conversions += 1
        affiliate.save(update_fields=['total_earnings', 'total_paid_conversions'])

    except Exception:
        pass  # Never crash the main payment flow due to affiliate tracking


def get_referral_discount(ref_code: str) -> Decimal:
    """
    Returns the discount % for a referral code.
    Returns 0 if code is invalid or affiliate is inactive.
    
    Usage on subscription page:
        from affiliatemarketing.utils import get_referral_discount
        discount = get_referral_discount(request.session.get('affiliate_ref', ''))
    """
    if not ref_code:
        return Decimal('0')
    try:
        from .models import Affiliate, AffiliateSettings
        Affiliate.objects.get(referral_code=ref_code, status='active')
        settings_obj = AffiliateSettings.get_settings()
        return settings_obj.referral_discount_rate
    except Exception:
        return Decimal('0')
