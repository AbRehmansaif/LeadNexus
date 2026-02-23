"""
Website scraper module
"""
import time
import random
import requests
from typing import Dict, Optional, List
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from fake_useragent import UserAgent

from utils.logger import logger
from utils.validators import (
    is_valid_url, 
    is_valid_email, 
    extract_email_from_text,
    extract_phone_from_text,
    clean_text
)


class WebsiteScraper:
    """Scraper for extracting data from websites"""
    
    def __init__(self, config: Dict):
        """
        Initialize website scraper
        
        Args:
            config: Configuration dictionary
        """
        self.config = config
        self.session = requests.Session()
        self.ua = UserAgent()
        
        # Set default headers
        self.session.headers.update({
            'User-Agent': self.ua.random,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
        })
    
    def scrape_website(self, url: str) -> Optional[Dict]:
        """
        Scrape data from a website
        
        Args:
            url: Website URL
            
        Returns:
            Dictionary with website data or None
        """
        if not is_valid_url(url):
            logger.warning(f"Invalid URL: {url}")
            return None
        
        try:
            logger.info(f"Scraping website: {url}")
            
            # Initialize data
            data = {
                'website_url': url,
                'email': None,
                'phone': None,
                'facebook': None,
                'twitter': None,
                'instagram': None,
                'linkedin': None,
                'address': None,
            }
            
            # Get main page
            main_page_data = self._scrape_page(url)
            if main_page_data:
                data.update(main_page_data)
            
            # Try to find and scrape contact page
            if self.config.get('website_scraping', {}).get('enabled', True):
                contact_urls = self._find_contact_pages(url)
                
                for contact_url in contact_urls[:3]:  # Limit to 3 contact pages
                    logger.info(f"Scraping contact page: {contact_url}")
                    contact_data = self._scrape_page(contact_url)
                    
                    if contact_data:
                        # Update data with contact page info (don't overwrite existing data)
                        for key, value in contact_data.items():
                            if value and not data.get(key):
                                data[key] = value
                    
                    time.sleep(random.uniform(1, 2))
            
            logger.info(f"Successfully scraped website: {url}")
            return data
            
        except Exception as e:
            logger.error(f"Error scraping website {url}: {str(e)}")
            return None
    
    def _scrape_page(self, url: str) -> Optional[Dict]:
        """
        Scrape a single page
        
        Args:
            url: Page URL
            
        Returns:
            Dictionary with extracted data
        """
        try:
            timeout = self.config.get('website_scraping', {}).get('timeout', 15)
            response = self.session.get(url, timeout=timeout)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Extract data
            data = {
                'email': self._extract_emails(soup),
                'phone': self._extract_phones(soup),
                'facebook': self._extract_social_link(soup, 'facebook'),
                'twitter': self._extract_social_link(soup, 'twitter'),
                'instagram': self._extract_social_link(soup, 'instagram'),
                'linkedin': self._extract_social_link(soup, 'linkedin'),
                'address': self._extract_address(soup),
            }
            
            return data
            
        except requests.RequestException as e:
            logger.warning(f"Request failed for {url}: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"Error parsing page {url}: {str(e)}")
            return None
    
    def _find_contact_pages(self, base_url: str) -> List[str]:
        """
        Find contact/about pages on a website
        
        Args:
            base_url: Base website URL
            
        Returns:
            List of potential contact page URLs
        """
        contact_urls = []
        
        try:
            response = self.session.get(base_url, timeout=10)
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Common contact page keywords
            keywords = ['contact', 'about', 'team', 'connect', 'reach', 'get-in-touch']
            
            # Find all links
            links = soup.find_all('a', href=True)
            
            for link in links:
                href = link.get('href', '').lower()
                text = link.get_text().lower()
                
                # Check if link contains contact keywords
                if any(keyword in href or keyword in text for keyword in keywords):
                    full_url = urljoin(base_url, link['href'])
                    
                    # Ensure it's from the same domain
                    if urlparse(full_url).netloc == urlparse(base_url).netloc:
                        if full_url not in contact_urls:
                            contact_urls.append(full_url)
            
            logger.info(f"Found {len(contact_urls)} potential contact pages")
            return contact_urls
            
        except Exception as e:
            logger.warning(f"Error finding contact pages: {str(e)}")
            return []
    
    def _extract_emails(self, soup: BeautifulSoup) -> Optional[str]:
        """
        Extract email addresses from page
        
        Args:
            soup: BeautifulSoup object
            
        Returns:
            First valid email found or None
        """
        # Get all text
        page_text = soup.get_text()
        
        # Extract email
        email = extract_email_from_text(page_text)
        
        if email:
            logger.debug(f"Found email: {email}")
            return email
        
        # Try mailto links
        mailto_links = soup.find_all('a', href=lambda x: x and 'mailto:' in x)
        for link in mailto_links:
            email = link['href'].replace('mailto:', '').split('?')[0]
            if is_valid_email(email):
                logger.debug(f"Found email in mailto: {email}")
                return email
        
        return None
    
    def _extract_phones(self, soup: BeautifulSoup) -> Optional[str]:
        """
        Extract phone numbers from page
        
        Args:
            soup: BeautifulSoup object
            
        Returns:
            First valid phone found or None
        """
        # Get all text
        page_text = soup.get_text()
        
        # Extract phone
        phone = extract_phone_from_text(page_text)
        
        if phone:
            logger.debug(f"Found phone: {phone}")
            return phone
        
        # Try tel links
        tel_links = soup.find_all('a', href=lambda x: x and 'tel:' in x)
        for link in tel_links:
            phone = link['href'].replace('tel:', '').strip()
            logger.debug(f"Found phone in tel link: {phone}")
            return phone
        
        return None
    
    def _extract_social_link(self, soup: BeautifulSoup, platform: str) -> Optional[str]:
        """
        Extract social media links
        
        Args:
            soup: BeautifulSoup object
            platform: Social media platform name
            
        Returns:
            Social media URL or None
        """
        platform_domains = {
            'facebook': ['facebook.com', 'fb.com'],
            'twitter': ['twitter.com', 'x.com'],
            'instagram': ['instagram.com'],
            'linkedin': ['linkedin.com'],
        }
        
        domains = platform_domains.get(platform.lower(), [])
        
        # Find all links
        links = soup.find_all('a', href=True)
        
        for link in links:
            href = link.get('href', '').lower()
            
            # Check if link contains platform domain
            if any(domain in href for domain in domains):
                full_url = link['href']
                if is_valid_url(full_url):
                    logger.debug(f"Found {platform} link: {full_url}")
                    return full_url
        
        return None
    
    def _extract_address(self, soup: BeautifulSoup) -> Optional[str]:
        """
        Extract physical address from page
        
        Args:
            soup: BeautifulSoup object
            
        Returns:
            Address string or None
        """
        # Look for address in schema.org markup
        address_schema = soup.find('span', {'itemprop': 'address'})
        if address_schema:
            return clean_text(address_schema.get_text())
        
        # Look for address class
        address_elem = soup.find(['div', 'p', 'span'], {'class': lambda x: x and 'address' in str(x).lower()})
        if address_elem:
            return clean_text(address_elem.get_text())
        
        # Look for common address patterns
        text = soup.get_text()
        
        # Simple pattern: look for street, city, state, zip
        import re
        address_pattern = r'\d+\s+[\w\s]+(?:Street|St|Avenue|Ave|Road|Rd|Boulevard|Blvd|Lane|Ln|Drive|Dr)[,\s]+[\w\s]+[,\s]+[A-Z]{2}\s+\d{5}'
        match = re.search(address_pattern, text)
        
        if match:
            return clean_text(match.group(0))
        
        return None
    
    def random_delay(self):
        """Add random delay between requests"""
        delay = random.uniform(1, 3)
        logger.debug(f"Waiting {delay:.2f} seconds...")
        time.sleep(delay)
