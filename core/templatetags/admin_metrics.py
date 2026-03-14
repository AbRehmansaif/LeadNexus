from django import template
from django.contrib.auth.models import User
from core.models import UserProfile, ScrapeJob, LinkedInScrapeJob
from mail.models import EmailCampaign
from subscriptions.models import SubscriptionPlan
from django.db.models import Sum
from datetime import datetime
from dateutil.relativedelta import relativedelta

register = template.Library()

@register.simple_tag
def get_nexus_metrics():
    # 1. User Statistics
    users_qs = User.objects.all()
    total_users = users_qs.count()
    
    profiles_qs = UserProfile.objects.all()
    pro_users = profiles_qs.filter(membership_status='pro').count()
    enterprise_users = profiles_qs.filter(membership_status='enterprise').count()
    free_users = profiles_qs.filter(membership_status='free').count()
    
    # 2. Financial Metrics (Estimated MRR)
    plans = SubscriptionPlan.objects.all()
    plan_prices = {p.name.lower(): p.monthly_price or 0 for p in plans}
    
    mrr = 0
    pro_plan_price = plan_prices.get('professional', plan_prices.get('pro', 299))
    mrr += pro_users * pro_plan_price
    ent_plan_price = plan_prices.get('enterprise', 999)
    mrr += enterprise_users * ent_plan_price

    # 3. Usage Metrics (For Donut Chart Instead of Traffic)
    total_websites = ScrapeJob.objects.count()
    total_linkedin = LinkedInScrapeJob.objects.count()
    total_emails = UserProfile.objects.aggregate(Sum('total_emails_sent'))['total_emails_sent__sum'] or 0
    total_campaigns = EmailCampaign.objects.count()
    
    total_system_actions = total_websites + total_linkedin + total_emails + total_campaigns

    # 4. Monthly Registrations and Revenue (Last 6 Months for Line Charts)
    import json
    import calendar
    from django.utils import timezone
    
    today = timezone.now()
    monthly_registrations = []
    monthly_revenue = []
    month_labels = []
    
    for i in range(5, -1, -1):
        target_date = today - relativedelta(months=i)
        month_label = target_date.strftime('%b') # e.g., 'Jan'
        
        # Count users who joined this specific month
        joined_count = users_qs.filter(
            date_joined__year=target_date.year,
            date_joined__month=target_date.month
        ).count()
        
        # Estimate MRR at the end of this month
        last_day = calendar.monthrange(target_date.year, target_date.month)[1]
        try:
            end_of_month = timezone.make_aware(datetime(target_date.year, target_date.month, last_day, 23, 59, 59))
        except ValueError:
            # If already aware or other issues, just use normal datetime fallback (Django handles it)
            end_of_month = datetime(target_date.year, target_date.month, last_day, 23, 59, 59)
            if timezone.is_naive(end_of_month):
                end_of_month = timezone.make_aware(end_of_month)
                
        active_up_to = profiles_qs.filter(user__date_joined__lte=end_of_month)
        m_pro_c = active_up_to.filter(membership_status='pro').count()
        m_ent_c = active_up_to.filter(membership_status='enterprise').count()
        
        m_rev = (m_pro_c * pro_plan_price) + (m_ent_c * ent_plan_price)
        
        monthly_registrations.append(joined_count)
        monthly_revenue.append(float(m_rev))
        month_labels.append(month_label)

    # 5. Monthly Goals and Conversion (Fetching from GlobalSettings)
    from core.models import GlobalSettings
    settings = GlobalSettings.objects.first()
    
    mrr_target = float(settings.mrr_target) if settings else 55000.00
    registrations_target = settings.registrations_target if settings else 1000
    
    mrr_progress = min(int((mrr / mrr_target) * 100), 100) if mrr_target > 0 else 0
    
    registrations_progress = min(int((total_users / registrations_target) * 100), 100) if registrations_target > 0 else 0
    
    paid_users = pro_users + enterprise_users
    conversion_rate = round((paid_users / total_users) * 100, 1) if total_users > 0 else 0.0

    return {
        'total_users': total_users,
        'pro_users': pro_users,
        'enterprise_users': enterprise_users,
        'free_users': free_users,
        'mrr': mrr,
        
        # Monthly Goals
        'mrr_target': mrr_target,
        'mrr_progress': mrr_progress,
        'registrations_target': registrations_target,
        'registrations_progress': registrations_progress,
        'conversion_rate': conversion_rate,
        
        # Action Metrics
        'total_websites': total_websites,
        'total_linkedin': total_linkedin,
        'total_emails': total_emails,
        'total_campaigns': total_campaigns,
        'total_system_actions': total_system_actions,
        
        # Line Chart Data (Last 6 months)
        'chart_labels': json.dumps(month_labels),
        'chart_data_revenue': json.dumps(monthly_revenue),
        'chart_data_registrations': json.dumps(monthly_registrations),
    }
