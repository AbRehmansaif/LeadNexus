from django.contrib import admin
from .models import ServerPerformanceLog, ErrorNotification, AdminTaskSettings, GlobalSettings

@admin.register(GlobalSettings)
class GlobalSettingsAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'maintenance_mode', 'registrations_enabled')
    fieldsets = (
        ('Security & Access', {
            'fields': ('maintenance_mode', 'registrations_enabled')
        }),
        ('Landing Page Info', {
            'fields': ('contact_email', 'whatsapp_number')
        }),
        ('Performance Targets', {
            'fields': ('mrr_target', 'registrations_target')
        }),
    )

    def has_add_permission(self, request):
        if self.model.objects.exists():
            return False
        return super().has_add_permission(request)

@admin.register(AdminTaskSettings)
class AdminTaskSettingsAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'enable_error_alerts')
    
    def has_add_permission(self, request):
        # Only allow one instance
        if self.model.objects.exists():
            return False
        return super().has_add_permission(request)

@admin.register(ServerPerformanceLog)
class ServerPerformanceLogAdmin(admin.ModelAdmin):
    list_display = ('timestamp', 'method', 'path', 'latency_seconds', 'status_code', 'user')
    list_filter = ('method', 'status_code', 'timestamp')
    search_fields = ('path', 'user__username')

@admin.register(ErrorNotification)
class ErrorNotificationAdmin(admin.ModelAdmin):
    list_display = ('timestamp', 'type', 'message', 'sent_to_telegram')
    list_filter = ('type', 'sent_to_telegram', 'timestamp')
    search_fields = ('message',)
