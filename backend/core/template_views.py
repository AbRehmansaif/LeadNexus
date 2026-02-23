"""
Template-based views for the DataScraper Pro web interface.
These render HTML pages using Django templates (separate from the API views).
"""
from django.shortcuts import render, get_object_or_404

from .models import (
    ScrapeJob, ScrapedWebsite,
    LinkedInScrapeJob, ScrapedLinkedInProfile,
)


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
        'recent_website_jobs':  website_jobs.order_by('-created_at')[:5],
        'recent_linkedin_jobs': linkedin_jobs.order_by('-created_at')[:5],
    })


def website_scraper_page(request):
    """Website scraper form page."""
    return render(request, 'website_scraper.html', {
        'active_page': 'website-scraper',
    })


def linkedin_scraper_page(request):
    """LinkedIn scraper form page."""
    return render(request, 'linkedin_scraper.html', {
        'active_page': 'linkedin-scraper',
    })


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


def all_jobs_page(request):
    """List all website and LinkedIn jobs."""
    website_jobs  = ScrapeJob.objects.all().order_by('-created_at')
    linkedin_jobs = LinkedInScrapeJob.objects.all().order_by('-created_at')

    return render(request, 'all_jobs.html', {
        'active_page':    'jobs',
        'website_jobs':   website_jobs,
        'linkedin_jobs':  linkedin_jobs,
    })
