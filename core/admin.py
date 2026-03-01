"""
Admin configuration for the core app.
Registers both Website and LinkedIn scraping models.
"""
from django.contrib import admin
from .models import ScrapeJob, ScrapedWebsite, LinkedInScrapeJob, ScrapedLinkedInProfile


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
