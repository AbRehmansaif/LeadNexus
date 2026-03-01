"""
URL configuration for the scrapper project.

Two sections:
  /api/...    → REST API endpoints (JSON responses)
  /...        → Template-based web pages (HTML)
"""
from django.contrib import admin
from django.urls import path, include
from django.contrib.auth import views as auth_views
from core.auth_views import LoginView
from core import template_views

urlpatterns = [
    # ── Authentication ─────────────────────────────────────
    path('login/', LoginView.as_view(), name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    # ── Django Admin ───────────────────────────────────────
    path('admin/', admin.site.urls),

    # ── REST API ───────────────────────────────────────────
    path('api/', include('core.urls', namespace='core')),

    # ── Web Pages (Templates) ──────────────────────────────
    path('',                       template_views.dashboard,           name='dashboard'),
    path('profile/',               template_views.profile_settings,    name='profile-settings'),
    path('',                       include('mail.urls')), 
    path('website-scraper/',       template_views.website_scraper_page, name='website-scraper'),
    path('linkedin-scraper/',      template_views.linkedin_scraper_page, name='linkedin-scraper'),
    path('jobs/',                  template_views.all_jobs_page,        name='all-jobs'),
    path('website-job/<int:pk>/',  template_views.website_job_detail,   name='website-job-detail'),
    path('linkedin-job/<int:pk>/', template_views.linkedin_job_detail,  name='linkedin-job-detail'),
]

from django.conf import settings
from django.conf.urls.static import static

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
