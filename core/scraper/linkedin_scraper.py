"""
LinkedIn scraper — Django-integrated version.
Ported from scrapers/linkedin_scraper.py into the core Django app.

Opens Chrome, logs into LinkedIn, searches for companies by niche,
scrapes profiles one by one, and extracts company data.
"""
import os
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
from fake_useragent import UserAgent

from .validators import is_valid_url, extract_email_from_text, clean_text

logger = logging.getLogger(__name__)


class LinkedInScraper:
    """
    Selenium-based LinkedIn company scraper.
    Designed to run in a background thread from a Django view / task.

    This is a direct port of scrapers/linkedin_scraper.py — the original
    standalone scraper. Config keys match the original format.
    """

    def __init__(self, config: Dict):
        """
        Initialize LinkedIn scraper.

        Args:
            config: Configuration dictionary (matches scrapers/linkedin_scraper.py format)
        """
        self.config = config
        self.driver = None
        self.wait = None
        self.is_logged_in = False

    # ------------------------------------------------------------------
    # Driver setup
    # ------------------------------------------------------------------

    def setup_driver(self):
        """Set up Chrome WebDriver with anti-detection options."""
        logger.info("Setting up Chrome WebDriver...")

        chrome_options = Options()

        # Headless mode
        if self.config.get('scraping', {}).get('headless', False):
            chrome_options.add_argument('--headless=new')

        # Additional options for stability & stealth
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--disable-gpu')
        chrome_options.add_argument('--window-size=1920,1080')
        chrome_options.add_argument('--disable-blink-features=AutomationControlled')
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)

        # Random user agent (same as original)
        ua = UserAgent()
        chrome_options.add_argument(f'user-agent={ua.random}')

        # Initialize driver with webdriver-manager
        try:
            from webdriver_manager.chrome import ChromeDriverManager
            # Use the default OS detection, or linux64 for Docker
            driver_path = ChromeDriverManager().install()
            logger.info(f"webdriver-manager returned: {driver_path}")

            # Correct the path if it's not pointing to the binary directly
            if not os.path.isfile(driver_path) or 'THIRD_PARTY' in driver_path:
                # Find the actual chromedriver binary in the installation directory
                import glob
                base_dir = os.path.dirname(driver_path)
                found_paths = glob.glob(os.path.join(base_dir, '**/chromedriver'), recursive=True)
                if not found_paths:
                    # Try with .exe extension (for robustness during development)
                    found_paths = glob.glob(os.path.join(base_dir, '**/chromedriver.exe'), recursive=True)
                
                if found_paths:
                    driver_path = found_paths[0]
                    logger.info(f"Found chromedriver at: {driver_path}")

            service = Service(executable_path=driver_path)
        except ImportError:
            service = Service()  # fallback: expects chromedriver on PATH
        except Exception as e:
            logger.warning(f"webdriver-manager failed: {e}, falling back to PATH")
            service = Service()

        self.driver = webdriver.Chrome(service=service, options=chrome_options)

        # Set timeouts (same as original)
        timeout = self.config.get('scraping', {}).get('timeout', 30)
        self.wait = WebDriverWait(self.driver, timeout)

        logger.info("WebDriver setup complete")

    # ------------------------------------------------------------------
    # Login  (matches scrapers/linkedin_scraper.py exactly)
    # ------------------------------------------------------------------

    # ------------------------------------------------------------------
    # Login
    # ------------------------------------------------------------------

    def login(self, email: str, password: str) -> bool:
        """
        Login to LinkedIn.
        Synchronized with standalone version but handles checkpoints for background tasks.
        """
        try:
            if not self.driver:
                return False

            logger.info("Attempting to login to LinkedIn...")
            self.driver.get('https://www.linkedin.com/login')
            
            # Wait for login form
            email_field = self.wait.until(
                EC.presence_of_element_located((By.ID, 'username'))
            )
            password_field = self.driver.find_element(By.ID, 'password')
            
            # Enter credentials with human-like behavior
            self._human_interaction(email_field, email)
            time.sleep(random.uniform(0.5, 1.5))
            
            self._human_interaction(password_field, password)
            time.sleep(random.uniform(0.5, 1.5))
            
            # Click login button
            login_btn = self.driver.find_element(By.CSS_SELECTOR, 'button[type="submit"]')
            self._move_and_click(login_btn)
            
            # Wait for redirect
            time.sleep(5)
            
            # Check success (defensive guards)
            try:
                curr = self.driver.current_url.lower()
            except:
                curr = ""

            if 'feed' in curr or 'mynetwork' in curr or 'jobs' in curr:
                self.is_logged_in = True
                logger.info("Login successful!")
                return True
            elif 'checkpoint' in curr or 'challenge' in curr:
                logger.warning("LinkedIn security checkpoint detected!")
                # Wait for manual solve in the browser (120s max for background safety)
                for _ in range(24):
                    time.sleep(5)
                    try:
                        temp_curr = self.driver.current_url.lower()
                        if 'feed' in temp_curr or 'mynetwork' in temp_curr:
                            self.is_logged_in = True
                            logger.info("Login successful after manual verification!")
                            return True
                    except:
                        break
                logger.warning("Login timed out waiting for checkpoint solve")
                return False
            else:
                # Fallback: check for global nav
                try:
                    self.driver.find_element(By.ID, 'global-nav')
                    self.is_logged_in = True
                    logger.info("Login successful (detected global-nav)")
                    return True
                except:
                    logger.warning(f"Login outcome uncertain. URL: {curr}")
                    return False
                
        except Exception as e:
            logger.error(f"Login failed: {str(e)}")
            return False

    # ------------------------------------------------------------------
    # Search & process pipeline
    # ------------------------------------------------------------------

    def search_and_scrape(
        self,
        niche: str,
        max_results: int = 50,
        location: str = "",
        company_size: str = "",
        progress_callback: Optional[Callable] = None,
        processor_callback: Optional[Callable] = None,
    ) -> List[Dict]:
        """
        Search for profiles and process them one by one.
        Improved version: Uses new tabs to keep search results stable.
        """
        results: List[Dict] = []
        processed_urls: set = set()

        try:
            # Build search URL with optional filters
            search_keywords = niche.strip()
            if location:
                # Add location directly to keywords as LinkedIn handles this well
                search_keywords += f" {location.strip()}"
            
            size_facet = ""
            if company_size and len(company_size) == 1 and company_size.upper() in "ABCDEFGHI":
                # LinkedIn facets for company size
                size_facet = f"&companySize=%5B%22{company_size.upper()}%22%5D"
            elif company_size:
                # Fallback for search query
                search_keywords += f" {company_size}"

            logger.info(f"Searching for: {search_keywords} (Facets: {company_size if company_size else 'None'})")

            # Combine keywords and origin with facets
            search_url = f"https://www.linkedin.com/search/results/companies/?keywords={search_keywords.replace(' ', '%20')}&origin=FACETED_SEARCH{size_facet}"
            self.driver.get(search_url)
            time.sleep(random.uniform(7, 10)) # Increased wait for search results to settle

            page = 1
            search_window = self.driver.current_window_handle

            while len(results) < max_results:
                # Check for "Page doesn't exist" or Bot detection
                if "page doesn't exist" in self.driver.page_source.lower() or "content unavailable" in self.driver.page_source.lower():
                    logger.warning("LinkedIn blocked access to this page (404 or detection). Ending scrape.")
                    break

                logger.info(f"Scanning page {page} (collected {len(results)}/max_results)...")
                
                # Check for login redirection
                if "login" in self.driver.current_url.lower() and not self.is_logged_in:
                    logger.warning("Redirected to login page. Stopping search.")
                    break

                self._scroll_page()

                # Get page source
                soup = BeautifulSoup(self.driver.page_source, 'html.parser')

                # Find profile links
                all_links = soup.find_all('a', href=True)
                page_urls = []
                for link in all_links:
                    href = link.get('href', '')
                    if '/company/' in href:
                        clean_url = href.split('?')[0].split('#')[0]
                        # Exclude sub-pages
                        if any(sub in clean_url for sub in ['/jobs/', '/life/', '/people/', '/about/', '/feed/', '/posts/', '/mycompany/']):
                            continue
                        if not clean_url.startswith('http'):
                            clean_url = f"https://www.linkedin.com{clean_url}"
                        if clean_url not in processed_urls:
                            processed_urls.add(clean_url)
                            page_urls.append(clean_url)

                if not page_urls:
                    logger.warning("No new companies found on this page.")
                    # Try to see if we reached the end
                    if "no results found" in self.driver.page_source.lower():
                        break

                for url in page_urls:
                    if len(results) >= max_results:
                        break

                    logger.info(f"Processing company {len(results) + 1}/{max_results}: {url}")
                    
                    # --- Multi-tab scraping for stability ---
                    # Open in NEW window/tab
                    self.driver.execute_script("window.open('');")
                    self.driver.switch_to.window(self.driver.window_handles[-1])
                    
                    profile_data = self.scrape_profile(url)
                    
                    # Close the tab
                    self.driver.close()
                    # Back to search tab
                    self.driver.switch_to.window(search_window)

                    if profile_data:
                        results.append(profile_data)
                        if processor_callback:
                            processor_callback(profile_data)
                    
                    if progress_callback:
                        progress_callback(len(results), max_results)

                    self.random_delay()

                # Pagination
                if len(results) < max_results:
                    try:
                        next_button = self.driver.find_element(By.CSS_SELECTOR, 'button[aria-label="Next"]')
                        if next_button.is_enabled():
                            self._move_and_click(next_button)
                            time.sleep(random.uniform(4, 6))
                            page += 1
                        else:
                            logger.info("Next button disabled.")
                            break
                    except:
                        # Fallback pagination
                        page += 1
                        logger.info(f"Next button not found, trying URL pagination for page {page}...")
                        self.driver.get(f"{search_url}&page={page}")
                        time.sleep(random.uniform(4, 6))
                        # Verify we actually moved
                        if "page=" + str(page) not in self.driver.current_url:
                           # Sometimes the param is offset or something else, but LinkedIn usually likes page=
                           pass

        except Exception as e:
            logger.error(f"Error in search_and_scrape: {str(e)}", exc_info=True)

        logger.info(f"Scraping complete — {len(results)} companies scraped")
        return results

    # ------------------------------------------------------------------
    # Single company scrape  (matches original scrape_profile exactly)
    # ------------------------------------------------------------------

    def scrape_profile(self, profile_url: str) -> Optional[Dict]:
        """
        Scrape data from a LinkedIn company profile.

        Args:
            profile_url: LinkedIn company profile URL

        Returns:
            Dictionary with profile data or None
        """
        try:
            logger.info(f"Scraping profile: {profile_url}")

            # Visit 'About' section for better data (same as original)
            about_url = f"{profile_url}/about/" if not profile_url.endswith('/about/') else profile_url
            self.driver.get(about_url)
            time.sleep(random.uniform(2, 4))

            # Scroll to load content
            self._scroll_page()

            # Parse page
            soup = BeautifulSoup(self.driver.page_source, 'html.parser')

            # Extract data (same fields as original)
            data = {
                'profile_url': profile_url,
                'name': self._extract_name(soup),
                'headline': self._extract_headline(soup),
                'location': self._extract_location(soup),
                'about': self._extract_about(soup),
                'company_size': self._extract_company_size(soup),
                'company_type': self._extract_company_type(soup),
                'industry': self._extract_field(soup, 'Industry'),
                'founded': self._extract_field(soup, 'Founded'),
                'website': self._extract_website(soup),
                'email': 'N/A',
                'phone': 'N/A',
            }

            logger.info(f"Successfully scraped profile: {data['name']}")
            return data

        except Exception as e:
            logger.error(f"Error scraping profile {profile_url}: {str(e)}")
            return None

    # ------------------------------------------------------------------
    # Extraction helpers  (match original exactly)
    # ------------------------------------------------------------------

    def _extract_name(self, soup: BeautifulSoup) -> str:
        """Extract company name"""
        try:
            name_elem = soup.find('h1', {'class': lambda x: x and (
                'org-top-card-summary__title' in x or 'text-heading-xlarge' in x
            )})
            if name_elem:
                return clean_text(name_elem.get_text())
        except:
            pass
        return "N/A"

    def _extract_headline(self, soup: BeautifulSoup) -> str:
        """Extract headline from profile"""
        try:
            headline_elem = soup.find('div', {'class': lambda x: x and 'text-body-medium' in x})
            if headline_elem:
                return clean_text(headline_elem.get_text())
        except:
            pass
        return "N/A"

    def _extract_location(self, soup: BeautifulSoup) -> str:
        """Extract company location"""
        try:
            # Get the industry to help identify what NOT to pick as location
            industry = self._extract_field(soup, 'Industry')
            
            # Find all summary info items
            items = soup.find_all('div', {'class': lambda x: x and 
                                       'org-top-card-summary-info-list__info-item' in x})
            
            for item in items:
                text = clean_text(item.get_text())
                # Skip the item if it matches the industry or is a follower count
                if text == industry or 'follower' in text.lower() or not text:
                    continue
                return text

            # Fallback: Check for Headquarters in About section
            hq = self._extract_field(soup, 'Headquarters')
            if hq and hq != 'N/A':
                return hq

            # Final fallback
            location_elem = soup.find('span', {'class': lambda x: x and 'text-body-small' in x})
            if location_elem:
                text = clean_text(location_elem.get_text())
                if text != industry and 'follower' not in text.lower():
                    return text
        except:
            pass
        return "N/A"

    def _extract_about(self, soup: BeautifulSoup) -> str:
        """Extract about section from profile"""
        try:
            about_section = soup.find('section', {'class': lambda x: x and 'artdeco-card' in x})
            if about_section:
                about_text = about_section.find('div', {'class': lambda x: x and 'display-flex' in x})
                if about_text:
                    return clean_text(about_text.get_text())
        except:
            pass
        return "N/A"

    def _extract_company_size(self, soup: BeautifulSoup) -> str:
        """Extract company size (same as original)"""
        try:
            dt_tags = soup.find_all('dt')
            for dt in dt_tags:
                if 'Company size' in dt.get_text():
                    dd = dt.find_next_sibling('dd')
                    if dd:
                        return clean_text(dd.get_text())
        except:
            pass
        return "N/A"

    def _extract_company_type(self, soup: BeautifulSoup) -> str:
        """Extract company type (Public, Private, etc.) — same as original"""
        try:
            dt_tags = soup.find_all('dt')
            for dt in dt_tags:
                if 'Type' in dt.get_text():
                    dd = dt.find_next_sibling('dd')
                    if dd:
                        return clean_text(dd.get_text())
        except:
            pass
        return "N/A"

    def _extract_field(self, soup: BeautifulSoup, label: str) -> str:
        """Extract a labelled dt/dd pair from the About page."""
        try:
            for dt in soup.find_all('dt'):
                if label.lower() in dt.get_text().lower():
                    dd = dt.find_next_sibling('dd')
                    if dd:
                        return clean_text(dd.get_text())
        except:
            pass
        return 'N/A'

    def _extract_website(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract website URL from company profile (same as original)"""
        try:
            # Look in description list (dl) common in About pages
            dt_tags = soup.find_all('dt')
            for dt in dt_tags:
                if 'Website' in dt.get_text():
                    dd = dt.find_next_sibling('dd')
                    if dd:
                        link = dd.find('a', href=True)
                        if link:
                            return link['href']

            # Fallback: Primary button
            website_link = soup.find('a', {'class': lambda x: x and
                                     'org-top-card-primary-actions__action' in x})
            if website_link:
                href = website_link.get('href', '')
                if is_valid_url(href):
                    return href
        except:
            pass
        return None

    def _extract_contact_info(self, soup: BeautifulSoup, info_type: str) -> Optional[str]:
        """Extract contact information from profile (same as original)"""
        try:
            contact_button = self.driver.find_element(By.CSS_SELECTOR, 'a[href*="overlay/contact-info"]')
            contact_button.click()
            time.sleep(2)

            contact_soup = BeautifulSoup(self.driver.page_source, 'html.parser')

            if info_type == 'email':
                return extract_email_from_text(contact_soup.get_text())
            elif info_type == 'phone':
                phone_section = contact_soup.find('section', {'class': lambda x: x and
                                                  'pv-contact-info__contact-type' in x})
                if phone_section:
                    return clean_text(phone_section.get_text())

            # Close modal
            close_button = self.driver.find_element(By.CSS_SELECTOR, 'button[aria-label="Dismiss"]')
            close_button.click()
            time.sleep(1)

        except:
            pass
        return None

    # ------------------------------------------------------------------
    # Navigation & interaction helpers  (exact match to original)
    # ------------------------------------------------------------------

    def _scroll_page(self):
        """Scroll page to load dynamic content (same as original)"""
        try:
            for _ in range(3):
                self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight/3);")
                time.sleep(1)
                self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight/2);")
                time.sleep(1)
                self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(1)
        except Exception as e:
            logger.warning(f"Error scrolling page: {str(e)}")

    def random_delay(self):
        """Add random delay between requests (same as original)"""
        delay_min = self.config.get('scraping', {}).get('delay_min', 2)
        delay_max = self.config.get('scraping', {}).get('delay_max', 5)
        delay = random.uniform(delay_min, delay_max)
        logger.debug(f"Waiting {delay:.2f} seconds...")
        time.sleep(delay)

    def _human_interaction(self, element, text: str):
        """
        Simulate human typing and interaction (EXACT copy from original).

        Args:
            element: WebElement to interact with
            text: Text to type
        """
        try:
            # Move to element
            actions = ActionChains(self.driver)
            actions.move_to_element(element).perform()
            time.sleep(random.uniform(0.2, 0.5))

            # Click element
            element.click()
            time.sleep(random.uniform(0.2, 0.5))

            # Type character by character with random delays
            for char in text:
                element.send_keys(char)
                time.sleep(random.uniform(0.05, 0.2))  # Random typing speed

        except Exception as e:
            logger.warning(f"Error in human interaction: {str(e)}")
            # Fallback to standard send_keys
            element.send_keys(text)

    def _move_and_click(self, element):
        """
        Simulate moving mouse to element and clicking (same as original).
        """
        try:
            actions = ActionChains(self.driver)
            actions.move_to_element(element).perform()
            time.sleep(random.uniform(0.3, 0.7))
            element.click()
        except Exception as e:
            logger.warning(f"Error in move and click: {str(e)}")
            element.click()

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    def close(self):
        """Close the WebDriver"""
        if self.driver:
            try:
                self.driver.quit()
            except Exception:
                pass
            logger.info("WebDriver closed")
