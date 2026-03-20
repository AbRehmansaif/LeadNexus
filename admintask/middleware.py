import time
from admintask.models import ServerPerformanceLog

class LatencyMiddleware:
    """Records the latency of every request and saves to the database."""
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        start_time = time.time()
        response = self.get_response(request)
        duration = time.time() - start_time

        # Ignore static and media files to avoid cluttering the DB
        if not request.path.startswith(('/static/', '/media/', '/favicon.ico')):
            try:
                ServerPerformanceLog.objects.create(
                    path=request.path,
                    method=request.method,
                    latency_seconds=round(duration, 4),
                    status_code=response.status_code,
                    user=request.user if request.user.is_authenticated else None
                )
            except:
                pass # Fail silently if DB recording fails

        return response
