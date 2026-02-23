"""
Website scraper — Django-integrated version.
Ported from scrapers/website_scraper.py into the core Django app.
"""
import re
import time
import random
import logging
import requests

from bs4 import BeautifulSoup
from typing import Dict, Optional, List
from urllib.parse import urljoin, urlparse

from .validators import (
    is_valid_url,
    is_valid_email,
    extract_email_from_text,
    extract_phone_from_text,
    clean_text,
)

logger = logging.getLogger(__name__)

# Default scraper config (can be overridden via ScrapeJob settings)
DEFAULT_CONFIG = {
    'website_scraping': {
        'enabled': True,
        'timeout': 15,
    }
}


class WebsiteScraper:
    """
    Scraper for extracting contact data from websites.
    Scrapes the homepage + up to `max_contact_pages` contact/about pages.
    """

    CONTACT_KEYWORDS = ['contact', 'about', 'team', 'connect', 'reach', 'get-in-touch']

    SOCIAL_DOMAINS = {
        'facebook':  ['facebook.com', 'fb.com'],
        'twitter':   ['twitter.com', 'x.com'],
        'instagram': ['instagram.com'],
        'linkedin':  ['linkedin.com'],
    }

    def __init__(self, timeout: int = 15):
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': (
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                'AppleWebKit/537.36 (KHTML, like Gecko) '
                'Chrome/122.0.0.0 Safari/537.36'
            ),
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
        })

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def scrape(self, url: str, scrape_contact: bool = True, max_contact_pages: int = 3) -> Dict:
        """
        Scrape a website and return extracted data.

        Args:
            url:                 Target website URL
            scrape_contact:      Whether to also scrape contact/about pages
            max_contact_pages:   Maximum number of contact pages to follow

        Returns:
            dict with keys: website_url, email, phone, address,
                            facebook, twitter, instagram, linkedin,
                            pages_scraped
        """
        if not is_valid_url(url):
            raise ValueError(f"Invalid URL: {url}")

        data = {
            'website_url': url,
            'email':      None,
            'phone':      None,
            'facebook':   None,
            'twitter':    None,
            'instagram':  None,
            'linkedin':   None,
            'address':    None,
            'pages_scraped': [],
        }

        # 1. Scrape the homepage
        logger.info(f"Scraping homepage: {url}")
        page_data = self._scrape_page(url)
        if page_data:
            data['pages_scraped'].append(url)
            self._merge(data, page_data)

        # 2. Optionally scrape contact pages
        if scrape_contact:
            contact_urls = self._find_contact_pages(url)
            logger.info(f"Found {len(contact_urls)} potential contact pages")

            for contact_url in contact_urls[:max_contact_pages]:
                logger.info(f"Scraping contact page: {contact_url}")
                contact_data = self._scrape_page(contact_url)
                if contact_data:
                    data['pages_scraped'].append(contact_url)
                    self._merge(data, contact_data)
                time.sleep(random.uniform(1, 2))

        return data

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _merge(self, base: Dict, new: Dict):
        """Update base dict with non-None values from new, without overwriting existing."""
        for key, value in new.items():
            if value and not base.get(key):
                base[key] = value

    def _scrape_page(self, url: str) -> Optional[Dict]:
        try:
            response = self.session.get(url, timeout=self.timeout)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, 'html.parser')

            return {
                'email':     self._extract_email(soup),
                'phone':     self._extract_phone(soup),
                'facebook':  self._extract_social(soup, 'facebook'),
                'twitter':   self._extract_social(soup, 'twitter'),
                'instagram': self._extract_social(soup, 'instagram'),
                'linkedin':  self._extract_social(soup, 'linkedin'),
                'address':   self._extract_address(soup),
            }
        except requests.RequestException as e:
            logger.warning(f"Request failed for {url}: {e}")
            return None
        except Exception as e:
            logger.error(f"Error parsing page {url}: {e}")
            return None

    def _find_contact_pages(self, base_url: str) -> List[str]:
        contact_urls = []
        try:
            response = self.session.get(base_url, timeout=self.timeout)
            soup = BeautifulSoup(response.content, 'html.parser')

            for link in soup.find_all('a', href=True):
                href = link.get('href', '').lower()
                text = link.get_text().lower()

                if any(kw in href or kw in text for kw in self.CONTACT_KEYWORDS):
                    full_url = urljoin(base_url, link['href'])
                    if (
                        urlparse(full_url).netloc == urlparse(base_url).netloc
                        and full_url not in contact_urls
                    ):
                        contact_urls.append(full_url)
        except Exception as e:
            logger.warning(f"Error finding contact pages on {base_url}: {e}")
        return contact_urls

    def _extract_email(self, soup: BeautifulSoup) -> Optional[str]:
        email = extract_email_from_text(soup.get_text())
        if email:
            return email
        for link in soup.find_all('a', href=lambda x: x and 'mailto:' in x):
            candidate = link['href'].replace('mailto:', '').split('?')[0]
            if is_valid_email(candidate):
                return candidate
        return None

    def _extract_phone(self, soup: BeautifulSoup) -> Optional[str]:
        phone = extract_phone_from_text(soup.get_text())
        if phone:
            return phone
        for link in soup.find_all('a', href=lambda x: x and 'tel:' in x):
            return link['href'].replace('tel:', '').strip()
        return None

    def _extract_social(self, soup: BeautifulSoup, platform: str) -> Optional[str]:
        domains = self.SOCIAL_DOMAINS.get(platform.lower(), [])
        for link in soup.find_all('a', href=True):
            href = link.get('href', '').lower()
            if any(d in href for d in domains):
                full_url = link['href']
                if is_valid_url(full_url):
                    return full_url
        return None

    def _extract_address(self, soup: BeautifulSoup) -> Optional[str]:
        # Schema.org markup
        elem = soup.find('span', {'itemprop': 'address'})
        if elem:
            return clean_text(elem.get_text())

        # CSS class with "address"
        elem = soup.find(
            ['div', 'p', 'span'],
            {'class': lambda x: x and 'address' in str(x).lower()}
        )
        if elem:
            return clean_text(elem.get_text())

        # US address regex fallback
        pattern = (
            r'\d+\s+[\w\s]+(?:Street|St|Avenue|Ave|Road|Rd|Boulevard|Blvd|Lane|Ln|Drive|Dr)'
            r'[,\s]+[\w\s]+[,\s]+[A-Z]{2}\s+\d{5}'
        )
        match = re.search(pattern, soup.get_text())
        if match:
            return clean_text(match.group(0))

        return None
