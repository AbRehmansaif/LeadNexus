"""
LinkedIn scraper — Django-integrated version.
Ported from scrapers/linkedin_scraper.py into the core Django app.

Opens Chrome, logs into LinkedIn, searches for companies by niche,
scrapes profiles one by one, and extracts company data.
"""
import re
import time
import random
import logging
from typing import List, Dict, Optional, Callable

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    TimeoutException,
    NoSuchElementException,
    StaleElementReferenceException,
)
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.keys import Keys

from bs4 import BeautifulSoup

from .validators import is_valid_url, extract_email_from_text, clean_text

logger = logging.getLogger(__name__)


class LinkedInScraper:
    """
    Selenium-based LinkedIn company scraper.
    Designed to run in a background thread from a Django view / task.
    """

    DEFAULT_CONFIG = {
        'email': '',
        'password': '',
        'use_authentication': True,
        'headless': False,
        'delay_min': 3,
        'delay_max': 6,
        'timeout': 30,
        'user_agent': (
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
            'AppleWebKit/537.36 (KHTML, like Gecko) '
            'Chrome/122.0.0.0 Safari/537.36'
        ),
    }

    def __init__(self, config: Optional[Dict] = None):
        self.config = {**self.DEFAULT_CONFIG, **(config or {})}
        self.driver: Optional[webdriver.Chrome] = None
        self.wait: Optional[WebDriverWait] = None
        self.is_logged_in = False

    # ------------------------------------------------------------------
    # Driver setup
    # ------------------------------------------------------------------

    def setup_driver(self):
        """Set up Chrome WebDriver with anti-detection options."""
        logger.info("Setting up Chrome WebDriver ...")

        chrome_options = Options()

        if self.config.get('headless', False):
            chrome_options.add_argument('--headless=new')

        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--disable-blink-features=AutomationControlled')
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)
        chrome_options.add_argument(f"user-agent={self.config['user_agent']}")

        # Try webdriver-manager for auto driver download
        try:
            from webdriver_manager.chrome import ChromeDriverManager
            service = Service(ChromeDriverManager().install())
        except ImportError:
            service = Service()  # fallback: expects chromedriver on PATH

        self.driver = webdriver.Chrome(service=service, options=chrome_options)
        self.wait = WebDriverWait(self.driver, self.config.get('timeout', 30))

        logger.info("WebDriver ready")

    # ------------------------------------------------------------------
    # Login
    # ------------------------------------------------------------------

    def login(self, email: str, password: str) -> bool:
        """
        Log in to LinkedIn with the supplied credentials.
        Returns True on success, False otherwise.
        """
        try:
            logger.info("Logging in to LinkedIn ...")
            self.driver.get('https://www.linkedin.com/login')
            time.sleep(3)

            email_field = self.wait.until(
                EC.presence_of_element_located((By.ID, 'username'))
            )
            password_field = self.driver.find_element(By.ID, 'password')

            self._human_type(email_field, email)
            time.sleep(random.uniform(0.5, 1.5))

            self._human_type(password_field, password)
            time.sleep(random.uniform(0.5, 1.5))

            login_btn = self.driver.find_element(By.CSS_SELECTOR, 'button[type="submit"]')
            self._move_and_click(login_btn)

            time.sleep(5)

            current = self.driver.current_url
            if 'feed' in current or 'mynetwork' in current:
                self.is_logged_in = True
                logger.info("Login successful!")
                return True
            elif 'checkpoint' in current or 'challenge' in current:
                logger.warning("Security checkpoint detected — waiting for manual verification …")
                # In a server context we wait up to 120 s for the user to solve it
                for _ in range(24):
                    time.sleep(5)
                    if 'feed' in self.driver.current_url:
                        self.is_logged_in = True
                        logger.info("Login successful after manual verification!")
                        return True
                logger.warning("Login timed out waiting for checkpoint")
                return False
            else:
                logger.warning("Login may have failed — check credentials")
                return False

        except Exception as e:
            logger.error(f"Login failed: {e}")
            return False

    # ------------------------------------------------------------------
    # Search & scrape pipeline
    # ------------------------------------------------------------------

    def search_and_scrape(
        self,
        niche: str,
        max_results: int = 50,
        progress_callback: Optional[Callable] = None,
    ) -> List[Dict]:
        """
        Full pipeline: search LinkedIn for companies in `niche`,
        visit each company page, extract data.

        Args:
            niche:              Search keyword / niche
            max_results:        Max number of company profiles to scrape
            progress_callback:  Optional fn(scraped_count, total) for progress

        Returns:
            List of dicts with company data
        """
        results: List[Dict] = []
        processed_urls: set = set()

        try:
            search_url = (
                f"https://www.linkedin.com/search/results/companies/"
                f"?keywords={niche.replace(' ', '%20')}"
            )
            logger.info(f"Searching LinkedIn companies for: {niche}")
            self.driver.get(search_url)
            time.sleep(random.uniform(3, 5))

            page = 1
            while len(results) < max_results:
                logger.info(f"Scanning search results — page {page} …")
                self._scroll_page()

                soup = BeautifulSoup(self.driver.page_source, 'html.parser')
                page_urls = self._extract_company_urls(soup, processed_urls)
                logger.info(f"Found {len(page_urls)} new companies on page {page}")

                if not page_urls:
                    logger.warning("No new companies found on this page — stopping.")
                    break

                for url in page_urls:
                    if len(results) >= max_results:
                        break

                    logger.info(f"Scraping company {len(results)+1}/{max_results}: {url}")
                    profile_data = self.scrape_company(url)

                    if profile_data:
                        results.append(profile_data)

                    if progress_callback:
                        progress_callback(len(results), max_results)

                    self._random_delay()

                    # Navigate back to search results
                    if '/search/' not in self.driver.current_url:
                        self.driver.back()
                        time.sleep(random.uniform(2, 4))

                # Pagination
                if len(results) < max_results:
                    if not self._go_to_next_page(search_url, page):
                        break
                    page += 1

        except Exception as e:
            logger.error(f"Error during search_and_scrape: {e}", exc_info=True)

        logger.info(f"Scraping complete — {len(results)} companies scraped")
        return results

    # ------------------------------------------------------------------
    # Single company scrape
    # ------------------------------------------------------------------

    def scrape_company(self, profile_url: str) -> Optional[Dict]:
        """
        Navigate to a LinkedIn company page and extract data.
        """
        try:
            about_url = profile_url.rstrip('/') + '/about/'
            self.driver.get(about_url)
            time.sleep(random.uniform(2, 4))
            self._scroll_page()

            soup = BeautifulSoup(self.driver.page_source, 'html.parser')

            data = {
                'profile_url':  profile_url,
                'name':         self._extract_name(soup),
                'headline':     self._extract_headline(soup),
                'location':     self._extract_location(soup),
                'about':        self._extract_about(soup),
                'company_size': self._extract_field(soup, 'Company size'),
                'company_type': self._extract_field(soup, 'Type'),
                'industry':     self._extract_field(soup, 'Industry'),
                'founded':      self._extract_field(soup, 'Founded'),
                'website':      self._extract_website(soup),
                'email':        'N/A',
                'phone':        'N/A',
            }
            logger.info(f"Scraped: {data['name']}")
            return data

        except Exception as e:
            logger.error(f"Error scraping {profile_url}: {e}")
            return None

    # ------------------------------------------------------------------
    # Extraction helpers
    # ------------------------------------------------------------------

    def _extract_company_urls(self, soup: BeautifulSoup, seen: set) -> List[str]:
        """Pull unique /company/ URLs from a search-results page."""
        urls = []
        exclude_subs = ['/jobs/', '/life/', '/people/', '/about/',
                        '/feed/', '/posts/', '/mycompany/']

        for link in soup.find_all('a', href=True):
            href = link['href']
            if '/company/' not in href:
                continue
            clean = href.split('?')[0].split('#')[0]
            if any(s in clean for s in exclude_subs):
                continue
            if not clean.startswith('http'):
                clean = f"https://www.linkedin.com{clean}"
            if clean not in seen:
                seen.add(clean)
                urls.append(clean)
        return urls

    def _extract_name(self, soup: BeautifulSoup) -> str:
        el = soup.find('h1', {'class': lambda x: x and (
            'org-top-card-summary__title' in x or 'text-heading-xlarge' in x
        )})
        return clean_text(el.get_text()) if el else 'N/A'

    def _extract_headline(self, soup: BeautifulSoup) -> str:
        el = soup.find('div', {'class': lambda x: x and 'text-body-medium' in x})
        return clean_text(el.get_text()) if el else 'N/A'

    def _extract_location(self, soup: BeautifulSoup) -> str:
        el = soup.find('div', {'class': lambda x: x and
                        'org-top-card-summary-info-list__info-item' in x})
        if el:
            return clean_text(el.get_text())
        el = soup.find('span', {'class': lambda x: x and 'text-body-small' in x})
        return clean_text(el.get_text()) if el else 'N/A'

    def _extract_about(self, soup: BeautifulSoup) -> str:
        section = soup.find('section', {'class': lambda x: x and 'artdeco-card' in x})
        if section:
            body = section.find('div', {'class': lambda x: x and 'display-flex' in x})
            if body:
                return clean_text(body.get_text())
        return 'N/A'

    def _extract_field(self, soup: BeautifulSoup, label: str) -> str:
        """Extract a labelled dt/dd pair from the About page."""
        for dt in soup.find_all('dt'):
            if label.lower() in dt.get_text().lower():
                dd = dt.find_next_sibling('dd')
                if dd:
                    return clean_text(dd.get_text())
        return 'N/A'

    def _extract_website(self, soup: BeautifulSoup) -> Optional[str]:
        # Try dt/dd approach first (About page)
        for dt in soup.find_all('dt'):
            if 'website' in dt.get_text().lower():
                dd = dt.find_next_sibling('dd')
                if dd:
                    a = dd.find('a', href=True)
                    if a:
                        return a['href']

        # Fallback: primary action button
        a = soup.find('a', {'class': lambda x: x and
                      'org-top-card-primary-actions__action' in x})
        if a and is_valid_url(a.get('href', '')):
            return a['href']
        return None

    # ------------------------------------------------------------------
    # Navigation & interaction helpers
    # ------------------------------------------------------------------

    def _go_to_next_page(self, search_url: str, current_page: int) -> bool:
        """Try clicking 'Next' or fall back to URL param."""
        try:
            btn = self.driver.find_element(By.CSS_SELECTOR, 'button[aria-label="Next"]')
            if btn.is_enabled():
                btn.click()
                time.sleep(random.uniform(3, 5))
                return True
        except NoSuchElementException:
            pass

        # URL-based fallback
        next_page = current_page + 1
        self.driver.get(f"{search_url}&page={next_page}")
        time.sleep(random.uniform(3, 5))
        return True

    def _scroll_page(self):
        """Scroll page in increments to trigger lazy-loading."""
        try:
            for frac in [0.33, 0.5, 0.66, 0.85, 1.0]:
                self.driver.execute_script(
                    f"window.scrollTo(0, document.body.scrollHeight * {frac});"
                )
                time.sleep(0.8)
        except Exception as e:
            logger.warning(f"Scroll error: {e}")

    def _random_delay(self):
        lo = self.config.get('delay_min', 3)
        hi = self.config.get('delay_max', 6)
        time.sleep(random.uniform(lo, hi))

    def _human_type(self, element, text: str):
        """Type text character-by-character with random delays."""
        try:
            ActionChains(self.driver).move_to_element(element).perform()
            time.sleep(random.uniform(0.2, 0.5))
            element.click()
            time.sleep(random.uniform(0.2, 0.5))
            for ch in text:
                element.send_keys(ch)
                time.sleep(random.uniform(0.05, 0.15))
        except Exception:
            element.send_keys(text)

    def _move_and_click(self, element):
        try:
            ActionChains(self.driver).move_to_element(element).perform()
            time.sleep(random.uniform(0.3, 0.7))
            element.click()
        except Exception:
            element.click()

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    def close(self):
        if self.driver:
            try:
                self.driver.quit()
            except Exception:
                pass
            logger.info("WebDriver closed")
