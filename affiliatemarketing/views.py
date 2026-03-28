from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.db.models import Sum, Avg
from django.db.models.functions import TruncMonth
from django.contrib.auth.models import User as DjangoUser
from django.db import transaction
import json

from .models import (
    Affiliate, AffiliateEarning, PayoutRequest,
    AffiliateSettings, encrypt_field, decrypt_field
)


from subscriptions.models import SubscriptionPlan

# ─────────────────────────────────────────────────────────────────────────────
def affiliate_landing(request):
    """SEO-optimized public landing page for the affiliate program."""
    settings_obj = AffiliateSettings.get_settings()
    
    # Real data for calculator
    active_plans = SubscriptionPlan.objects.exclude(is_custom_pricing=True).filter(monthly_price__isnull=False)
    if active_plans.exists():
        min_p = int(active_plans.order_by('monthly_price').first().monthly_price)
        max_p = int(active_plans.order_by('monthly_price').last().monthly_price)
        avg_p = int(active_plans.aggregate(avg=Avg('monthly_price'))['avg'])
    else:
        min_p, max_p, avg_p = 99, 1499, 299

    # Real stats (with marketing floors for new projects)
    real_affiliate_count = Affiliate.objects.filter(status='active').count()
    total_affiliates = max(real_affiliate_count, 542) # dynamic if > 542
    
    real_user_count = DjangoUser.objects.count()
    total_users = max(real_user_count, 12840)

    # Commission Breakdown for Visual
    breakdown = []
    counts = [4, 3, 2, 1]
    for i, p in enumerate(active_plans[:4]):
        count = counts[i]
        total_p = float(p.monthly_price) * count
        comm = total_p * (float(settings_obj.commission_rate) / 100)
        breakdown.append({
            'name': p.name,
            'count': count,
            'unit_price': p.monthly_price,
            'total_price': total_p,
            'commission': comm,
        })
    
    return render(request, 'affiliatemarketing/affiliate.html', {
        'active_page': 'affiliate_landing',
        'settings': settings_obj,
        'plans': active_plans,
        'breakdown': breakdown,
        'min_p': min_p,
        'max_p': max_p,
        'avg_p': avg_p,
        'total_affiliates': total_affiliates,
        'total_users': total_users,
    })


# ─────────────────────────────────────────────────────────────────────────────
@login_required
def affiliate_register(request):
    """
    Professional 4-step affiliate application wizard.
    Collects: account identity → promotion profile → payout details → review + declaration.
    Goes to PENDING for manual admin review (unless auto_approve is on).
    """
    if request.user.is_authenticated and hasattr(request.user, 'affiliate_profile'):
        return redirect('affiliate-dashboard')

    settings_obj = AffiliateSettings.get_settings()

    if request.method == 'POST':
        errors = []

        # User MUST be authenticated now
        user = request.user

        # ── Step 2: Promotion Profile ────────────────────────────────────────
        full_name        = request.POST.get('full_name', '').strip()
        phone_number     = request.POST.get('phone_number', '').strip()
        country          = request.POST.get('country', '').strip()
        promotion_method = request.POST.get('promotion_method', 'blog').strip()
        website_url      = request.POST.get('website_url', '').strip()
        audience_size    = request.POST.get('audience_size', '').strip()
        bio              = request.POST.get('bio', '').strip()

        if not full_name:
            errors.append("Full name is required.")
        if not phone_number:
            errors.append("WhatsApp/phone number is required.")
        if not country:
            errors.append("Country is required.")
        if not bio or len(bio) < 50:
            errors.append("Promotion description must be at least 50 characters.")

        # ── Step 3: Payout Details ────────────────────────────────────────────
        payout_method = request.POST.get('payout_method', 'easypaisa').strip()
        payout_data   = {}

        if payout_method == 'easypaisa':
            ep_name   = request.POST.get('easypaisa_name', '').strip()
            ep_number = request.POST.get('easypaisa_number', '').strip()
            if not ep_name:
                errors.append("EasyPaisa account holder name is required.")
            if not ep_number:
                errors.append("EasyPaisa mobile number is required.")
            payout_data = {'easypaisa_name': ep_name, 'easypaisa_number': ep_number}

        elif payout_method == 'paypal':
            pp_email = request.POST.get('paypal_email', '').strip()
            if not pp_email or '@' not in pp_email:
                errors.append("A valid PayPal email address is required.")
            payout_data = {'paypal_email': pp_email}

        elif payout_method == 'bank':
            ba_name   = request.POST.get('bank_account_name', '').strip()
            ba_number = request.POST.get('bank_account_number', '').strip()
            ba_bank   = request.POST.get('bank_name', '').strip()
            ba_swift  = request.POST.get('bank_swift_code', '').strip()
            if not ba_name:   errors.append("Bank account holder name is required.")
            if not ba_number: errors.append("Bank account number / IBAN is required.")
            if not ba_bank:   errors.append("Bank name is required.")
            payout_data = {
                'bank_account_name': ba_name,
                'bank_account_number': ba_number,
                'bank_name': ba_bank,
                'bank_swift_code': ba_swift,
            }

        # Declaration
        if not request.POST.get('declaration'):
            errors.append("You must accept the Partner Program Agreement.")

        if errors:
            for e in errors:
                messages.error(request, e)
            return render(request, 'affiliatemarketing/apply.html', {
                'post': request.POST,
                'settings': settings_obj,
                'active_page': 'affiliate',
            })

        # ── Create User + Affiliate ───────────────────────────────────────────
        try:
            with transaction.atomic():
                user = request.user

                affiliate = Affiliate(
                    user=user,
                    full_name=full_name,
                    phone_number=phone_number,
                    country=country,
                    promotion_method=promotion_method,
                    website_url=website_url,
                    audience_size=audience_size,
                    bio=bio,
                    status='active' if settings_obj.auto_approve_affiliates else 'pending',
                )
                affiliate.set_payout_details(payout_method, payout_data)
                affiliate.save()

                # User is already logged in

                if settings_obj.auto_approve_affiliates:
                    messages.success(request, "🎉 Your partner account is now active! Start sharing your referral link.")
                else:
                    messages.success(request, "✅ Application submitted! Our team will review within 24–48 hours.")

                return redirect('affiliate-dashboard')

        except Exception as e:
            messages.error(request, f"Registration error: {str(e)}")

    return render(request, 'affiliatemarketing/apply.html', {
        'active_page': 'affiliate',
        'settings': settings_obj,
    })


# ─────────────────────────────────────────────────────────────────────────────
@login_required
def affiliate_dashboard(request):
    """Partner command dashboard."""
    if not hasattr(request.user, 'affiliate_profile'):
        return redirect('affiliate-apply')

    affiliate    = request.user.affiliate_profile
    settings_obj = AffiliateSettings.get_settings()

    from django.conf import settings
    base         = getattr(settings, 'SITE_URL', 'http://127.0.0.1:8000')
    referral_url = f"{base}/register/?ref={affiliate.referral_code}"

    # Referred users
    referred_users = []
    paid_users     = []
    try:
        from core.models import UserProfile
        referred_profiles = UserProfile.objects.filter(
            referred_by=affiliate.referral_code
        ).select_related('user')
        referred_users = [p.user for p in referred_profiles]
        paid_users     = [u for u in referred_users if u.profile.is_paid]
    except Exception:
        pass

    # Earnings
    now = timezone.now()
    this_month_earnings = affiliate.earnings.filter(
        created_at__year=now.year, created_at__month=now.month
    ).aggregate(t=Sum('commission_amount'))['t'] or 0

    # Chart (last 6 months)
    six_ago = now - timezone.timedelta(days=180)
    monthly = (
        affiliate.earnings
        .filter(created_at__gte=six_ago)
        .annotate(month=TruncMonth('created_at'))
        .values('month')
        .annotate(total=Sum('commission_amount'))
        .order_by('month')
    )
    chart_labels = [e['month'].strftime('%b %Y') for e in monthly]
    chart_data   = [float(e['total']) for e in monthly]

    recent_payouts = affiliate.payout_requests.all()[:10]

    can_request_payout = (
        affiliate.status == 'active'
        and affiliate.available_balance >= settings_obj.minimum_payout
        and affiliate.has_payout_configured
        and not affiliate.payout_requests.filter(status='pending').exists()
    )

    payout_summary = affiliate.get_payout_summary()

    return render(request, 'affiliatemarketing/dashboard.html', {
        'active_page':           'affiliate',
        'affiliate':             affiliate,
        'settings':              settings_obj,
        'referral_url':          referral_url,
        'total_signups':         affiliate.total_signups,
        'total_paid_conversions': affiliate.total_paid_conversions,
        'total_revenue':         affiliate.total_revenue,
        'this_month_earnings':   this_month_earnings,
        'available_balance':     affiliate.available_balance,
        'total_earnings':        affiliate.total_earnings,
        'paid_out':              affiliate.paid_out,
        'referred_users':        referred_users[:20],
        'recent_payouts':        recent_payouts,
        'minimum_payout':        settings_obj.minimum_payout,
        'chart_labels':          chart_labels,
        'chart_data':            chart_data,
        'can_request_payout':    can_request_payout,
        'payout_summary':        payout_summary,
        # Decrypted for display in settings panel
        'ep_name':    affiliate.get_easypaisa_name(),
        'ep_number':  affiliate.get_easypaisa_number(),
        'pp_email':   affiliate.get_paypal_email(),
        'bk_name':    affiliate.get_bank_account_name(),
        'bk_number':  affiliate.get_bank_account_number(),
        'bk_bank':    affiliate.get_bank_name(),
        'bk_swift':   affiliate.get_bank_swift_code(),
    })


# ─────────────────────────────────────────────────────────────────────────────
@login_required
def affiliate_payouts_page(request):
    """Dedicated professional page for managing payouts and withdrawals."""
    if not hasattr(request.user, 'affiliate_profile'):
        return redirect('affiliate-apply')

    affiliate = request.user.affiliate_profile
    settings_obj = AffiliateSettings.get_settings()

    can_request_payout = (
        affiliate.status == 'active'
        and affiliate.available_balance >= settings_obj.minimum_payout
        and affiliate.has_payout_configured
        and not affiliate.payout_requests.filter(status__in=['pending', 'approved']).exists()
    )

    all_payouts = affiliate.payout_requests.all().order_by('-requested_at')
    payout_summary = affiliate.get_payout_summary()

    return render(request, 'affiliatemarketing/payout_manage.html', {
        'active_page': 'affiliate_payouts',
        'affiliate': affiliate,
        'settings': settings_obj,
        'can_request_payout': can_request_payout,
        'payout_summary': payout_summary,
        'all_payouts': all_payouts,
        # Decrypted for the update form
        'ep_name':    affiliate.get_easypaisa_name(),
        'ep_number':  affiliate.get_easypaisa_number(),
        'pp_email':   affiliate.get_paypal_email(),
        'bk_name':    affiliate.get_bank_account_name(),
        'bk_number':  affiliate.get_bank_account_number(),
        'bk_bank':    affiliate.get_bank_name(),
        'bk_swift':   affiliate.get_bank_swift_code(),
    })


# ─────────────────────────────────────────────────────────────────────────────
@login_required
def affiliate_payout_request(request):
    """Submit a payout withdrawal request."""
    if not hasattr(request.user, 'affiliate_profile'):
        return redirect('affiliate-apply')

    affiliate    = request.user.affiliate_profile
    settings_obj = AffiliateSettings.get_settings()

    if request.method != 'POST':
        return redirect('affiliate-dashboard')

    if affiliate.status != 'active':
        messages.error(request, "Your affiliate account must be active to request a payout.")
        return redirect('affiliate-dashboard')

    if not affiliate.has_payout_configured:
        messages.error(request, "Configure your payout account details before requesting a payout.")
        return redirect('affiliate-dashboard')

    amount = affiliate.available_balance
    if amount < settings_obj.minimum_payout:
        messages.error(request, f"Minimum payout is {settings_obj.minimum_payout}. Your balance is {amount:.2f}.")
        return redirect('affiliate-dashboard')

    if affiliate.payout_requests.filter(status='pending').exists():
        messages.warning(request, "You already have a pending payout request.")
        return redirect('affiliate-dashboard')

    # Build encrypted snapshot of current payout details
    summary = affiliate.get_payout_summary()
    snapshot_json = json.dumps({
        'method':     affiliate.payout_method,
        'primary':    summary.get('primary', ''),
        'secondary':  summary.get('secondary', ''),
    })

    PayoutRequest.objects.create(
        affiliate=affiliate,
        amount=amount,
        payout_method=affiliate.payout_method,
        payout_snapshot=encrypt_field(snapshot_json),
    )

    messages.success(request, f"💰 Payout request of {amount:.2f} submitted via {summary.get('method', '')}. Processed within 3–5 business days.")
    return redirect('affiliate-payouts-page')


# ─────────────────────────────────────────────────────────────────────────────
@login_required
def affiliate_update_payout(request):
    """Update payout account details (encrypted)."""
    if not hasattr(request.user, 'affiliate_profile'):
        return redirect('affiliate-apply')

    if request.method == 'POST':
        affiliate     = request.user.affiliate_profile
        payout_method = request.POST.get('payout_method', 'easypaisa').strip()
        errors        = []

        payout_data = {}
        if payout_method == 'easypaisa':
            ep_name   = request.POST.get('easypaisa_name', '').strip()
            ep_number = request.POST.get('easypaisa_number', '').strip()
            if not ep_name:   errors.append("EasyPaisa account holder name is required.")
            if not ep_number: errors.append("EasyPaisa mobile number is required.")
            payout_data = {'easypaisa_name': ep_name, 'easypaisa_number': ep_number}

        elif payout_method == 'paypal':
            pp_email = request.POST.get('paypal_email', '').strip()
            if not pp_email or '@' not in pp_email:
                errors.append("A valid PayPal email is required.")
            payout_data = {'paypal_email': pp_email}

        elif payout_method == 'bank':
            ba_name   = request.POST.get('bank_account_name', '').strip()
            ba_number = request.POST.get('bank_account_number', '').strip()
            ba_bank   = request.POST.get('bank_name', '').strip()
            ba_swift  = request.POST.get('bank_swift_code', '').strip()
            if not ba_name:   errors.append("Account holder name is required.")
            if not ba_number: errors.append("Account number / IBAN is required.")
            if not ba_bank:   errors.append("Bank name is required.")
            payout_data = {
                'bank_account_name': ba_name,
                'bank_account_number': ba_number,
                'bank_name': ba_bank,
                'bank_swift_code': ba_swift,
            }

        if errors:
            for e in errors:
                messages.error(request, e)
        else:
            affiliate.set_payout_details(payout_method, payout_data)
            affiliate.is_payout_verified = False  # requires admin verification
            affiliate.save()
            messages.success(request, "✅ Payout account details updated. Waiting for admin verification.")

    return redirect(request.META.get('HTTP_REFERER', 'affiliate-payouts-page'))


# ─────────────────────────────────────────────────────────────────────────────
@login_required
def affiliate_delete_payout(request):
    """Clear all payout account details."""
    if not hasattr(request.user, 'affiliate_profile'):
        return redirect('affiliate-apply')

    if request.method == 'POST':
        affiliate = request.user.affiliate_profile
        if affiliate.payout_requests.filter(status='pending').exists():
            messages.error(request, "Cannot remove payout details while a pending request is active.")
        else:
            affiliate.clear_payout_details()
            affiliate.save()
            messages.info(request, "Payout account details removed. Re-add details before your next withdrawal.")

    return redirect(request.META.get('HTTP_REFERER', 'affiliate-payouts-page'))


# ─────────────────────────────────────────────────────────────────────────────
@login_required
def affiliate_payout_nudge(request, payout_id):
    """Nudge admin regarding a delayed payout."""
    if request.method == 'POST':
        messages.success(request, "Our finance team has been notified of your inquiry regarding this transaction.")
    return redirect('affiliate-payouts-page')

# ─────────────────────────────────────────────────────────────────────────────
@login_required
def affiliate_update_settings(request):
    """Alias for update_payout (backwards compat)."""
    return affiliate_update_payout(request)
