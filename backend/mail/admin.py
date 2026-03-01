from django.contrib import admin
from .models import SMTPCredential, EmailCampaign, Recipient

@admin.register(SMTPCredential)
class SMTPCredentialAdmin(admin.ModelAdmin):
    list_display = ('name', 'provider', 'from_email', 'host', 'port', 'is_active', 'created_at')
    list_filter = ('provider', 'is_active')
    search_fields = ('name', 'from_email', 'username')
    ordering = ('-created_at',)

class RecipientInline(admin.TabularInline):
    model = Recipient
    extra = 0
    readonly_fields = ('sent_at',)
    fields = ('email', 'name', 'status', 'sent_at')

@admin.register(EmailCampaign)
class EmailCampaignAdmin(admin.ModelAdmin):
    list_display = ('name', 'subject', 'status', 'progress_bar', 'sent_count', 'total_recipients', 'created_at')
    list_filter = ('status', 'created_at')
    search_fields = ('name', 'subject')
    inlines = [RecipientInline]
    readonly_fields = ('created_at', 'updated_at', 'total_recipients', 'sent_count', 'failed_count')
    
    def progress_bar(self, obj):
        percent = obj.progress_percentage
        return f"{percent}%"
    progress_bar.short_description = "Progress"

@admin.register(Recipient)
class RecipientAdmin(admin.ModelAdmin):
    list_display = ('email', 'name', 'campaign', 'status', 'sent_at')
    list_filter = ('status', 'campaign')
    search_fields = ('email', 'name')
    ordering = ('-sent_at',)
