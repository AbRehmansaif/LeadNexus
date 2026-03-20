from django.shortcuts import render
from django.contrib.admin.views.decorators import staff_member_required
from django.db.models import Avg, Count
from admintask.models import ServerPerformanceLog, ErrorNotification
from django.http import JsonResponse
import psutil
from datetime import datetime

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

@staff_member_required
def get_server_health(request):
    """AJAX endpoint for real-time server health data."""
    # RAM
    ram = psutil.virtual_memory()
    # Disk
    disk = psutil.disk_usage('/')
    # CPU
    cpu = psutil.cpu_percent(interval=None)
    cpu_count = psutil.cpu_count(logical=True)
    # Net
    net_io = psutil.net_io_counters()
    # Uptime
    boot_time = datetime.fromtimestamp(psutil.boot_time())
    uptime_delta = datetime.now() - boot_time
    total_seconds = int(uptime_delta.total_seconds())
    days, remainder = divmod(total_seconds, 86400)
    hours, remainder = divmod(remainder, 3600)
    uptime_str = f"{days}d {hours}h" if days > 0 else f"{hours}h"

    return JsonResponse({
        'cpu': cpu,
        'cpu_count': cpu_count,
        'ram_pct': ram.percent,
        'ram_total': f"{ram.total / (1024**3):.1f}GB",
        'ram_used': f"{ram.used / (1024**3):.1f}GB",
        'ram_free': f"{ram.available / (1024**3):.1f}GB",
        'disk_pct': disk.percent,
        'disk_total': f"{disk.total / (1024**3):.1f}GB",
        'disk_used': f"{disk.used / (1024**3):.1f}GB",
        'disk_free': f"{disk.free / (1024**3):.1f}GB",
        'net_sent': f"{net_io.bytes_sent / (1024*1024):.1f}MB",
        'net_recv': f"{net_io.bytes_recv / (1024*1024):.1f}MB",
        'uptime': uptime_str
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
