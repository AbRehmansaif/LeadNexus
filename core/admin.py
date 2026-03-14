"""
Admin configuration for the core app.
Registers both Website and LinkedIn scraping models.
"""
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User
from .models import (
    ScrapeJob, ScrapedWebsite, LinkedInScrapeJob, 
    ScrapedLinkedInProfile, UserProfile, GlobalSettings
)

# ── System Settings ────────────────────────────────────

@admin.register(GlobalSettings)
class GlobalSettingsAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'registrations_enabled', 'maintenance_mode', 'contact_email')
    fieldsets = (
        ('System Config', {
            'fields': ('registrations_enabled', 'maintenance_mode')
        }),
        ('Landing Page Contact', {
            'fields': ('contact_email', 'whatsapp_number'),
            'description': 'Contact info displayed publicly to visitors.'
        }),
        ('Dashboard Monthly Targets', {
            'fields': ('mrr_target', 'registrations_target'),
            'description': 'Target goals for the Admin Dashboard metrics.'
        }),
    )
    
    def has_add_permission(self, request):
        # Only allow one instance
        return not GlobalSettings.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False

# ── User Management ────────────────────────────────────

class UserProfileInline(admin.StackedInline):
    model = UserProfile
    can_delete = False
    verbose_name_plural = 'Membership & Quotas'
    fieldsets = (
        ('Status', {
            'fields': ('membership_status', 'is_verified', 'admin_notes')
        }),
        ('Quotas', {
            'fields': (('job_limit_monthly', 'linkedin_limit_monthly', 'smtp_limit', 'email_outreach_limit_monthly'), ('jobs_this_month_count', 'linkedin_this_month_count', 'emails_this_month_count')),
            'description': 'Manage monthly resource allocations.'
        }),
        ('Lifetime Intelligence', {
            'fields': (('total_websites_scraped', 'total_linkedin_scraped'), 'total_emails_sent', 'total_records_scraped'),
            'description': 'Historical performance and data acquisition metrics.'
        }),
        ('Billing & Payments', {
            'fields': ('is_paid', 'last_payment_date', 'subscription_end_date'),
            'description': 'Tracking user payment history and active subscription periods.'
        }),
        ('Profile', {
            'fields': ('avatar', 'bio'),
            'classes': ('collapse',),
        }),
    )

class UserAdmin(BaseUserAdmin):
    inlines = (UserProfileInline,)
    list_display = ('username', 'email', 'first_name', 'last_name', 'is_active', 'is_staff', 'get_membership')
    list_filter = ('is_active', 'is_staff', 'profile__membership_status')
    actions = ['activate_users', 'deactivate_users']

    def get_membership(self, obj):
        return obj.profile.membership_status
    get_membership.short_description = 'Plan'

    def activate_users(self, request, queryset):
        queryset.update(is_active=True)
    activate_users.short_description = "Activate selected identities"

    def deactivate_users(self, request, queryset):
        queryset.update(is_active=False)
    deactivate_users.short_description = "Lock selected identities (Ban)"

    def changelist_view(self, request, extra_context=None):
        from core.models import UserProfile
        
        total_users = User.objects.count()
        free_users = UserProfile.objects.filter(membership_status='free').count()
        pro_users = UserProfile.objects.filter(membership_status='pro').count()
        enterprise_users = UserProfile.objects.filter(membership_status='enterprise').count()
        
        extra_context = extra_context or {}
        extra_context.update({
            'total_users': total_users,
            'free_users': free_users,
            'pro_users': pro_users,
            'enterprise_users': enterprise_users,
        })
        return super().changelist_view(request, extra_context=extra_context)

# Re-register UserAdmin
admin.site.unregister(User)
admin.site.register(User, UserAdmin)


# ── Website Scraping ───────────────────────────────────

@admin.register(ScrapeJob)
class ScrapeJobAdmin(admin.ModelAdmin):
    list_display  = ('id', 'url', 'status', 'scrape_contact', 'created_at', 'get_duration')
    list_filter   = ('status', 'scrape_contact')
    search_fields = ('url',)
    readonly_fields = ('status', 'error_message', 'created_at', 'started_at', 'completed_at')
    ordering = ('-created_at',)

    def get_duration(self, obj):
        d = obj.duration_seconds
        return f"{d:.1f}s" if d is not None else "—"
    get_duration.short_description = "Duration"


@admin.register(ScrapedWebsite)
class ScrapedWebsiteAdmin(admin.ModelAdmin):
    list_display  = ('id', 'job', 'website_url', 'email', 'phone', 'scraped_at')
    search_fields = ('website_url', 'email', 'phone')
    readonly_fields = ('scraped_at',)
    ordering = ('-scraped_at',)


# ── LinkedIn Scraping ──────────────────────────────────

class ProfileInline(admin.TabularInline):
    model = ScrapedLinkedInProfile
    extra = 0
    readonly_fields = (
        'profile_url', 'name', 'headline', 'location', 'company_size',
        'company_type', 'industry', 'founded', 'website',
        'website_email', 'website_phone', 'website_address',
        'website_facebook', 'website_twitter', 'website_instagram', 'website_linkedin',
        'scraped_at',
    )
    fields = readonly_fields
    can_delete = False
    show_change_link = True


@admin.register(LinkedInScrapeJob)
class LinkedInScrapeJobAdmin(admin.ModelAdmin):
    list_display  = ('id', 'niche', 'max_profiles', 'progress', 'status', 'scrape_websites', 'created_at', 'get_duration')
    list_filter   = ('status', 'scrape_websites', 'headless')
    search_fields = ('niche',)
    readonly_fields = ('status', 'error_message', 'progress', 'created_at', 'started_at', 'completed_at')
    ordering = ('-created_at',)
    inlines = [ProfileInline]

    def get_duration(self, obj):
        d = obj.duration_seconds
        return f"{d:.1f}s" if d is not None else "—"
    get_duration.short_description = "Duration"


@admin.register(ScrapedLinkedInProfile)
class ScrapedLinkedInProfileAdmin(admin.ModelAdmin):
    list_display  = ('id', 'name', 'location', 'company_size', 'industry', 'website', 'website_email', 'scraped_at')
    list_filter   = ('company_type', 'industry')
    search_fields = ('name', 'location', 'website', 'website_email')
    readonly_fields = ('scraped_at',)
    ordering = ('-scraped_at',)
