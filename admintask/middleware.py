import time
import random
from django.utils import timezone
from datetime import timedelta
from admintask.models import ServerPerformanceLog, AdminTaskSettings

class LatencyMiddleware:
    """
    Optimized Latency Monitoring:
    1. Records slow requests only (based on Admin threshold).
    2. Auto-cleans old logs randomly to preserve DB storage.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        start_time = time.time()
        response = self.get_response(request)
        duration = time.time() - start_time

        # 1. Fetch Config (Optimized with Cache-like singleton access)
        config = AdminTaskSettings.objects.first()
        if not config:
            return response

        # 2. Skip if Disabled OR fast enough to be ignored
        is_slow = duration >= config.slow_request_threshold
        is_tracked_path = not request.path.startswith(('/static/', '/media/', '/favicon.ico'))

        if config.enable_performance_logging and is_slow and is_tracked_path:
            try:
                ServerPerformanceLog.objects.create(
                    path=request.path,
                    method=request.method,
                    latency_seconds=round(duration, 4),
                    status_code=response.status_code,
                    user=request.user if request.user.is_authenticated else None
                )
            except:
                pass

        # 3. Auto-Cleanup Logic (Low Frequency - 1% chance per request)
        # Prevents high database load while maintaining storage health
        if random.random() < 0.01:
            try:
                cut_off_date = timezone.now() - timedelta(days=config.retention_days)
                ServerPerformanceLog.objects.filter(timestamp__lt=cut_off_date).delete()
            except:
                pass

        return response
