from django.contrib import admin
from .models import SMTPCredential, EmailCampaign, Recipient, CampaignStep, SentEmailLog

@admin.register(SMTPCredential)
class SMTPCredentialAdmin(admin.ModelAdmin):
    list_display = ('name', 'provider', 'from_email', 'emails_sent_today', 'daily_limit', 'is_active', 'created_at')
    list_filter = ('provider', 'is_active')
    search_fields = ('name', 'from_email', 'username')
    ordering = ('-created_at',)

class RecipientInline(admin.TabularInline):
    model = Recipient
    extra = 0
    readonly_fields = ('last_sent_at', 'opened_at', 'replied_at')
    fields = ('email', 'name', 'status', 'current_step_index', 'is_opened', 'is_replied', 'last_sent_at')

@admin.register(EmailCampaign)
class EmailCampaignAdmin(admin.ModelAdmin):
    list_display = ('name', 'subject', 'status', 'progress_bar', 'sent_count', 'total_recipients', 'created_at')
    list_filter = ('status', 'created_at')
    search_fields = ('name', 'subject')
    inlines = [RecipientInline]
    readonly_fields = ('created_at', 'updated_at', 'total_recipients', 'sent_count', 'failed_count')
    
    @admin.display(description="Progress")
    def progress_bar(self, obj):
        percent = obj.progress_percentage
        return f"{percent}%"

@admin.register(Recipient)
class RecipientAdmin(admin.ModelAdmin):
    list_display = ('email', 'name', 'campaign', 'status', 'current_step_index', 'is_replied', 'last_sent_at')
    list_filter = ('status', 'campaign', 'is_replied', 'is_opened')
    search_fields = ('email', 'name')
    ordering = ('-last_sent_at',)

@admin.register(CampaignStep)
class CampaignStepAdmin(admin.ModelAdmin):
    list_display = ('campaign', 'step_number', 'wait_days', 'subject')
    list_filter = ('campaign',)

@admin.register(SentEmailLog)
class SentEmailLogAdmin(admin.ModelAdmin):
    list_display = ('recipient', 'step', 'smtp_used', 'sent_at')
    list_filter = ('sent_at', 'smtp_used')
