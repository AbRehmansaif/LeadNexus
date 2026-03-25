from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from .models import EmailCampaign, SMTPCredential, Recipient, SentEmailLog

@login_required
def mail_dashboard(request):
    """Mail sender dashboard - overview of campaigns and SMTP status."""
    campaigns_list = EmailCampaign.objects.filter(user=request.user, steps__isnull=False).distinct().order_by('-created_at')
    
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
        'profile': request.user.profile
    })

@login_required
def campaign_detail_page(request, pk):
    """Detail page for a specific campaign with progress tracking."""
    campaign = get_object_or_404(EmailCampaign, pk=pk, user=request.user)
    
    # Sorting logic
    sort_by = request.GET.get('sort', 'activity')
    if sort_by == 'email':
        order = 'email'
    elif sort_by == 'status':
        order = 'status'
    elif sort_by == 'opened':
        order = '-is_opened'
    elif sort_by == 'replied':
        order = '-is_replied'
    else:  # activity
        order = '-last_sent_at'
        
    recipients_list = campaign.recipients.all().order_by(order)
    paginator = Paginator(recipients_list, 20) # 20 leads per page
    page_number = request.GET.get('page')
    recipients = paginator.get_page(page_number)
    
    # A/B Testing Analytics Logic
    ab_stats = {}
    try:
        logs = SentEmailLog.objects.filter(recipient__campaign=campaign).select_related('recipient', 'step')
        
        for log in logs:
            step_num = log.step.step_number if log.step else 1
            variant = log.variant_used if log.variant_used in ['A', 'B'] else 'A'
            
            if step_num not in ab_stats:
                ab_stats[step_num] = {
                    'A': {'sent': 0, 'opened': 0, 'replied': 0, 'open_rate': 0, 'reply_rate': 0},
                    'B': {'sent': 0, 'opened': 0, 'replied': 0, 'open_rate': 0, 'reply_rate': 0},
                    'winner': None,
                    'has_b': False
                }
                
            ab_stats[step_num][variant]['sent'] += 1
            if variant == 'B':
                ab_stats[step_num]['has_b'] = True
                
            if log.recipient.is_opened:
                ab_stats[step_num][variant]['opened'] += 1
            if log.recipient.is_replied:
                ab_stats[step_num][variant]['replied'] += 1
                
        # Final Calculation for UI Rates & Winner
        for step_num, variants in ab_stats.items():
            if not variants['has_b']:
                continue
                
            for v in ['A', 'B']:
                if variants[v]['sent'] > 0:
                    variants[v]['open_rate'] = round((variants[v]['opened'] / variants[v]['sent']) * 100, 1)
                    variants[v]['reply_rate'] = round((variants[v]['replied'] / variants[v]['sent']) * 100, 1)
                    
            # Auto-Determine Winner
            score_a = (variants['A']['reply_rate'] * 3) + variants['A']['open_rate']
            score_b = (variants['B']['reply_rate'] * 3) + variants['B']['open_rate']
            
            if score_a > score_b and variants['A']['sent'] > 0:
                variants['winner'] = 'A'
            elif score_b > score_a and variants['B']['sent'] > 0:
                variants['winner'] = 'B'
            elif variants['A']['sent'] > 0 and variants['B']['sent'] > 0:
                variants['winner'] = 'Tie'
    except Exception as e:
        # Fail silently in production, keeping ab_stats empty
        print(f"Analytics error for campaign {pk}: {e}")
        ab_stats = {}

    return render(request, 'mail/campaign_detail.html', {
        'active_page': 'campaigns',
        'campaign': campaign,
        'recipients': recipients,
        'current_sort': sort_by,
        'ab_stats': ab_stats,
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
