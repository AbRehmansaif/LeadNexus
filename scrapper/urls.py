"""
URL configuration for the LeadNexus project.

Two sections:
  /api/...    → REST API endpoints (JSON responses)
  /...        → Template-based web pages (HTML)
"""
import os
from django.contrib import admin
from django.http import HttpResponse
from django.urls import path, include, reverse_lazy
from django.views.generic import TemplateView
from django.contrib.auth import views as auth_views
from core.auth_views import (
    LoginView, RegisterView, RequestPasswordResetView, 
    VerifyResetCodeView, CustomPasswordResetConfirmView,
    VerifyEmailView, ResendVerificationCodeView, VerifyRequestView
)
from core import template_views
from admintask import views as admintask_views
from django.contrib.sitemaps.views import sitemap
from scrapper.sitemaps import StaticViewSitemap, AffiliateViewSitemap, SeoViewSitemap, ToolsViewSitemap

sitemaps = {
    'static': StaticViewSitemap,
    'affiliate': AffiliateViewSitemap,
    'seo': SeoViewSitemap,
    'tools': ToolsViewSitemap,
}

def robots_txt_view(request):
    robots_path = os.path.join(os.path.dirname(__file__), '..', 'templates', 'robots.txt')
    with open(robots_path) as f:
        content = f.read()
    return HttpResponse(content, content_type='text/plain')

urlpatterns = [
    # ── Authentication ─────────────────────────────────────
    path('login/', LoginView.as_view(), name='login'),
    path('logout/', auth_views.LogoutView.as_view(next_page='landing'), name='logout'),
    path('register/', RegisterView.as_view(), name='register'),
    path('verify-email/', VerifyEmailView.as_view(), name='verify-email'),
    path('resend-verification/', ResendVerificationCodeView.as_view(), name='resend-verification'),
    path('verify-request/', VerifyRequestView.as_view(), name='verify-request'),
    
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
    path('admin-intelligence/', include('admintask.urls')),

    # ── REST API ───────────────────────────────────────────
    path('api/', include('core.urls', namespace='core')),

    # ── Web Pages (Templates) ──────────────────────────────
    path('',                       template_views.landing_page,        name='landing'),
    path('dashboard/',             template_views.dashboard,           name='dashboard'),
    path('profile/',               template_views.profile_settings,    name='profile-settings'),
    path('profile/linkedin-accounts/', template_views.linkedin_accounts_page, name='linkedin-accounts'),
    path('subscription/',          template_views.subscription_page,    name='subscription'),
    path('',                       include('mail.urls')), 
    path('webintelligence/',       template_views.website_scraper_page, name='webintelligence'),
    path('profinder/',             template_views.linkedin_scraper_page, name='profinder'),
    path('jobs/',                  template_views.all_jobs_page,        name='all-jobs'),
    path('website-job/<int:pk>/',  template_views.website_job_detail,   name='website-job-detail'),
    path('linkedin-job/<int:pk>/', template_views.linkedin_job_detail,  name='linkedin-job-detail'),
    path('keyword-job/<int:pk>/',  template_views.keyword_job_detail,   name='keyword-job-detail'),

    # ── Contact Us ──────────────────────────────────────────
    path('contact-us/', include('contactus.urls', namespace='contactus')),

    # ── Legal Pages ─────────────────────────────────────────
    path('privacy-policy/', TemplateView.as_view(template_name='shared/privacy_policy.html'), name='privacy-policy'),
    path('terms-of-service/', TemplateView.as_view(template_name='shared/terms_of_service.html'), name='terms-of-service'),

    # ── Affiliate ───────────────────────────────────────────
    path('affiliate/', include('affiliatemarketing.urls')),

    # ── SEO Marketing Pages ──────────────────────────────
    path('', include('seo.urls')),

    # ── CSV Data Cleaner Tool ─────────────────────────────
    path('', include('csvtools.urls', namespace='csvtools')),

    
    # ── Sitemaps ──────────────────────────────────────────────
    path('sitemap.xml', sitemap, {'sitemaps': sitemaps}, name='django.contrib.sitemaps.views.sitemap'),
    
    # ── Robots.txt ──────────────────────────────────────────
    path('robots.txt', robots_txt_view, name='robots-txt'),

]

from django.conf import settings
from django.conf.urls.static import static

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

# ── Custom Error Handlers ───────────────────────────────────────────
handler404 = 'admintask.views.error_404'
handler500 = 'admintask.views.error_500'
handler403 = 'admintask.views.error_403'
handler400 = 'admintask.views.error_400'

