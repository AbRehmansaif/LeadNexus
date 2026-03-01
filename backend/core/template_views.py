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

@login_required
def profile_settings(request):
    """View to update user profile (bio, avatar)."""
    profile, created = UserProfile.objects.get_or_create(user=request.user)
    
    if request.method == 'POST':
        bio = request.POST.get('bio')
        avatar = request.FILES.get('avatar')
        
        profile.bio = bio
        if avatar:
            profile.avatar = avatar
        profile.save()
        messages.success(request, "Neural profile updated successfully.")
        return redirect('profile-settings')

    return render(request, 'profile_settings.html', {
        'active_page': 'profile',
        'profile': profile,
        'linkedin_accounts': LinkedInAccount.objects.filter(user=request.user)
    })


@login_required
def dashboard(request):
    """Landing page — overview stats & recent jobs."""
    website_jobs  = ScrapeJob.objects.all()
    linkedin_jobs = LinkedInScrapeJob.objects.all()

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
    total_profiles = ScrapedLinkedInProfile.objects.count()
    emails_found = (
        ScrapedWebsite.objects.exclude(email__isnull=True).exclude(email='').count()
        + ScrapedLinkedInProfile.objects.exclude(website_email__isnull=True).exclude(website_email='').count()
    )

    return render(request, 'dashboard.html', {
        'active_page':     'dashboard',
        'total_jobs':      total_jobs,
        'completed_jobs':  completed_jobs,
        'running_jobs':    running_jobs,
        'failed_jobs':     failed_jobs,
        'total_profiles':  total_profiles,
        'emails_found':    emails_found,
        'total_emails_sent': sum(c.sent_count for c in EmailCampaign.objects.all()),
        'active_campaigns': EmailCampaign.objects.filter(status='running').count(),
        'smtp_accounts': SMTPCredential.objects.all(),
        'recent_website_jobs':  website_jobs.order_by('-created_at')[:5],
        'recent_linkedin_jobs': linkedin_jobs.order_by('-created_at')[:5],
        'recent_campaigns': EmailCampaign.objects.all().order_by('-created_at')[:5],
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
    job = get_object_or_404(ScrapeJob, pk=pk)
    result = None
    try:
        result = job.result
    except ScrapedWebsite.DoesNotExist:
        pass

    return render(request, 'website_job_detail.html', {
        'active_page': 'jobs',
        'job':         job,
        'result':      result,
    })


@login_required
def linkedin_job_detail(request, pk):
    """Detail page for a LinkedIn scrape job — with all profiles."""
    job = get_object_or_404(LinkedInScrapeJob, pk=pk)
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
def all_jobs_page(request):
    """List all website and LinkedIn jobs."""
    from django.core.paginator import Paginator
    website_jobs_list  = ScrapeJob.objects.all().order_by('-created_at')
    linkedin_jobs_list = LinkedInScrapeJob.objects.all().order_by('-created_at')

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
