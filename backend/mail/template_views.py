from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from .models import EmailCampaign, SMTPCredential, Recipient

@login_required
def mail_dashboard(request):
    """Mail sender dashboard - overview of campaigns and SMTP status."""
    campaigns = EmailCampaign.objects.all().order_by('-created_at')
    smtp_accounts = SMTPCredential.objects.all()
    
    total_emails_sent = sum(c.sent_count for c in campaigns)
    active_campaigns = campaigns.filter(status='running').count()
    
    return render(request, 'mail/dashboard.html', {
        'active_page': 'campaigns',
        'campaigns': campaigns,
        'smtp_accounts': smtp_accounts,
        'total_emails_sent': total_emails_sent,
        'active_campaigns': active_campaigns,
    })

@login_required
def create_campaign_page(request):
    """Page to create a new email campaign."""
    return render(request, 'mail/create_campaign.html', {
        'active_page': 'campaigns',
    })

@login_required
def campaign_detail_page(request, pk):
    """Detail page for a specific campaign with progress tracking."""
    campaign = get_object_or_404(EmailCampaign, pk=pk)
    recipients = campaign.recipients.all().order_by('-sent_at')
    
    return render(request, 'mail/campaign_detail.html', {
        'active_page': 'campaigns',
        'campaign': campaign,
        'recipients': recipients,
    })

@login_required
def smtp_settings_page(request):
    """Manage SMTP backend accounts."""
    accounts = SMTPCredential.objects.all()
    for account in accounts:
        account.check_and_reset_limit()
    
    return render(request, 'mail/smtp_settings.html', {
        'active_page': 'campaigns',
        'accounts': accounts,
    })
