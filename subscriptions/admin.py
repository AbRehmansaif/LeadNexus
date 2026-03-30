from django.contrib import admin
from .models import SubscriptionPlan

@admin.register(SubscriptionPlan)
class SubscriptionPlanAdmin(admin.ModelAdmin):
    list_display = ('name', 'order', 'monthly_price', 'yearly_price', 'job_limit', 'outreach_limit', 'is_featured')
    list_editable = ('order', 'monthly_price', 'is_featured')
    fieldsets = (
        ('Name & Order', {
            'fields': ('name', 'badge', 'short_description', 'btn_text', 'btn_url_name', 'order', 'is_featured')
        }),
        ('Pricing', {
            'fields': (('monthly_price', 'is_custom_pricing'), 'yearly_price')
        }),
        ('Quotas', {
            'fields': ('job_limit', 'linkedin_limit', 'outreach_limit', 'smtp_limit')
        }),
        ('Features & Flags', {
            'fields': ('has_multi_thread', 'has_csv_export', 'has_priority_execution', 'has_dedicated_ip', 'support_level', 'features')
        })
    )
