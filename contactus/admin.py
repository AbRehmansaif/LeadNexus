from django.contrib import admin
from .models import ContactMessage, ContactSettings

@admin.register(ContactSettings)
class ContactSettingsAdmin(admin.ModelAdmin):
    """Admin for ContactSettings singleton."""
    def has_add_permission(self, request):
        if ContactSettings.objects.exists():
            return False
        return True

    def has_delete_permission(self, request, obj=None):
        return False

@admin.register(ContactMessage)
class ContactMessageAdmin(admin.ModelAdmin):
    list_display = ('name', 'email', 'subject', 'created_at', 'is_read')
    list_filter = ('is_read', 'created_at')
    search_fields = ('name', 'email', 'subject', 'message')
    readonly_fields = ('created_at',)
    ordering = ('-created_at',)

    def has_add_permission(self, request):
        return False # Messages should only come from the contact form
