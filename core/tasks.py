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

    # Job starts, we will increment usage PER DOMAIN inside the loop below
    pass

    try:
        scraper = WebsiteScraper(timeout=15)
        
        urls_to_process = job.urls_to_scrape if job.urls_to_scrape else []
        if job.url and job.url not in urls_to_process:
            urls_to_process.append(job.url)
            
        for current_url in urls_to_process:
            # --- Check for Pause/Cancel ---
            job.refresh_from_db()
            while job.status == 'paused':
                import time
                time.sleep(5)
                job.refresh_from_db()

            if job.status == 'cancelled':
                break

            # --- SaaS Quota Check (Per Domain) ---
            if job.user and hasattr(job.user, 'profile'):
                if not job.user.profile.can_scrape_website():
                    job.status = 'failed'
                    job.error_message = "Monthly website scanning quota reached. Please upgrade your plan for more credits."
                    job.save(update_fields=['status', 'error_message'])
                    logger.error(f"User {job.user.username} reached monthly website quota mid-job #{job_id}")
                    return

                # Increment Usage BEFORE scrape to prevent 'free' overlaps
                job.user.profile.increment_web_usage()
                
            try:
                data = scraper.scrape(
                    url=current_url,
                    scrape_contact=job.scrape_contact,
                    max_contact_pages=job.max_contact_pages,
                )
                
                # Add delay between domains but AFTER check
                import time, random
                time.sleep(random.uniform(2, 4))

                ScrapedWebsite.objects.update_or_create(
                    job=job,
                    website_url=data.get('website_url', current_url),
                    defaults={
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

                # Update Lifetime Stats
                if job.user and hasattr(job.user, 'profile'):
                    job.user.profile.increment_records_found()
            except Exception as e:
                logger.error(f"Failed to scrape {current_url} in job #{job_id}: {e}")

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

    # Job starts, we will increment usage PER PROFILE inside the callback below
    pass

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
        # Use stored account credentials if selected, otherwise fallback to manual entry
        if job.account:
            email = job.account.email
            password = job.account.password
            logger.info(f"[LinkedInJob #{job_id}] Using stored account: {email}")
        else:
            email = job.linkedin_email
            password = job.linkedin_password
            logger.info(f"[LinkedInJob #{job_id}] Using manual credentials")

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

            # --- SaaS Quota Check (Per Profile) ---
            if job.user and hasattr(job.user, 'profile'):
                if not job.user.profile.can_scrape_linkedin():
                    logger.warning(f"User {job.user.username} reached monthly LinkedIn quota mid-job #{job_id}")
                    # We return early to skip this profile. The main loop in search_and_scrape 
                    # should ideally also stop, but since it's inside the scraper class,
                    # simply skipping saves credits.
                    return

                # Increment Usage
                job.user.profile.increment_linkedin_usage()

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

            # Update Lifetime Stats
            if job.user and hasattr(job.user, 'profile'):
                job.user.profile.increment_records_found()

        # Start search and scrape loop
        scraper.search_and_scrape(
            niche=job.niche,
            max_results=job.max_profiles,
            location=job.location,
            company_size=job.company_size,
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

        # ── JSON preparation ──
        profile_data_list = []
        for profile_obj in profiles:
            # profile_obj is an instance of ScrapedLinkedInProfile
            p_dict = {
                'profile_url': profile_obj.profile_url,
                'name': profile_obj.name,
                'headline': profile_obj.headline,
                'location': profile_obj.location,
                'about': profile_obj.about,
                'company_size': profile_obj.company_size,
                'company_type': profile_obj.company_type,
                'industry': profile_obj.industry,
                'founded': profile_obj.founded,
                'website': profile_obj.website or '',
                'website_email': profile_obj.website_email or '',
                'website_phone': profile_obj.website_phone or '',
                'website_address': profile_obj.website_address or '',
                'website_facebook': profile_obj.website_facebook or '',
                'website_twitter': profile_obj.website_twitter or '',
                'website_instagram': profile_obj.website_instagram or '',
                'website_linkedin': profile_obj.website_linkedin or '',
            }
            profile_data_list.append(p_dict)

        output_json = {
            'metadata': {
                'niche': job.niche,
                'max_profiles': job.max_profiles,
                'scraped_at': ts,
                'total_profiles': len(profiles),
            },
            'profiles': profile_data_list,
        }

        json_path = os.path.join(DATA_DIR, f'{niche_slug}_{ts}.json')
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(output_json, f, indent=2, ensure_ascii=False)
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
            for entry_dict in profile_data_list:
                # Use .get() on the dictionary
                row = {k: entry_dict.get(k, '') for k in fieldnames}
                writer.writerow(row)
        logger.info(f"Saved LinkedIn CSV → {csv_path}")

        # ── LinkedIn-only CSV ──
        li_csv_path = os.path.join(DATA_DIR, f'{niche_slug}_linkedin_{ts}.csv')
        li_fields = ['name', 'headline', 'location', 'company_size', 'company_type',
                      'industry', 'founded', 'website', 'profile_url']
        with open(li_csv_path, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.DictWriter(f, fieldnames=li_fields)
            writer.writeheader()
            for entry_dict in profile_data_list:
                row = {k: entry_dict.get(k, '') for k in li_fields}
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
            for entry_dict in profile_data_list:
                if entry_dict.get('website'):
                    row = {k: entry_dict.get(k, '') for k in web_fields}
                    writer.writerow(row)
        logger.info(f"Saved website-only CSV → {web_csv_path}")

    except Exception as e:
        logger.warning(f"Failed to save LinkedIn data files: {e}")
