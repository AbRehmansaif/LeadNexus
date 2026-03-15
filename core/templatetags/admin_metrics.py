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
    monthly_conversion = []
    month_labels = []
    
    for i in range(5, -1, -1):
        target_date = today - relativedelta(months=i)
        month_label = target_date.strftime('%b') # e.g., 'Jan'
        
        # Count users who joined this specific month
        joined_count = users_qs.filter(
            date_joined__year=target_date.year,
            date_joined__month=target_date.month
        ).count()
        
        # Estimate metrics at the end of this month
        last_day = calendar.monthrange(target_date.year, target_date.month)[1]
        try:
            end_of_month = timezone.make_aware(datetime(target_date.year, target_date.month, last_day, 23, 59, 59))
        except ValueError:
            end_of_month = datetime(target_date.year, target_date.month, last_day, 23, 59, 59)
            if timezone.is_naive(end_of_month):
                end_of_month = timezone.make_aware(end_of_month)
                
        active_up_to = profiles_qs.filter(user__date_joined__lte=end_of_month)
        m_pro_c = active_up_to.filter(membership_status='pro').count()
        m_ent_c = active_up_to.filter(membership_status='enterprise').count()
        m_total_c = active_up_to.count()
        
        m_rev = (m_pro_c * pro_plan_price) + (m_ent_c * ent_plan_price)
        m_conv = round(((m_pro_c + m_ent_c) / m_total_c) * 100, 1) if m_total_c > 0 else 0.0
        
        monthly_registrations.append(joined_count)
        monthly_revenue.append(float(m_rev))
        monthly_conversion.append(float(m_conv))
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

    # 6. Server Health (CPU, RAM, Disk, Network)
    server_health = {
        'cpu': 0,
        'cpu_count': 0,
        'ram': 0,
        'ram_total': "0GB",
        'disk': 0,
        'disk_total': "0GB",
        'net_sent': "0MB",
        'net_recv': "0MB",
        'uptime': "Unknown"
    }
    
    try:
        import psutil
        import time

        # CPU Usage
        server_health['cpu'] = psutil.cpu_percent(interval=None)
        server_health['cpu_count'] = psutil.cpu_count(logical=True)
        
        # RAM Usage
        ram = psutil.virtual_memory()
        server_health['ram'] = ram.percent
        server_health['ram_total'] = f"{ram.total / (1024**3):.1f}GB"
        
        # Disk Usage (Root)
        disk = psutil.disk_usage('/')
        server_health['disk'] = disk.percent
        server_health['disk_total'] = f"{disk.total / (1024**3):.1f}GB"
        
        # Network Traffic
        net_io = psutil.net_io_counters()
        server_health['net_sent'] = f"{net_io.bytes_sent / (1024*1024):.1f}MB"
        server_health['net_recv'] = f"{net_io.bytes_recv / (1024*1024):.1f}MB"
        
        # System Uptime
        boot_time_timestamp = psutil.boot_time()
        bt = datetime.fromtimestamp(boot_time_timestamp)
        uptime_delta = datetime.now() - bt
        hours, remainder = divmod(int(uptime_delta.total_seconds()), 3600)
        days, hours = divmod(hours, 24)
        if days > 0:
            server_health['uptime'] = f"{days}d {hours}h"
        else:
            server_health['uptime'] = f"{hours}h"

    except ImportError:
        pass
    except Exception:
        pass

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
        
        # Server Health
        'server': server_health,
        
        # Line Chart Data (Last 6 months)
        'chart_labels': json.dumps(month_labels),
        'chart_data_revenue': json.dumps(monthly_revenue),
        'chart_data_registrations': json.dumps(monthly_registrations),
        'chart_data_conversion': json.dumps(monthly_conversion),
    }
