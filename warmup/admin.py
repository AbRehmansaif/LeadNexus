from django.contrib import admin
from .models import WarmupAccount, WarmupPool, WarmupEmail, WarmupDailyScore


@admin.register(WarmupAccount)
class WarmupAccountAdmin(admin.ModelAdmin):
    list_display = ['smtp_credential', 'user', 'status', 'day_number', 'warmup_score',
                    'inbox_rate', 'spam_rate', 'total_sent', 'last_run_at']
    list_filter = ['status']
    search_fields = ['smtp_credential__from_email', 'user__username']
    readonly_fields = ['warmup_score', 'total_sent', 'inbox_count', 'spam_count',
                       'reply_count', 'started_at', 'last_run_at', 'created_at']


@admin.register(WarmupPool)
class WarmupPoolAdmin(admin.ModelAdmin):
    list_display = ['email', 'user', 'smtp_host', 'is_active', 'created_at']
    list_filter = ['is_active']
    search_fields = ['email', 'user__username']


@admin.register(WarmupEmail)
class WarmupEmailAdmin(admin.ModelAdmin):
    list_display = ['account', 'to_email', 'subject', 'placement', 'is_replied', 'sent_at']
    list_filter = ['placement', 'is_replied']
    search_fields = ['to_email', 'account__smtp_credential__from_email']
    readonly_fields = ['sent_at', 'checked_at', 'replied_at', 'message_id']


@admin.register(WarmupDailyScore)
class WarmupDailyScoreAdmin(admin.ModelAdmin):
    list_display = ['account', 'date', 'day_number', 'score', 'inbox_rate', 'spam_rate', 'emails_sent']
    list_filter = ['date']
    ordering = ['-date']
