"""
Background scraping tasks.
Supports two job types:
1. Website scrape (ScrapeJob)     — give a URL, extract contact data
2. LinkedIn scrape (LinkedInScrapeJob) — niche search → profiles → websites
"""
import os
import json
import csv
import logging
import threading
from datetime import datetime

from django.conf import settings
from django.utils import timezone

from .models import (
    ScrapeJob, ScrapedWebsite,
    LinkedInScrapeJob, ScrapedLinkedInProfile,
)
from .scraper.website_scraper import WebsiteScraper

logger = logging.getLogger(__name__)

# Data output directory (shared with the standalone scraper)
DATA_DIR = os.path.join(settings.BASE_DIR.parent, 'data')
os.makedirs(DATA_DIR, exist_ok=True)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  1.  Website Scrape Job  (existing — give a URL)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def run_scrape_job(job_id: int):
    """Execute a ScrapeJob (website-only scrape)."""
    try:
        job = ScrapeJob.objects.get(pk=job_id)
    except ScrapeJob.DoesNotExist:
        logger.error(f"ScrapeJob #{job_id} not found")
        return

    job.status = 'running'
    job.started_at = timezone.now()
    job.save(update_fields=['status', 'started_at'])

    try:
        scraper = WebsiteScraper(timeout=15)
        data = scraper.scrape(
            url=job.url,
            scrape_contact=job.scrape_contact,
            max_contact_pages=job.max_contact_pages,
        )

        ScrapedWebsite.objects.update_or_create(
            job=job,
            defaults={
                'website_url':   data.get('website_url', job.url),
                'email':         data.get('email'),
                'phone':         data.get('phone'),
                'address':       data.get('address'),
                'facebook':      data.get('facebook'),
                'twitter':       data.get('twitter'),
                'instagram':     data.get('instagram'),
                'linkedin':      data.get('linkedin'),
                'pages_scraped': data.get('pages_scraped', []),
                'scraped_at':    timezone.now(),
            }
        )

        # Also save to data/ folder
        _save_website_to_file(job, data)

        job.status = 'completed'
        job.error_message = ''

    except Exception as e:
        logger.exception(f"ScrapeJob #{job_id} failed: {e}")
        job.status = 'failed'
        job.error_message = str(e)

    finally:
        job.completed_at = timezone.now()
        job.save(update_fields=['status', 'error_message', 'completed_at'])


def run_scrape_job_async(job_id: int):
    """Fire-and-forget website scrape in a background thread."""
    t = threading.Thread(target=run_scrape_job, args=(job_id,), daemon=True)
    t.start()


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  2.  LinkedIn Scrape Job  (niche → Chrome → profiles → websites)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def run_linkedin_job(job_id: int):
    """
    Full LinkedIn pipeline:
    1. Open Chrome → navigate to LinkedIn
    2. Login (if credentials provided)
    3. Search companies by niche
    4. Scrape profiles one-by-one (with delays)
    5. Optionally visit associated websites and scrape contact data
    6. Save results to DB + data/ folder
    """
    from .scraper.linkedin_scraper import LinkedInScraper

    try:
        job = LinkedInScrapeJob.objects.get(pk=job_id)
    except LinkedInScrapeJob.DoesNotExist:
        logger.error(f"LinkedInScrapeJob #{job_id} not found")
        return

    job.status = 'running'
    job.started_at = timezone.now()
    job.progress = 0
    job.save(update_fields=['status', 'started_at', 'progress'])

    scraper = None

    try:
        # ─── Step 1: Initialize Chrome ─────────────────────────────
        logger.info(f"[LinkedInJob #{job_id}] Initializing Chrome ...")
        # Config matches the original scrapers/linkedin_scraper.py format
        config = {
            'scraping': {
                'headless': job.headless,
                'delay_min': 3,
                'delay_max': 6,
                'timeout': 30,
            },
            'website_scraping': {
                'enabled': job.scrape_websites,
                'timeout': 15,
            },
        }
        scraper = LinkedInScraper(config)
        scraper.setup_driver()

        # ─── Step 2: Login ─────────────────────────────────────────
        email = job.linkedin_email
        password = job.linkedin_password
        if email and password:
            logger.info(f"[LinkedInJob #{job_id}] Logging in ...")
            if not scraper.login(email, password):
                raise Exception("LinkedIn login failed — check credentials or solve security challenge")
        else:
            logger.info(f"[LinkedInJob #{job_id}] No credentials — proceeding without login (limited data)")

        # ─── Step 3, 4 & 5: Search and scrape profiles ────────────────
        logger.info(f"[LinkedInJob #{job_id}] Searching for: {job.niche}")

        website_scraper = WebsiteScraper(timeout=15) if job.scrape_websites else None
        saved_profiles = []

        def on_profile_found(profile_data):
            """Callback for each profile found during search_and_scrape."""
            website_data = {}
            website_url = profile_data.get('website')

            if website_scraper and website_url:
                try:
                    logger.info(f"[LinkedInJob #{job_id}] Scraping website: {website_url}")
                    wd = website_scraper.scrape(url=website_url, scrape_contact=True, max_contact_pages=3)
                    website_data = wd or {}
                except Exception as we:
                    logger.warning(f"Website scrape failed for {website_url}: {we}")

            # Save to DB immediately
            sp = ScrapedLinkedInProfile.objects.create(
                job=job,
                profile_url=profile_data.get('profile_url', ''),
                name=profile_data.get('name', 'N/A'),
                headline=profile_data.get('headline', 'N/A'),
                location=profile_data.get('location', 'N/A'),
                about=profile_data.get('about', 'N/A'),
                company_size=profile_data.get('company_size', 'N/A'),
                company_type=profile_data.get('company_type', 'N/A'),
                industry=profile_data.get('industry', 'N/A'),
                founded=profile_data.get('founded', 'N/A'),
                website=website_url,
                website_email=website_data.get('email'),
                website_phone=website_data.get('phone'),
                website_address=website_data.get('address'),
                website_facebook=website_data.get('facebook'),
                website_twitter=website_data.get('twitter'),
                website_instagram=website_data.get('instagram'),
                website_linkedin=website_data.get('linkedin'),
            )
            saved_profiles.append(sp)
            
            # Update progress
            LinkedInScrapeJob.objects.filter(pk=job_id).update(progress=len(saved_profiles))

        # Start search and scrape loop
        scraper.search_and_scrape(
            niche=job.niche,
            max_results=job.max_profiles,
            processor_callback=on_profile_found,
        )

        # ─── Step 6: Save to data/ folder ──────────────────────────
        _save_linkedin_to_files(job, saved_profiles)

        job.status = 'completed'
        job.error_message = ''
        job.progress = len(saved_profiles)

    except Exception as e:
        logger.exception(f"LinkedInScrapeJob #{job_id} failed: {e}")
        job.status = 'failed'
        job.error_message = str(e)

    finally:
        if scraper:
            scraper.close()
        job.completed_at = timezone.now()
        job.save(update_fields=['status', 'error_message', 'completed_at', 'progress'])


def run_linkedin_job_async(job_id: int):
    """Fire-and-forget LinkedIn scrape in a background thread."""
    t = threading.Thread(target=run_linkedin_job, args=(job_id,), daemon=True)
    t.start()


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  File saving helpers  (save to data/ folder)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def _save_website_to_file(job: ScrapeJob, data: dict):
    """Save a website scrape result to a JSON file in data/."""
    try:
        ts = datetime.now().strftime('%Y%m%d_%H%M%S')
        domain = data.get('website_url', 'unknown').replace('https://', '').replace('http://', '').split('/')[0]
        safe_domain = domain.replace('.', '_').replace(':', '_')

        filepath = os.path.join(DATA_DIR, f'website_{safe_domain}_{ts}.json')
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False, default=str)
        logger.info(f"Saved website data to {filepath}")
    except Exception as e:
        logger.warning(f"Failed to save file: {e}")


def _save_linkedin_to_files(job: LinkedInScrapeJob, profiles):
    """Save LinkedIn scrape results to CSV + JSON in data/."""
    if not profiles:
        return

    try:
        ts = datetime.now().strftime('%Y%m%d_%H%M%S')
        niche_slug = job.niche.replace(' ', '_').lower()[:40]

        # ── JSON ──
        json_data = {
            'metadata': {
                'niche': job.niche,
                'max_profiles': job.max_profiles,
                'scraped_at': ts,
                'total_profiles': len(profiles),
            },
            'profiles': [],
        }
        for p in profiles:
            json_data['profiles'].append({
                'profile_url': p.profile_url,
                'name': p.name,
                'headline': p.headline,
                'location': p.location,
                'about': p.about,
                'company_size': p.company_size,
                'company_type': p.company_type,
                'industry': p.industry,
                'founded': p.founded,
                'website': p.website or '',
                'website_email': p.website_email or '',
                'website_phone': p.website_phone or '',
                'website_address': p.website_address or '',
                'website_facebook': p.website_facebook or '',
                'website_twitter': p.website_twitter or '',
                'website_instagram': p.website_instagram or '',
                'website_linkedin': p.website_linkedin or '',
            })

        json_path = os.path.join(DATA_DIR, f'{niche_slug}_{ts}.json')
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(json_data, f, indent=2, ensure_ascii=False)
        logger.info(f"Saved LinkedIn JSON → {json_path}")

        # ── CSV (combined) ──
        csv_path = os.path.join(DATA_DIR, f'{niche_slug}_combined_{ts}.csv')
        fieldnames = [
            'name', 'headline', 'location', 'company_size', 'company_type',
            'industry', 'founded', 'website', 'profile_url',
            'website_email', 'website_phone', 'website_address',
            'website_facebook', 'website_twitter', 'website_instagram', 'website_linkedin',
        ]
        with open(csv_path, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for entry in json_data['profiles']:
                row = {k: entry.get(k, '') for k in fieldnames}
                writer.writerow(row)
        logger.info(f"Saved LinkedIn CSV → {csv_path}")

        # ── LinkedIn-only CSV ──
        li_csv_path = os.path.join(DATA_DIR, f'{niche_slug}_linkedin_{ts}.csv')
        li_fields = ['name', 'headline', 'location', 'company_size', 'company_type',
                      'industry', 'founded', 'website', 'profile_url']
        with open(li_csv_path, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.DictWriter(f, fieldnames=li_fields)
            writer.writeheader()
            for entry in json_data['profiles']:
                row = {k: entry.get(k, '') for k in li_fields}
                writer.writerow(row)
        logger.info(f"Saved LinkedIn-only CSV → {li_csv_path}")

        # ── Website-only CSV ──
        web_csv_path = os.path.join(DATA_DIR, f'{niche_slug}_website_{ts}.csv')
        web_fields = ['name', 'website', 'website_email', 'website_phone',
                       'website_address', 'website_facebook', 'website_twitter',
                       'website_instagram', 'website_linkedin']
        with open(web_csv_path, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.DictWriter(f, fieldnames=web_fields)
            writer.writeheader()
            for entry in json_data['profiles']:
                if entry.get('website'):
                    row = {k: entry.get(k, '') for k in web_fields}
                    writer.writerow(row)
        logger.info(f"Saved website-only CSV → {web_csv_path}")

    except Exception as e:
        logger.warning(f"Failed to save LinkedIn data files: {e}")
