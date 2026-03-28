from django.contrib import admin
from .models import SubscriptionPlan

@admin.register(SubscriptionPlan)
class SubscriptionPlanAdmin(admin.ModelAdmin):
    list_display = ('name', 'monthly_price', 'yearly_price', 'short_description', 'is_custom_pricing', 'is_featured', 'order')
    list_editable = ('monthly_price', 'yearly_price', 'short_description', 'is_custom_pricing', 'is_featured', 'order')
