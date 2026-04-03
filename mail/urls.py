from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import SMTPCredentialViewSet, EmailCampaignViewSet, RecipientViewSet, track_open, download_campaign_csv, unsubscribe, email_dedup_tool_page, email_dedup_tool_process, email_dedup_download
from . import template_views

router = DefaultRouter()
router.register(r'smtp', SMTPCredentialViewSet, basename='smtp')
router.register(r'campaigns', EmailCampaignViewSet, basename='campaigns')
router.register(r'recipients', RecipientViewSet, basename='recipients')

urlpatterns = [
    # Template views
    path('mail/', template_views.mail_dashboard, name='mail-dashboard'),
    path('mail/campaign/create/', template_views.create_campaign_page, name='mail-campaign-create'),
    path('mail/campaign/<int:pk>/', template_views.campaign_detail_page, name='mail-campaign-detail'),
    path('mail/settings/smtp/', template_views.smtp_settings_page, name='mail-smtp-settings'),
    
    # API views
    path('mail/api/', include(router.urls)),
    
    path('mail/n/<int:recipient_id>/logo.gif', track_open, name='track-open'),
    path('mail/unsub/<int:recipient_id>/', unsubscribe, name='unsubscribe'),
    path('mail/campaign/<int:pk>/export-csv/', download_campaign_csv, name='mail-campaign-export-csv'),

    # Email Deduplication Tool
    path('mail/tools/email-dedup/', email_dedup_tool_page, name='mail-email-dedup'),
    path('mail/tools/email-dedup/process/', email_dedup_tool_process, name='mail-email-dedup-process'),
    path('mail/tools/email-dedup/download/', email_dedup_download, name='mail-email-dedup-download'),
]
