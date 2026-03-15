"""
API Views for the Scraper Django app.

Two modes:
  ● Website scraping  — POST a URL, extract contact data
  ● LinkedIn scraping — POST a niche, Chrome opens LinkedIn, scrapes companies + websites
"""
import csv
import json
import logging
from io import StringIO

from django.http import HttpResponse
from django.utils import timezone

from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.generics import (
    ListCreateAPIView,
    RetrieveAPIView,
    DestroyAPIView,
    UpdateAPIView,
)
from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated

from .models import (
    ScrapeJob, ScrapedWebsite,
    LinkedInScrapeJob, ScrapedLinkedInProfile,
    KeywordScrapeJob, ScrapedKeywordWebsite,
    LinkedInAccount,
)
from .serializers import (
    ScrapeJobSerializer, ScrapeJobCreateSerializer, ScrapedWebsiteSerializer,
    LinkedInScrapeJobSerializer, LinkedInScrapeJobCreateSerializer,
    LinkedInScrapeJobListSerializer, ScrapedLinkedInProfileSerializer,
    KeywordScrapeJobSerializer, KeywordScrapeJobCreateSerializer, ScrapedKeywordWebsiteSerializer,
    LinkedInAccountSerializer,
)
from .tasks import run_scrape_job_async, run_linkedin_job_async, run_keyword_job_async

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════
#  WEBSITE SCRAPING  — Give a URL → extract contact data
# ═══════════════════════════════════════════════════════════════════

class ScrapeJobListCreateView(ListCreateAPIView):
    """
    GET  /api/jobs/   → list all website-scrape jobs
    POST /api/jobs/   → create & start a new website-scrape job
    """
    def get_queryset(self):
        return ScrapeJob.objects.filter(user=self.request.user).prefetch_related('results').all()

    def get_serializer_class(self):
        if self.request.method == 'POST':
            return ScrapeJobCreateSerializer
        return ScrapeJobSerializer

    def create(self, request, *args, **kwargs):
        # Check Quota
        if not request.user.profile.can_scrape_website():
            return Response(
                {'error': 'Monthly website scraping quota reached. Upgrade your plan for more bandwidth.'},
                status=status.HTTP_403_FORBIDDEN
            )

        serializer = ScrapeJobCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        job = serializer.save(status='pending', user=request.user)
        run_scrape_job_async(job.id)
        return Response(ScrapeJobSerializer(job).data, status=status.HTTP_201_CREATED)

@api_view(['POST'])
def bulk_scrape_jobs_csv(request):
    """POST /api/jobs/bulk/ -> upload a CSV, create one ScrapeJob with all valid URLs."""
    # Check Quota
    if not request.user.profile.can_scrape_website():
        return Response(
            {'error': 'Monthly website scraping quota reached. Upgrade your plan for more bandwidth.'},
            status=status.HTTP_403_FORBIDDEN
        )

    import io
    file = request.FILES.get('file')
    if not file:
        return Response({'error': 'No file provided.'}, status=status.HTTP_400_BAD_REQUEST)

    scrape_contact = request.data.get('scrape_contact', 'true').lower() == 'true'
    try:
        max_contact_pages = int(request.data.get('max_contact_pages', 3))
    except ValueError:
        max_contact_pages = 3

    try:
        decoded_file = file.read().decode('utf-8-sig') # Handle potential BOM
        reader = csv.reader(io.StringIO(decoded_file))
        valid_urls = []

        for i, row in enumerate(reader):
            if not row:
                continue
            
            # Skip header row if it seems to contain headers
            row_text = ','.join(row).lower()
            if i == 0 and ('url' in row_text or 'domain' in row_text or 'website' in row_text):
                continue
                
            from core.scraper.validators import is_valid_url
            found_url = None
            
            for col in row:
                pot_url = col.strip()
                if not pot_url:
                    continue
                
                # Check for an identifiable domain-like segment
                # If there's a dot and it's not mostly numbers, try to extract something that looks like a domain.
                if '.' in pot_url and len(pot_url) > 3:
                     # Try simple format first
                    test_url = pot_url
                    if not test_url.startswith('http://') and not test_url.startswith('https://'):
                        test_url = 'https://' + test_url
                    
                    if is_valid_url(test_url):
                        found_url = test_url
                        break
            
            if found_url:
                valid_urls.append(found_url)
            else:
                logger.warning(f"Skipping invalid row from CSV (no URL found): {row}")

        if not valid_urls:
            return Response({'error': 'No valid URLs found in CSV.'}, status=status.HTTP_400_BAD_REQUEST)

        job = ScrapeJob.objects.create(
            user=request.user,
            name=f"Bulk Upload: {file.name}",
            urls_to_scrape=valid_urls,
            scrape_contact=scrape_contact,
            max_contact_pages=max_contact_pages,
            status='pending'
        )
        run_scrape_job_async(job.id)

        return Response({
            'message': f'Successfully queued bulk domain analysis job for {len(valid_urls)} domains.',
            'job_ids': [job.id]  # Returning as list for backward compatibility in frontend if it expects it
        }, status=status.HTTP_201_CREATED)
    except Exception as e:
        logger.exception("Failed processing bulk CSV upload")
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


class ScrapeJobDetailView(RetrieveAPIView):
    """GET /api/jobs/<id>/"""
    def get_queryset(self):
        return ScrapeJob.objects.filter(user=self.request.user).prefetch_related('results').all()
    serializer_class = ScrapeJobSerializer


class ScrapeJobDeleteView(DestroyAPIView):
    """DELETE /api/jobs/<id>/delete/"""
    def get_queryset(self):
        return ScrapeJob.objects.filter(user=self.request.user)
    serializer_class = ScrapeJobSerializer


@api_view(['GET'])
def job_status(request, pk):
    """GET /api/jobs/<id>/status/"""
    try:
        job = ScrapeJob.objects.get(pk=pk, user=request.user)
    except ScrapeJob.DoesNotExist:
        return Response({'error': 'Job not found'}, status=status.HTTP_404_NOT_FOUND)

    return Response({
        'id':               job.id,
        'status':           job.status,
        'url':              job.url,
        'created_at':       job.created_at,
        'started_at':       job.started_at,
        'completed_at':     job.completed_at,
        'duration_seconds': job.duration_seconds,
        'error_message':    job.error_message or None,
    })


@api_view(['POST'])
def toggle_job_pause(request, pk):
    """POST /api/jobs/<id>/toggle-pause/"""
    try:
        job = ScrapeJob.objects.get(pk=pk, user=request.user)
    except ScrapeJob.DoesNotExist:
        return Response({'error': 'Job not found'}, status=status.HTTP_404_NOT_FOUND)

    if job.status == 'running':
        job.status = 'paused'
    elif job.status == 'paused':
        job.status = 'running'
    else:
        return Response({'error': f'Cannot pause/resume job with status {job.status}'}, status=status.HTTP_400_BAD_REQUEST)
    
    job.save(update_fields=['status'])
    return Response({'status': job.status})


@api_view(['GET'])
def job_result(request, pk):
    """GET /api/jobs/<id>/result/"""
    try:
        job = ScrapeJob.objects.prefetch_related('results').get(pk=pk, user=request.user)
    except ScrapeJob.DoesNotExist:
        return Response({'error': 'Job not found'}, status=status.HTTP_404_NOT_FOUND)

    if job.status != 'completed':
        return Response(
            {'error': f'Job is not completed yet. Current status: {job.status}'},
            status=status.HTTP_400_BAD_REQUEST,
        )
    
    results = job.results.all()
    if not results.exists():
        return Response({'error': 'No results found'}, status=status.HTTP_404_NOT_FOUND)

    return Response(ScrapedWebsiteSerializer(results, many=True).data)


# ═══════════════════════════════════════════════════════════════════
#  LINKEDIN SCRAPING  — Give a niche → Chrome opens → scrapes
# ═══════════════════════════════════════════════════════════════════

class LinkedInJobListCreateView(ListCreateAPIView):
    """
    GET  /api/linkedin/jobs/   → list all LinkedIn scrape jobs
    POST /api/linkedin/jobs/   → create & start a new LinkedIn scrape job

    POST body example:
    {
      "niche": "digital marketing agency",
      "max_profiles": 50,
      "scrape_websites": true,
      "headless": false,
      "linkedin_email": "user@example.com",
      "linkedin_password": "secret"
    }
    """
    def get_queryset(self):
        return LinkedInScrapeJob.objects.filter(user=self.request.user).prefetch_related('profiles').all()

    def get_serializer_class(self):
        if self.request.method == 'POST':
            return LinkedInScrapeJobCreateSerializer
        return LinkedInScrapeJobListSerializer

    def create(self, request, *args, **kwargs):
        # Check Quota
        if not request.user.profile.can_scrape_linkedin():
            return Response(
                {'error': 'Monthly LinkedIn scraping quota reached. Upgrade your plan for more searches.'},
                status=status.HTTP_403_FORBIDDEN
            )

        serializer = LinkedInScrapeJobCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        job = serializer.save(status='pending', user=request.user)

        # Launch background thread
        run_linkedin_job_async(job.id)

        return Response(
            LinkedInScrapeJobListSerializer(job).data,
            status=status.HTTP_201_CREATED,
        )


class LinkedInJobDetailView(RetrieveAPIView):
    """GET /api/linkedin/jobs/<id>/  — full detail including all profiles"""
    def get_queryset(self):
        return LinkedInScrapeJob.objects.filter(user=self.request.user).prefetch_related('profiles').all()
    serializer_class = LinkedInScrapeJobSerializer


class LinkedInJobDeleteView(DestroyAPIView):
    """DELETE /api/linkedin/jobs/<id>/delete/"""
    def get_queryset(self):
        return LinkedInScrapeJob.objects.filter(user=self.request.user)
    serializer_class = LinkedInScrapeJobListSerializer


@api_view(['GET'])
def linkedin_job_status(request, pk):
    """
    GET /api/linkedin/jobs/<id>/status/   → lightweight polling endpoint
    """
    try:
        job = LinkedInScrapeJob.objects.get(pk=pk, user=request.user)
    except LinkedInScrapeJob.DoesNotExist:
        return Response({'error': 'Job not found'}, status=status.HTTP_404_NOT_FOUND)

    return Response({
        'id':               job.id,
        'niche':            job.niche,
        'status':           job.status,
        'progress':         job.progress,
        'max_profiles':     job.max_profiles,
        'created_at':       job.created_at,
        'started_at':       job.started_at,
        'completed_at':     job.completed_at,
        'duration_seconds': job.duration_seconds,
        'error_message':    job.error_message or None,
    })


@api_view(['GET'])
def linkedin_job_profiles(request, pk):
    """
    GET /api/linkedin/jobs/<id>/profiles/  → return all scraped profiles
    """
    try:
        job = LinkedInScrapeJob.objects.get(pk=pk, user=request.user)
    except LinkedInScrapeJob.DoesNotExist:
        return Response({'error': 'Job not found'}, status=status.HTTP_404_NOT_FOUND)

    profiles = job.profiles.all()
    return Response(ScrapedLinkedInProfileSerializer(profiles, many=True).data)


# ═══════════════════════════════════════════════════════════════════
#  KEYWORD SCRAPING  — Give a niche → search engine → websites → contacts
# ═══════════════════════════════════════════════════════════════════

class KeywordJobListCreateView(ListCreateAPIView):
    """
    GET  /api/keyword/jobs/   → list all keyword-scrape jobs
    POST /api/keyword/jobs/   → create & start a new keyword-scrape job
    """
    def get_queryset(self):
        return KeywordScrapeJob.objects.filter(user=self.request.user).prefetch_related('results').all()

    def get_serializer_class(self):
        if self.request.method == 'POST':
            return KeywordScrapeJobCreateSerializer
        return KeywordScrapeJobSerializer

    def create(self, request, *args, **kwargs):
        # Check Quota (Keywords consume website credits for now)
        if not request.user.profile.can_scrape_website():
            return Response(
                {'error': 'Monthly website scraping quota reached. Upgrade your plan for more searches.'},
                status=status.HTTP_403_FORBIDDEN
            )

        serializer = KeywordScrapeJobCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        job = serializer.save(status='pending', user=request.user)
        
        # Launch background thread
        run_keyword_job_async(job.id)

        return Response(KeywordScrapeJobSerializer(job).data, status=status.HTTP_201_CREATED)


class KeywordJobDetailView(RetrieveAPIView):
    """GET /api/keyword/jobs/<id>/"""
    def get_queryset(self):
        return KeywordScrapeJob.objects.filter(user=self.request.user).prefetch_related('results').all()
    serializer_class = KeywordScrapeJobSerializer


class KeywordJobDeleteView(DestroyAPIView):
    """DELETE /api/keyword/jobs/<id>/delete/"""
    def get_queryset(self):
        return KeywordScrapeJob.objects.filter(user=self.request.user)
    serializer_class = KeywordScrapeJobSerializer


@api_view(['GET'])
def keyword_job_status(request, pk):
    """GET /api/keyword/jobs/<id>/status/"""
    try:
        job = KeywordScrapeJob.objects.get(pk=pk, user=request.user)
    except KeywordScrapeJob.DoesNotExist:
        return Response({'error': 'Job not found'}, status=status.HTTP_404_NOT_FOUND)

    return Response({
        'id':               job.id,
        'niche':            job.niche,
        'status':           job.status,
        'progress':         job.progress,
        'max_results':      job.max_results,
        'created_at':       job.created_at,
        'started_at':       job.started_at,
        'completed_at':     job.completed_at,
        'duration_seconds': job.duration_seconds,
        'error_message':    job.error_message or None,
    })


@api_view(['GET'])
def keyword_job_result(request, pk):
    """GET /api/keyword/jobs/<id>/result/"""
    try:
        job = KeywordScrapeJob.objects.prefetch_related('results').get(pk=pk, user=request.user)
    except KeywordScrapeJob.DoesNotExist:
        return Response({'error': 'Job not found'}, status=status.HTTP_404_NOT_FOUND)

    results = job.results.all()
    return Response(ScrapedKeywordWebsiteSerializer(results, many=True).data)


# ═══════════════════════════════════════════════════════════════════
#  LINKEDIN CREDENTIALS — CRUD for accounts
# ═══════════════════════════════════════════════════════════════════

class LinkedInAccountViewSet(viewsets.ModelViewSet):
    """
    CRUD for LinkedIn accounts.
    - list
    - create
    - retrieve
    - update
    - destroy
    """
    serializer_class = LinkedInAccountSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return LinkedInAccount.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


# ═══════════════════════════════════════════════════════════════════
#  EXPORTS  (CSV / JSON)
# ═══════════════════════════════════════════════════════════════════

@api_view(['GET'])
def export_results_csv(request):
    """
    GET /api/export/csv/           → all website results as CSV
    GET /api/export/csv/?job_id=X  → single job
    """
    qs = ScrapedWebsite.objects.filter(job__user=request.user).select_related('job').all()
    job_id = request.query_params.get('job_id')
    if job_id:
        qs = qs.filter(job_id=job_id)

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="scraped_websites.csv"'

    writer = csv.writer(response)
    writer.writerow([
        'Job ID', 'URL', 'Email', 'Phone', 'Address',
        'Facebook', 'Twitter', 'Instagram', 'LinkedIn',
        'Pages Scraped', 'Scraped At',
    ])
    for obj in qs:
        writer.writerow([
            obj.job_id, obj.website_url,
            obj.email or '', obj.phone or '', obj.address or '',
            obj.facebook or '', obj.twitter or '', obj.instagram or '', obj.linkedin or '',
            ', '.join(obj.pages_scraped), obj.scraped_at.strftime('%Y-%m-%d %H:%M:%S'),
        ])
    return response


@api_view(['GET'])
def export_results_json(request):
    """GET /api/export/json/"""
    qs = ScrapedWebsite.objects.filter(job__user=request.user).select_related('job').all()
    job_id = request.query_params.get('job_id')
    if job_id:
        qs = qs.filter(job_id=job_id)

    data = ScrapedWebsiteSerializer(qs, many=True).data
    response = HttpResponse(
        json.dumps(data, indent=2, default=str),
        content_type='application/json',
    )
    response['Content-Disposition'] = 'attachment; filename="scraped_websites.json"'
    return response


@api_view(['GET'])
def export_linkedin_csv(request):
    """
    GET /api/export/linkedin/csv/            → all LinkedIn profiles as CSV
    GET /api/export/linkedin/csv/?job_id=X   → single job
    """
    qs = ScrapedLinkedInProfile.objects.filter(job__user=request.user).select_related('job').all()
    job_id = request.query_params.get('job_id')
    if job_id:
        qs = qs.filter(job_id=job_id)

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="linkedin_profiles.csv"'

    writer = csv.writer(response)
    writer.writerow([
        'Job ID', 'Name', 'Headline', 'Location',
        'Company Size', 'Company Type', 'Industry', 'Founded',
        'Website', 'Profile URL',
        'Website Email', 'Website Phone', 'Website Address',
        'Website Facebook', 'Website Twitter', 'Website Instagram', 'Website LinkedIn',
        'Scraped At',
    ])
    for p in qs:
        writer.writerow([
            p.job_id, p.name, p.headline, p.location,
            p.company_size, p.company_type, p.industry, p.founded,
            p.website or '', p.profile_url,
            p.website_email or '', p.website_phone or '', p.website_address or '',
            p.website_facebook or '', p.website_twitter or '', p.website_instagram or '',
            p.website_linkedin or '',
            p.scraped_at.strftime('%Y-%m-%d %H:%M:%S'),
        ])
    return response


@api_view(['GET'])
def export_linkedin_json(request):
    """GET /api/export/linkedin/json/"""
    qs = ScrapedLinkedInProfile.objects.filter(job__user=request.user).select_related('job').all()
    job_id = request.query_params.get('job_id')
    if job_id:
        qs = qs.filter(job_id=job_id)

    data = ScrapedLinkedInProfileSerializer(qs, many=True).data
    response = HttpResponse(
        json.dumps(data, indent=2, default=str),
        content_type='application/json',
    )
    response['Content-Disposition'] = 'attachment; filename="linkedin_profiles.json"'
    return response


# ═══════════════════════════════════════════════════════════════════
#  DASHBOARD STATS
# ═══════════════════════════════════════════════════════════════════

@api_view(['GET'])
def dashboard_stats(request):
    user = request.user

    # Website jobs
    web_total     = ScrapeJob.objects.filter(user=user).count()
    web_pending   = ScrapeJob.objects.filter(user=user, status='pending').count()
    web_running   = ScrapeJob.objects.filter(user=user, status='running').count()
    web_completed = ScrapeJob.objects.filter(user=user, status='completed').count()
    web_failed    = ScrapeJob.objects.filter(user=user, status='failed').count()

    with_email  = ScrapedWebsite.objects.filter(job__user=user).exclude(email__isnull=True).exclude(email='').count()
    with_phone  = ScrapedWebsite.objects.filter(job__user=user).exclude(phone__isnull=True).exclude(phone='').count()
    with_social = ScrapedWebsite.objects.filter(job__user=user).exclude(facebook__isnull=True).count()

    # LinkedIn jobs
    li_total     = LinkedInScrapeJob.objects.filter(user=user).count()
    li_pending   = LinkedInScrapeJob.objects.filter(user=user, status='pending').count()
    li_running   = LinkedInScrapeJob.objects.filter(user=user, status='running').count()
    li_completed = LinkedInScrapeJob.objects.filter(user=user, status='completed').count()
    li_failed    = LinkedInScrapeJob.objects.filter(user=user, status='failed').count()
    li_profiles  = ScrapedLinkedInProfile.objects.filter(job__user=user).count()

    # Keyword jobs
    kw_total     = KeywordScrapeJob.objects.filter(user=user).count()
    kw_pending   = KeywordScrapeJob.objects.filter(user=user, status='pending').count()
    kw_running   = KeywordScrapeJob.objects.filter(user=user, status='running').count()
    kw_completed = KeywordScrapeJob.objects.filter(user=user, status='completed').count()
    kw_failed    = KeywordScrapeJob.objects.filter(user=user, status='failed').count()

    return Response({
        'website_jobs': {
            'total':     web_total,
            'pending':   web_pending,
            'running':   web_running,
            'completed': web_completed,
            'failed':    web_failed,
            'results': {
                'with_email':  with_email,
                'with_phone':  with_phone,
                'with_social': with_social,
            },
        },
        'linkedin_jobs': {
            'total':     li_total,
            'pending':   li_pending,
            'running':   li_running,
            'completed': li_completed,
            'failed':    li_failed,
            'total_profiles_scraped': li_profiles,
        },
        'keyword_jobs': {
            'total':     kw_total,
            'pending':   kw_pending,
            'running':   kw_running,
            'completed': kw_completed,
            'failed':    kw_failed,
        },
    })
