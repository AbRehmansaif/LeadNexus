"""
LinkedIn scraper module
"""
import time
import random
from typing import List, Dict, Optional
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
from fake_useragent import UserAgent
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.keys import Keys

from utils.logger import logger
from utils.validators import is_valid_url, extract_email_from_text, clean_text


class LinkedInScraper:
    """Scraper for LinkedIn profiles"""
    
    def __init__(self, config: Dict):
        """
        Initialize LinkedIn scraper
        
        Args:
            config: Configuration dictionary
        """
        self.config = config
        self.driver = None
        self.wait = None
        self.is_logged_in = False
    
    def setup_driver(self):
        """Set up Selenium WebDriver"""
        logger.info("Setting up Chrome WebDriver...")
        
        chrome_options = Options()
        
        # Headless mode
        # if self.config.get('scraping', {}).get('headless', True):
        #     chrome_options.add_argument('--headless')
        
        # Additional options
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--disable-blink-features=AutomationControlled')
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)
        
        # Random user agent
        ua = UserAgent()
        chrome_options.add_argument(f'user-agent={ua.random}')
        
        # Initialize driver
        service = Service(ChromeDriverManager().install())
        self.driver = webdriver.Chrome(service=service, options=chrome_options)
        
        # Set timeouts
        timeout = self.config.get('scraping', {}).get('timeout', 30)
        self.wait = WebDriverWait(self.driver, timeout)
        
        logger.info("WebDriver setup complete")
    
    def login(self, email: str, password: str) -> bool:
        """
        Login to LinkedIn
        
        Args:
            email: LinkedIn email
            password: LinkedIn password
            
        Returns:
            True if login successful
        """
        try:
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
            login_button = self.driver.find_element(By.CSS_SELECTOR, 'button[type="submit"]')
            self._move_and_click(login_button)
            
            # Wait for redirect
            time.sleep(5)
            
            # Check if login successful
            if 'feed' in self.driver.current_url or 'mynetwork' in self.driver.current_url:
                self.is_logged_in = True
                logger.info("Login successful!")
                return True
            elif 'checkpoint' in self.driver.current_url or 'challenge' in self.driver.current_url:
                logger.warning("LinkedIn security checkpoint detected!")
                logger.info("Please complete the verification manually in the browser window.")
                input("Press Enter here after you have successfully logged in and can see your feed...")
                self.is_logged_in = True
                return True
            else:
                logger.warning("Login may have failed - check credentials")
                return False
                
        except Exception as e:
            logger.error(f"Login failed: {str(e)}")
            return False
    
    def search_and_process(self, niche: str, processor_callback, max_results: int = 50):
        """
        Search for profiles and process them one by one
        
        Args:
            niche: Search keyword/niche
            processor_callback: Function to call for each found profile URL
            max_results: Maximum number of profiles to process
        """
        processed_count = 0
        processed_urls = set()
        
        try:
            logger.info(f"Searching and processing profiles for: {niche}")
            
            # Construct search URL for Companies
            search_url = f"https://www.linkedin.com/search/results/companies/?keywords={niche.replace(' ', '%20')}"
            self.driver.get(search_url)
            time.sleep(random.uniform(3, 5))
            
            page = 1
            while processed_count < max_results:
                logger.info(f"Scanning page {page}...")
                
                # Scroll to load results
                self._scroll_page()
                
                # Get page source
                soup = BeautifulSoup(self.driver.page_source, 'html.parser')
                
                # Find profile links - Broadened search
                # We target ANY link that looks like a company profile
                all_links = soup.find_all('a', href=True)
                
                page_urls = []
                for link in all_links:
                    href = link.get('href', '')
                    
                    # Core check: must contain /company/
                    if '/company/' in href:
                        # Clean the URL (remove query params)
                        clean_url = href.split('?')[0].split('#')[0]
                        
                        # Filter out non-profile pages
                        # We want: /company/google
                        # We do NOT want: /company/google/jobs, /company/google/life, etc.
                        # Sometimes the href is relative: /company/google
                        
                        # Check for sub-pages to exclude
                        if any(sub in clean_url for sub in ['/jobs/', '/life/', '/people/', '/about/', '/feed/', '/posts/', '/mycompany/']):
                            continue
                            
                        # Ensure absolute URL
                        if not clean_url.startswith('http'):
                            clean_url = f"https://www.linkedin.com{clean_url}"
                            
                        # Deduplicate
                        if clean_url not in processed_urls and clean_url not in page_urls:
                            processed_urls.add(clean_url)
                            page_urls.append(clean_url)
                            logger.info(f"Found company: {clean_url}")
                
                # Debugging: If no companies found, log what we see
                if not page_urls:
                    logger.warning("No companies found on this page with current criteria.")
                    # Optional: Print some hrefs to see what's going on
                    # sample_hrefs = [l.get('href', '') for l in all_links[:10]]
                    # logger.debug(f"Sample links found: {sample_hrefs}")
                
                logger.info(f"Found {len(page_urls)} new companies on page {page}")

                # Process found URLs on this page
                for url in page_urls:
                    if processed_count >= max_results:
                        break
                        
                    logger.info(f"Processing company {processed_count + 1}/{max_results}: {url}")
                    
                    # Call the callback (scraping function)
                    processor_callback(url)
                    processed_count += 1
                    
                    # Return to search results if we navigated away
                    if self.driver.current_url != search_url:
                        self.driver.back()
                        time.sleep(random.uniform(2, 4))
                        # We might need to handle pagination state here if 'back' loses it, 
                        # but often LinkedIn keeps state or we re-construct the search URL with page param
                        
                # Pagination logic
                if processed_count < max_results:
                    try:
                        # Re-find next button because DOM might have changed or became stale
                        next_button = self.driver.find_element(By.CSS_SELECTOR, 'button[aria-label="Next"]')
                        if next_button.is_enabled():
                            next_button.click()
                            time.sleep(random.uniform(3, 5))
                            page += 1
                        else:
                            logger.info("No next page button enabled.")
                            break
                    except NoSuchElementException:
                        # If simple Next button isn't found, try URL manipulation for next page
                        logger.info("Next button not found, trying URL pagination...")
                        page += 1
                        next_page_url = f"{search_url}&page={page}"
                        self.driver.get(next_page_url)
                        time.sleep(random.uniform(3, 5))

        except Exception as e:
            logger.error(f"Error in search_and_process: {str(e)}")
            return profile_urls
    
    def scrape_profile(self, profile_url: str) -> Optional[Dict]:
        """
        Scrape data from a LinkedIn profile
        
        Args:
            profile_url: LinkedIn profile URL
            
        Returns:
            Dictionary with profile data or None
        """
        try:
            logger.info(f"Scraping profile: {profile_url}")
            
            # Visit 'About' section for better data
            about_url = f"{profile_url}/about/" if not profile_url.endswith('/about/') else profile_url
            self.driver.get(about_url)
            time.sleep(random.uniform(2, 4))
            
            # Scroll to load content
            self._scroll_page()
            
            # Parse page
            soup = BeautifulSoup(self.driver.page_source, 'html.parser')
            
            # Extract data
            data = {
                'profile_url': profile_url,
                'name': self._extract_name(soup),
                'headline': self._extract_headline(soup), 
                'location': self._extract_location(soup),
                'about': self._extract_about(soup),
                'company_size': self._extract_company_size(soup),
                'company_type': self._extract_company_type(soup),
                'website': self._extract_website(soup),
                'email': "N/A", 
                'phone': "N/A", 
            }
            
            logger.info(f"Successfully scraped profile: {data['name']}")
            return data
            
        except Exception as e:
            logger.error(f"Error scraping profile {profile_url}: {str(e)}")
            return None
    
    def _scroll_page(self):
        """Scroll page to load dynamic content"""
        try:
            # Scroll down in increments
            for _ in range(3):
                self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight/3);")
                time.sleep(1)
                self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight/2);")
                time.sleep(1)
                self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(1)
        except Exception as e:
            logger.warning(f"Error scrolling page: {str(e)}")
    
    def _extract_name(self, soup: BeautifulSoup) -> str:
        """Extract company name"""
        try:
            name_elem = soup.find('h1', {'class': lambda x: x and ('org-top-card-summary__title' in x or 'text-heading-xlarge' in x)})
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
            location_elem = soup.find('div', {'class': lambda x: x and 'org-top-card-summary-info-list__info-item' in x})
            if location_elem:
                 return clean_text(location_elem.get_text())
            
            # Fallback
            location_elem = soup.find('span', {'class': lambda x: x and 'text-body-small' in x})
            if location_elem:
                return clean_text(location_elem.get_text())
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
        """Extract company size"""
        try:
            # Look in description list (dl) common in About pages
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
        """Extract company type (Public, Private, etc.)"""
        try:
             # Look in description list (dl) common in About pages
            dt_tags = soup.find_all('dt')
            for dt in dt_tags:
                if 'Type' in dt.get_text():
                    dd = dt.find_next_sibling('dd')
                    if dd:
                        return clean_text(dd.get_text())
        except:
            pass
        return "N/A"
    
    def _extract_website(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract website URL from company profile"""
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
            website_link = soup.find('a', {'class': lambda x: x and 'org-top-card-primary-actions__action' in x})
            if website_link:
                href = website_link.get('href', '')
                if is_valid_url(href):
                    return href
        except:
            pass
        return None
    
    def _extract_contact_info(self, soup: BeautifulSoup, info_type: str) -> Optional[str]:
        """Extract contact information from profile"""
        try:
            # Try to click contact info button
            contact_button = self.driver.find_element(By.CSS_SELECTOR, 'a[href*="overlay/contact-info"]')
            contact_button.click()
            time.sleep(2)
            
            # Parse contact info modal
            contact_soup = BeautifulSoup(self.driver.page_source, 'html.parser')
            
            if info_type == 'email':
                return extract_email_from_text(contact_soup.get_text())
            elif info_type == 'phone':
                # Look for phone number patterns
                phone_section = contact_soup.find('section', {'class': lambda x: x and 'pv-contact-info__contact-type' in x})
                if phone_section:
                    return clean_text(phone_section.get_text())
            
            # Close modal
            close_button = self.driver.find_element(By.CSS_SELECTOR, 'button[aria-label="Dismiss"]')
            close_button.click()
            time.sleep(1)
            
        except:
            pass
        return None
    
    def random_delay(self):
        """Add random delay between requests"""
        delay_min = self.config.get('scraping', {}).get('delay_min', 2)
        delay_max = self.config.get('scraping', {}).get('delay_max', 5)
        delay = random.uniform(delay_min, delay_max)
        logger.debug(f"Waiting {delay:.2f} seconds...")
        time.sleep(delay)
    
    def _human_interaction(self, element, text: str):
        """
        Simulate human typing and interaction
        
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
        Simulate moving mouse to element and clicking
        
        Args:
            element: WebElement to click
        """
        try:
            actions = ActionChains(self.driver)
            actions.move_to_element(element).perform()
            time.sleep(random.uniform(0.3, 0.7))
            element.click()
        except Exception as e:
            logger.warning(f"Error in move and click: {str(e)}")
            element.click()

    def close(self):
        """Close the WebDriver"""
        if self.driver:
            self.driver.quit()
            logger.info("WebDriver closed")
