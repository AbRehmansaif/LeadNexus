from django.contrib.sitemaps import Sitemap
from django.urls import reverse
from datetime import date


class StaticViewSitemap(Sitemap):
    priority = 1.0
    changefreq = 'daily'
    protocol = 'https'

    def items(self):
        return [
            'landing',
            'login',
            'register',
        ]

    def location(self, item):
        return reverse(item)

    def lastmod(self, item):
        return date.today()


class AffiliateViewSitemap(Sitemap):
    priority = 0.9
    changefreq = 'weekly'
    protocol = 'https'

    def items(self):
        return [
            'affiliatemarketing:affiliate',
        ]

    def location(self, item):
        return reverse(item)

    def lastmod(self, item):
        return date.today()


class SeoViewSitemap(Sitemap):
    priority = 0.9
    changefreq = 'weekly'
    protocol = 'https'

    def items(self):
        return [
            'seo:seo-email-automation-tool',
            'seo:seo-cold-email-automation',
            'seo:seo-email-automation-for-sales',
            'seo:seo-email-automation-for-marketing',
            'seo:seo-email-automation-for-seo',
            'seo:seo-email-automation-for-agencies',
            'seo:seo-email-automation-for-recruiters',
            'seo:seo-email-automation-for-saas',
            'seo:seo-email-automation-for-startups',
            'seo:seo-lead-generation-email-tool',
            'seo:seo-outreach-automation',
        ]

    def location(self, item):
        return reverse(item)

    def lastmod(self, item):
        return date.today()


class ToolsViewSitemap(Sitemap):
    priority = 0.85
    changefreq = 'monthly'
    protocol = 'https'

    def items(self):
        return [
            'seo:seo-tool-markdown-to-html',
            'seo:seo-tool-excel-to-csv',
            'seo:seo-tool-utm-link-builder',
            'seo:seo-tool-dns-config-generator',
            'seo:seo-tool-cold-email-roi-calculator',
            'seo:seo-tool-email-spam-word-checker',
            'seo:seo-tool-email-warmup-calculator',
        ]

    def location(self, item):
        return reverse(item)

    def lastmod(self, item):
        return date(2025, 1, 1)