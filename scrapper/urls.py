"""
URL configuration for the scrapper project.

Two sections:
  /api/...    → REST API endpoints (JSON responses)
  /...        → Template-based web pages (HTML)
"""
from django.contrib import admin
from django.urls import path, include, reverse_lazy
from django.contrib.auth import views as auth_views
from core.auth_views import (
    LoginView, RegisterView, RequestPasswordResetView, 
    VerifyResetCodeView, CustomPasswordResetConfirmView
)
from core import template_views

urlpatterns = [
    # ── Authentication ─────────────────────────────────────
    path('login/', LoginView.as_view(), name='login'),
    path('logout/', auth_views.LogoutView.as_view(next_page='landing'), name='logout'),
    path('register/', RegisterView.as_view(), name='register'),
    
    # Password Reset (Custom Code-based Flow)
    path('password_reset/', RequestPasswordResetView.as_view(), name='password_reset'),
    
    path('password_reset/done/', auth_views.PasswordResetDoneView.as_view(
        template_name='registration/password_reset_done.html'
    ), name='password_reset_done'),
    
    path('password_reset/verify/', VerifyResetCodeView.as_view(), name='password-verify-code'),
    path('password_reset/confirm/', CustomPasswordResetConfirmView.as_view(), name='password-reset-confirm'),
    
    # Keeping old names for potential compatibility
    path('reset/done/', auth_views.PasswordResetCompleteView.as_view(
        template_name='registration/password_reset_complete.html'
    ), name='password_reset_complete'),
    # ── Django Admin ───────────────────────────────────────
    path('admin/', admin.site.urls),

    # ── REST API ───────────────────────────────────────────
    path('api/', include('core.urls', namespace='core')),

    # ── Web Pages (Templates) ──────────────────────────────
    path('',                       template_views.landing_page,        name='landing'),
    path('dashboard/',             template_views.dashboard,           name='dashboard'),
    path('profile/',               template_views.profile_settings,    name='profile-settings'),
    path('subscription/',          template_views.subscription_page,    name='subscription'),
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
