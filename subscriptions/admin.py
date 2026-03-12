from django.contrib import admin
from .models import PlanFeature, SubscriptionPlan

@admin.register(SubscriptionPlan)
class SubscriptionPlanAdmin(admin.ModelAdmin):
    list_display = ('name', 'monthly_price', 'yearly_price', 'is_custom_pricing', 'is_featured', 'order')
    list_editable = ('monthly_price', 'yearly_price', 'is_custom_pricing', 'is_featured', 'order')

@admin.register(PlanFeature)
class PlanFeatureAdmin(admin.ModelAdmin):
    list_display = ('name', 'free_value', 'pro_value', 'enterprise_value', 'order')
    list_editable = ('free_value', 'pro_value', 'enterprise_value', 'order')
    search_fields = ('name',)
