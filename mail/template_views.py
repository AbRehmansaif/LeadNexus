from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from .models import EmailCampaign, SMTPCredential, Recipient

@login_required
def mail_dashboard(request):
    """Mail sender dashboard - overview of campaigns and SMTP status."""
    campaigns_list = EmailCampaign.objects.filter(user=request.user).order_by('-created_at')
    
    paginator = Paginator(campaigns_list, 10)
    page_number = request.GET.get('page')
    campaigns = paginator.get_page(page_number)
    
    smtp_accounts = SMTPCredential.objects.filter(user=request.user)
    
    total_emails_sent = sum(c.sent_count for c in campaigns_list)
    active_campaigns = campaigns_list.filter(status='running').count()
    
    return render(request, 'mail/dashboard.html', {
        'active_page': 'campaigns',
        'campaigns': campaigns,
        'smtp_accounts': smtp_accounts,
        'total_emails_sent': total_emails_sent,
        'active_campaigns': active_campaigns,
        'total_campaigns': campaigns_list.count(),
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
    campaign = get_object_or_404(EmailCampaign, pk=pk, user=request.user)
    recipients = campaign.recipients.all().order_by('-sent_at')
    
    return render(request, 'mail/campaign_detail.html', {
        'active_page': 'campaigns',
        'campaign': campaign,
        'recipients': recipients,
    })

@login_required
def smtp_settings_page(request):
    """Manage SMTP backend accounts."""
    accounts_list = SMTPCredential.objects.filter(user=request.user).order_by('-created_at')
    
    for account in accounts_list:
        account.check_and_reset_limit()
        
    paginator = Paginator(accounts_list, 10) # 10 accounts per page
    page_number = request.GET.get('page')
    accounts = paginator.get_page(page_number)
    
    return render(request, 'mail/smtp_settings.html', {
        'active_page': 'campaigns',
        'accounts': accounts,
        'total_accounts': accounts_list.count(),
        'active_accounts': accounts_list.filter(is_active=True).count(),
    })
