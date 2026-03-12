"""
Template-based views for the DataScraper Pro web interface.
These render HTML pages using Django templates (separate from the API views).
"""
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .models import (
    ScrapeJob, ScrapedWebsite,
    LinkedInScrapeJob, ScrapedLinkedInProfile,
    UserProfile, LinkedInAccount
)
from mail.models import EmailCampaign, SMTPCredential

def landing_page(request):
    """Product introduction and attraction page - accessible without login."""
    try:
        from subscriptions.models import PlanFeature, SubscriptionPlan
        plan_rows = PlanFeature.objects.all()
        subscription_plans = list(SubscriptionPlan.objects.all())
    except Exception:
        plan_rows = []
        subscription_plans = []

    if request.user.is_authenticated:
        # If already logged in, show stats or redirect to dashboard (optional)
        # For now, let's just let them see the landing page too.
        pass
    
    return render(request, 'landing.html', {
        'active_page': 'landing',
        'plan_rows': plan_rows,
        'subscription_plans': subscription_plans,
    })

@login_required
def profile_settings(request):
    """View to update user profile (bio, avatar)."""
    from django.db.models import Sum
    from mail.models import EmailCampaign, SMTPCredential
    from .models import ScrapeJob, LinkedInScrapeJob

    profile, created = UserProfile.objects.get_or_create(user=request.user)

    if request.method == 'POST':
        bio = request.POST.get('bio', '')
        first_name = request.POST.get('first_name', '').strip()
        last_name  = request.POST.get('last_name', '').strip()
        email      = request.POST.get('email', '').strip()
        avatar     = request.FILES.get('avatar')

        profile.bio = bio
        if avatar:
            profile.avatar = avatar
        profile.save()

        # Update User fields
        request.user.first_name = first_name
        request.user.last_name  = last_name
        if email and email != request.user.email:
            request.user.email = email
        request.user.save()

        messages.success(request, "Neural profile updated successfully.")
        return redirect('profile-settings')

    # Stats for the sidebar
    website_jobs   = ScrapeJob.objects.filter(user=request.user)
    linkedin_jobs  = LinkedInScrapeJob.objects.filter(user=request.user)
    campaigns      = EmailCampaign.objects.filter(user=request.user)
    smtp_count     = SMTPCredential.objects.filter(user=request.user).count()

    # Monthly reset countdown
    from django.utils import timezone as tz
    import calendar
    today = tz.localdate()
    last_day = calendar.monthrange(today.year, today.month)[1]
    from datetime import date
    next_reset = date(today.year, today.month, last_day) if today.day < last_day else date(
        today.year + (1 if today.month == 12 else 0),
        1 if today.month == 12 else today.month + 1,
        1
    )
    days_until_reset = (next_reset - today).days + 1

    return render(request, 'profile_settings.html', {
        'active_page':        'profile',
        'profile':            profile,
        'linkedin_accounts':  LinkedInAccount.objects.filter(user=request.user),
        'website_job_count':  website_jobs.count(),
        'linkedin_job_count': linkedin_jobs.count(),
        'campaign_count':     campaigns.count(),
        'smtp_count':         smtp_count,
        'member_since':       request.user.date_joined,
        'days_until_reset':   days_until_reset,
    })


@login_required
def dashboard(request):
    """Landing page — overview stats & recent jobs."""
    website_jobs  = ScrapeJob.objects.filter(user=request.user)
    linkedin_jobs = LinkedInScrapeJob.objects.filter(user=request.user)
    user_campaigns = EmailCampaign.objects.filter(user=request.user)
    user_smtp = SMTPCredential.objects.filter(user=request.user)

    total_jobs = website_jobs.count() + linkedin_jobs.count()
    completed_jobs = (
        website_jobs.filter(status='completed').count()
        + linkedin_jobs.filter(status='completed').count()
    )
    running_jobs = (
        website_jobs.filter(status='running').count()
        + linkedin_jobs.filter(status='running').count()
    )
    failed_jobs = (
        website_jobs.filter(status='failed').count()
        + linkedin_jobs.filter(status='failed').count()
    )
    
    # Filter results by the user's jobs
    total_profiles = ScrapedLinkedInProfile.objects.filter(job__user=request.user).count()
    emails_found = (
        ScrapedWebsite.objects.filter(job__user=request.user).exclude(email__isnull=True).exclude(email='').count()
        + ScrapedLinkedInProfile.objects.filter(job__user=request.user).exclude(website_email__isnull=True).exclude(website_email='').count()
    )

    profile, _ = UserProfile.objects.get_or_create(user=request.user)
    profile.check_and_reset_quotas()
    
    # Calculate usage percentages
    web_usage_pct = (profile.jobs_this_month_count / profile.job_limit_monthly * 100) if profile.job_limit_monthly > 0 else 100
    li_usage_pct = (profile.linkedin_this_month_count / profile.linkedin_limit_monthly * 100) if profile.linkedin_limit_monthly > 0 else 100
    email_usage_pct = (profile.emails_this_month_count / profile.email_outreach_limit_monthly * 100) if profile.email_outreach_limit_monthly > 0 else 100
    
    smtp_count = user_smtp.count()
    smtp_usage_pct = (smtp_count / profile.smtp_limit * 100) if profile.smtp_limit > 0 else 100

    return render(request, 'dashboard.html', {
        'active_page':     'dashboard',
        'profile':         profile,
        'web_usage_pct':   min(web_usage_pct, 100),
        'li_usage_pct':    min(li_usage_pct, 100),
        'email_usage_pct': min(email_usage_pct, 100),
        'smtp_count':      smtp_count,
        'smtp_usage_pct':  min(smtp_usage_pct, 100),
        'web_remaining':   max(profile.job_limit_monthly - profile.jobs_this_month_count, 0),
        'li_remaining':    max(profile.linkedin_limit_monthly - profile.linkedin_this_month_count, 0),
        'email_remaining': max(profile.email_outreach_limit_monthly - profile.emails_this_month_count, 0),
        'smtp_available':  max(profile.smtp_limit - smtp_count, 0),
        'total_jobs':      total_jobs,
        'completed_jobs':  completed_jobs,
        'running_jobs':    running_jobs,
        'failed_jobs':     failed_jobs,
        'total_profiles':  total_profiles,
        'emails_found':    emails_found,
        'total_campaigns': user_campaigns.count(),
        'total_emails_sent': sum(c.sent_count for c in user_campaigns),
        'active_campaigns': user_campaigns.filter(status='running').count(),
        'smtp_accounts': user_smtp,
        'recent_website_jobs':  website_jobs.order_by('-created_at')[:5],
        'recent_linkedin_jobs': linkedin_jobs.order_by('-created_at')[:5],
        'recent_campaigns': user_campaigns.order_by('-created_at')[:5],
    })


@login_required
def website_scraper_page(request):
    """Website scraper form page."""
    return render(request, 'website_scraper.html', {
        'active_page': 'website-scraper',
    })


@login_required
def linkedin_scraper_page(request):
    """LinkedIn scraper form page — now with account management."""
    if request.method == 'POST' and 'action' in request.POST:
        action = request.POST.get('action')
        if action == 'add':
            email = request.POST.get('email')
            password = request.POST.get('password')
            name = request.POST.get('name', '')
            LinkedInAccount.objects.create(user=request.user, email=email, password=password, name=name)
            messages.success(request, f"LinkedIn account {email} added successfully.")
        elif action == 'delete':
            acc_id = request.POST.get('account_id')
            LinkedInAccount.objects.filter(user=request.user, id=acc_id).delete()
            messages.warning(request, "LinkedIn account removed.")
        elif action == 'update':
            acc_id = request.POST.get('account_id')
            email = request.POST.get('email')
            password = request.POST.get('password')
            name = request.POST.get('name', '')
            acc = get_object_or_404(LinkedInAccount, user=request.user, id=acc_id)
            acc.email = email
            if password:
                acc.password = password
            acc.name = name
            acc.save()
            messages.success(request, f"Credentials for {email} updated.")
        return redirect('linkedin-scraper')

    accounts = LinkedInAccount.objects.filter(user=request.user, is_active=True)
    return render(request, 'linkedin_scraper.html', {
        'active_page': 'linkedin-scraper',
        'accounts': accounts
    })


@login_required
def website_job_detail(request, pk):
    """Detail page for a website scrape job."""
    job = get_object_or_404(ScrapeJob, pk=pk, user=request.user)
    results = job.results.all().order_by('-scraped_at')

    emails_found = sum(1 for r in results if r.email)
    phones_found = sum(1 for r in results if r.phone)
    socials_found = sum(1 for r in results if r.facebook or r.linkedin or r.twitter or r.instagram)
    urls_to_process = list(job.urls_to_scrape) if job.urls_to_scrape else []
    if job.url and job.url not in urls_to_process:
        urls_to_process.append(job.url)
    
    total_domains = len(urls_to_process)
    progress = min(results.count(), total_domains)

    return render(request, 'website_job_detail.html', {
        'active_page': 'jobs',
        'job':         job,
        'results':     results,
        'emails_found': emails_found,
        'phones_found': phones_found,
        'socials_found': socials_found,
        'total_domains': total_domains,
        'progress': progress,
    })


@login_required
def linkedin_job_detail(request, pk):
    """Detail page for a LinkedIn scrape job — with all profiles."""
    job = get_object_or_404(LinkedInScrapeJob, pk=pk, user=request.user)
    profiles = job.profiles.all().order_by('-scraped_at')

    profiles_with_website = profiles.exclude(website__isnull=True).exclude(website='').count()
    emails_found = profiles.exclude(website_email__isnull=True).exclude(website_email='').count()
    phones_found = profiles.exclude(website_phone__isnull=True).exclude(website_phone='').count()

    return render(request, 'linkedin_job_detail.html', {
        'active_page':          'jobs',
        'job':                  job,
        'profiles':             profiles,
        'profiles_with_website': profiles_with_website,
        'emails_found':         emails_found,
        'phones_found':         phones_found,
    })


@login_required
def subscription_page(request):
    """View to show membership details and quotas."""
    profile, _ = UserProfile.objects.get_or_create(user=request.user)
    profile.check_and_reset_quotas()
    
    # Calculate usage percentages for the bars
    web_usage_pct = (profile.jobs_this_month_count / profile.job_limit_monthly * 100) if profile.job_limit_monthly > 0 else 100
    li_usage_pct = (profile.linkedin_this_month_count / profile.linkedin_limit_monthly * 100) if profile.linkedin_limit_monthly > 0 else 100
    email_usage_pct = (profile.emails_this_month_count / profile.email_outreach_limit_monthly * 100) if profile.email_outreach_limit_monthly > 0 else 100
    
    smtp_count = SMTPCredential.objects.filter(user=request.user).count()
    smtp_usage_pct = (smtp_count / profile.smtp_limit * 100) if profile.smtp_limit > 0 else 100

    # Monthly reset countdown
    from django.utils import timezone as tz
    import calendar
    from datetime import date
    today = tz.localdate()
    last_day = calendar.monthrange(today.year, today.month)[1]
    next_reset = date(today.year, today.month, last_day) if today.day < last_day else date(
        today.year + (1 if today.month == 12 else 0),
        1 if today.month == 12 else today.month + 1,
        1
    )
    days_until_reset = (next_reset - today).days + 1

    try:
        from subscriptions.models import PlanFeature, SubscriptionPlan
        plan_rows = PlanFeature.objects.all()
        subscription_plans = list(SubscriptionPlan.objects.all())
    except Exception:
        plan_rows = []
        subscription_plans = []

    return render(request, 'subscription.html', {
        'active_page': 'subscription',
        'profile': profile,
        'web_usage_pct': min(web_usage_pct, 100),
        'li_usage_pct': min(li_usage_pct, 100),
        'email_usage_pct': min(email_usage_pct, 100),
        'smtp_count': smtp_count,
        'smtp_usage_pct': min(smtp_usage_pct, 100),
        'web_remaining':     max(profile.job_limit_monthly - profile.jobs_this_month_count, 0),
        'li_remaining':      max(profile.linkedin_limit_monthly - profile.linkedin_this_month_count, 0),
        'email_remaining':   max(profile.email_outreach_limit_monthly - profile.emails_this_month_count, 0),
        'smtp_available':    max(profile.smtp_limit - smtp_count, 0),
        'days_until_reset':  days_until_reset,
        'plan_rows':         plan_rows,
        'subscription_plans': subscription_plans,
    })

@login_required
def linkedin_accounts_page(request):
    """Manage connected LinkedIn accounts."""
    from .models import LinkedInAccount
    return render(request, 'linkedin_accounts.html', {
        'active_page': 'profile',
        'linkedin_accounts': LinkedInAccount.objects.filter(user=request.user)
    })

@login_required
def all_jobs_page(request):
    """List all website and LinkedIn jobs."""
    from django.core.paginator import Paginator
    website_jobs_list  = ScrapeJob.objects.filter(user=request.user).order_by('-created_at')
    linkedin_jobs_list = LinkedInScrapeJob.objects.filter(user=request.user).order_by('-created_at')

    paginator_linkedin = Paginator(linkedin_jobs_list, 10)
    page_li = request.GET.get('page_li')
    linkedin_jobs = paginator_linkedin.get_page(page_li)

    paginator_web = Paginator(website_jobs_list, 10)
    page_web = request.GET.get('page_web')
    website_jobs = paginator_web.get_page(page_web)

    return render(request, 'all_jobs.html', {
        'active_page':    'jobs',
        'website_jobs':   website_jobs,
        'linkedin_jobs':  linkedin_jobs,
        'total_web_jobs': website_jobs_list.count(),
        'total_li_jobs': linkedin_jobs_list.count(),
    })
