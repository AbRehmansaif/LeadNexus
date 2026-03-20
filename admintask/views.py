from django.shortcuts import render
from django.contrib.admin.views.decorators import staff_member_required
from django.db.models import Avg, Count
from admintask.models import ServerPerformanceLog, ErrorNotification

@staff_member_required
def admin_matrix(request):
    """Deep analytics console for admin to monitor latency and errors."""
    # Latency Stats
    recent_logs = ServerPerformanceLog.objects.all().order_by('-timestamp')[:100]
    
    # Path Performance
    path_stats = ServerPerformanceLog.objects.values('path').annotate(
        avg_latency=Avg('latency_seconds'),
        request_count=Count('id'),
        slowest=Avg('latency_seconds')
    ).order_by('-avg_latency')[:20]

    # Error Intel
    recent_errors = ErrorNotification.objects.all()[:50]

    return render(request, 'admin/matrix.html', {
        'active_page': 'admin-matrix',
        'recent_logs': recent_logs,
        'path_stats': path_stats,
        'recent_errors': recent_errors,
        'total_requests': ServerPerformanceLog.objects.count(),
        'avg_global_latency': round(ServerPerformanceLog.objects.aggregate(Avg('latency_seconds'))['latency_seconds__avg'] or 0, 4)
    })

# ── Custom Error Handlers ───────────────────────────────────────────
from admintask.utils.alerts import send_admin_alert

def error_404(request, exception):
    from admintask.models import GlobalSettings
    settings = GlobalSettings.objects.first()
    return render(request, '404.html', {'global_settings': settings}, status=404)

def error_500(request):
    from admintask.models import GlobalSettings
    settings = GlobalSettings.objects.first()
    
    # Send intelligence alert for 500 error
    try:
        send_admin_alert('server_error', f"Critical 500 Server Error on path: {request.path}", {
            'user': str(request.user),
            'method': request.method,
            'path': request.path
        })
    except:
        pass

    return render(request, '500.html', {'global_settings': settings}, status=500)

def error_403(request, exception=None):
    from admintask.models import GlobalSettings
    settings = GlobalSettings.objects.first()
    return render(request, '403.html', {'global_settings': settings}, status=403)

def error_400(request, exception=None):
    from admintask.models import GlobalSettings
    settings = GlobalSettings.objects.first()
    return render(request, '400.html', {'global_settings': settings}, status=400)
