from django.shortcuts import render
from django.urls import reverse
from .models import GlobalSettings

class MaintenanceModeMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # 1. Get current settings
        settings = GlobalSettings.objects.first()
        
        # 2. Check if maintenance mode is ON and user is NOT staff
        if settings and settings.maintenance_mode:
            # Allow access to admin and staff users
            is_admin_path = request.path.startswith(reverse('admin:index'))
            if not (request.user.is_staff or is_admin_path):
                return render(request, 'maintenance.html', {'global_settings': settings}, status=503)

        return self.get_response(request)
