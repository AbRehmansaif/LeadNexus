"""
URL configuration for the scrapper project.

Two sections:
  /api/...    → REST API endpoints (JSON responses)
  /...        → Template-based web pages (HTML)
"""
from django.contrib import admin
from django.urls import path, include
from core import template_views

urlpatterns = [
    # ── Django Admin ───────────────────────────────────────
    path('admin/', admin.site.urls),

    # ── REST API ───────────────────────────────────────────
    path('api/', include('core.urls', namespace='core')),

    # ── Web Pages (Templates) ──────────────────────────────
    path('',                       template_views.dashboard,           name='dashboard'),
    path('website-scraper/',       template_views.website_scraper_page, name='website-scraper'),
    path('linkedin-scraper/',      template_views.linkedin_scraper_page, name='linkedin-scraper'),
    path('jobs/',                  template_views.all_jobs_page,        name='all-jobs'),
    path('website-job/<int:pk>/',  template_views.website_job_detail,   name='website-job-detail'),
    path('linkedin-job/<int:pk>/', template_views.linkedin_job_detail,  name='linkedin-job-detail'),
]
