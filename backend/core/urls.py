"""
URL configuration for the core scraper app.

Two main sections:
  /api/jobs/...           — Website scraping (give a URL)
  /api/linkedin/jobs/...  — LinkedIn scraping (give a niche)
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

app_name = 'core'

router = DefaultRouter()
router.register(r'linkedin/accounts', views.LinkedInAccountViewSet, basename='linkedin-account')

urlpatterns = [
    path('', include(router.urls)),
    # ── Website Scrape Jobs ─────────────────────────────────────
    path('jobs/',                    views.ScrapeJobListCreateView.as_view(), name='job-list-create'),
    path('jobs/bulk/',               views.bulk_scrape_jobs_csv,              name='job-bulk-create'),
    path('jobs/<int:pk>/',           views.ScrapeJobDetailView.as_view(),     name='job-detail'),
    path('jobs/<int:pk>/delete/',    views.ScrapeJobDeleteView.as_view(),     name='job-delete'),
    path('jobs/<int:pk>/status/',    views.job_status,                        name='job-status'),
    path('jobs/<int:pk>/result/',    views.job_result,                        name='job-result'),

    # ── LinkedIn Scrape Jobs ────────────────────────────────────
    path('linkedin/jobs/',                   views.LinkedInJobListCreateView.as_view(), name='linkedin-job-list-create'),
    path('linkedin/jobs/<int:pk>/',          views.LinkedInJobDetailView.as_view(),     name='linkedin-job-detail'),
    path('linkedin/jobs/<int:pk>/delete/',   views.LinkedInJobDeleteView.as_view(),     name='linkedin-job-delete'),
    path('linkedin/jobs/<int:pk>/status/',   views.linkedin_job_status,                 name='linkedin-job-status'),
    path('linkedin/jobs/<int:pk>/profiles/', views.linkedin_job_profiles,               name='linkedin-job-profiles'),

    # ── Exports (Website) ──────────────────────────────────────
    path('export/csv/',  views.export_results_csv,  name='export-csv'),
    path('export/json/', views.export_results_json, name='export-json'),

    # ── Exports (LinkedIn) ─────────────────────────────────────
    path('export/linkedin/csv/',  views.export_linkedin_csv,  name='export-linkedin-csv'),
    path('export/linkedin/json/', views.export_linkedin_json, name='export-linkedin-json'),

    # ── Dashboard ──────────────────────────────────────────────
    path('stats/', views.dashboard_stats, name='stats'),
]
