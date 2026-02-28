"""
DRF Serializers for the core scraper app.
Covers both Website-scraping and LinkedIn-scraping jobs.
"""
from rest_framework import serializers
from .models import (
    ScrapeJob, ScrapedWebsite,
    LinkedInScrapeJob, ScrapedLinkedInProfile,
    LinkedInAccount,
)


# ━━━━━━━━━━━━━━  Website Scraping  ━━━━━━━━━━━━━━━━━━━━

class ScrapedWebsiteSerializer(serializers.ModelSerializer):
    class Meta:
        model  = ScrapedWebsite
        fields = [
            'id', 'website_url',
            'email', 'phone', 'address',
            'facebook', 'twitter', 'instagram', 'linkedin',
            'pages_scraped', 'scraped_at',
        ]


class ScrapeJobSerializer(serializers.ModelSerializer):
    result           = ScrapedWebsiteSerializer(read_only=True)
    duration_seconds = serializers.FloatField(read_only=True)

    class Meta:
        model  = ScrapeJob
        fields = [
            'id', 'url', 'scrape_contact', 'max_contact_pages',
            'status', 'error_message',
            'created_at', 'started_at', 'completed_at', 'duration_seconds',
            'result',
        ]
        read_only_fields = [
            'status', 'error_message',
            'created_at', 'started_at', 'completed_at',
        ]


class ScrapeJobCreateSerializer(serializers.ModelSerializer):
    """POST /api/jobs/ — create a website scrape job."""

    class Meta:
        model  = ScrapeJob
        fields = ['url', 'scrape_contact', 'max_contact_pages']

    def validate_url(self, value):
        from .scraper.validators import is_valid_url
        if not is_valid_url(value):
            raise serializers.ValidationError("Enter a valid URL starting with http:// or https://")
        return value


# ━━━━━━━━━━━━━━  LinkedIn Scraping  ━━━━━━━━━━━━━━━━━━━

class ScrapedLinkedInProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model  = ScrapedLinkedInProfile
        fields = [
            'id', 'profile_url', 'name', 'headline', 'location',
            'about', 'company_size', 'company_type', 'industry', 'founded',
            'website',
            'website_email', 'website_phone', 'website_address',
            'website_facebook', 'website_twitter', 'website_instagram', 'website_linkedin',
            'scraped_at',
        ]


class LinkedInScrapeJobSerializer(serializers.ModelSerializer):
    profiles         = ScrapedLinkedInProfileSerializer(many=True, read_only=True)
    duration_seconds = serializers.FloatField(read_only=True)
    profiles_count   = serializers.SerializerMethodField()

    class Meta:
        model  = LinkedInScrapeJob
        fields = [
            'id', 'niche', 'max_profiles', 'scrape_websites', 'headless',
            'status', 'error_message', 'progress',
            'created_at', 'started_at', 'completed_at', 'duration_seconds',
            'profiles_count', 'profiles',
        ]
        read_only_fields = [
            'status', 'error_message', 'progress',
            'created_at', 'started_at', 'completed_at',
        ]

    def get_profiles_count(self, obj):
        return obj.profiles.count()


class LinkedInAccountSerializer(serializers.ModelSerializer):
    class Meta:
        model = LinkedInAccount
        fields = ['id', 'email', 'password', 'name', 'is_active', 'created_at', 'updated_at']
        read_only_fields = ['created_at', 'updated_at']
        extra_kwargs = {
            'password': {'write_only': True}
        }

class LinkedInScrapeJobCreateSerializer(serializers.ModelSerializer):
    """POST /api/linkedin/jobs/ — create a LinkedIn scrape job."""

    class Meta:
        model  = LinkedInScrapeJob
        fields = [
            'niche', 'max_profiles', 'scrape_websites', 'headless',
            'account', 'linkedin_email', 'linkedin_password',
        ]


class LinkedInScrapeJobListSerializer(serializers.ModelSerializer):
    """Lighter serializer for listing jobs (no full profiles embedded)."""
    duration_seconds = serializers.FloatField(read_only=True)
    profiles_count   = serializers.SerializerMethodField()

    class Meta:
        model  = LinkedInScrapeJob
        fields = [
            'id', 'niche', 'max_profiles', 'scrape_websites', 'headless',
            'status', 'error_message', 'progress',
            'created_at', 'started_at', 'completed_at', 'duration_seconds',
            'profiles_count',
        ]

    def get_profiles_count(self, obj):
        return obj.profiles.count()
