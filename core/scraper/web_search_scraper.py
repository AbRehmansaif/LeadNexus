"""
Web search scraper - finds website domains for a given niche/keyword.
Uses Selenium for search engine interaction to avoid easy blocks.
"""
import time
import random
import logging
import urllib.parse
from typing import List, Set
from bs4 import BeautifulSoup
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from fake_useragent import UserAgent

from .validators import is_valid_url

logger = logging.getLogger(__name__)

class WebSearchScraper:
    def __init__(self, driver_factory=None):
        """
        Args:
            driver_factory: A callable that returns a configured Selenium driver.
        """
        self.driver_factory = driver_factory
        self.driver = None

    def search(self, keywords: str, max_results: int = 50) -> List[str]:
        """
        Search for websites using multiple engines (DuckDuckGo, Bing, Google)
        to ensure high reliability and avoid CAPTCHA blocks.
        """
        if not self.driver_factory:
            from .linkedin_scraper import LinkedInScraper
            temp_scraper = LinkedInScraper({'scraping': {'headless': True}})
            temp_scraper.setup_driver()
            self.driver = temp_scraper.driver
        else:
            self.driver = self.driver_factory()

        unique_domains: Set[str] = set()
        
        # Request higher counts where supported
        engines = [
            {"name": "DuckDuckGo", "url": "https://html.duckduckgo.com/html/?q={query}"},
            {"name": "Bing", "url": "https://www.bing.com/search?q={query}&count=50&first=1"},
            {"name": "Google", "url": "https://www.google.com/search?q={query}&num=100"}
        ]

        try:
            for engine in engines:
                if len(unique_domains) >= max_results:
                    break
                    
                logger.info(f"Attempting search via {engine['name']}...")
                query = urllib.parse.quote(keywords)
                search_url = engine['url'].format(query=query)
                
                try:
                    if self.driver is None: continue
                    self.driver.get(search_url)
                    time.sleep(random.uniform(4, 6))

                    content = self.driver.page_source
                    if "g-recaptcha" in content or "system details from your computer" in content:
                        logger.warning(f"{engine['name']} blocked (CAPTCHA).")
                        continue

                    page = 0
                    consecutive_empty_pages = 0
                    while len(unique_domains) < max_results and page < 10:
                        if self.driver is None: break

                        # Wait for results to load
                        selector = '.result__a' if engine['name'] == "DuckDuckGo" else '.b_algo' if engine['name'] == "Bing" else '#search'
                        try:
                            WebDriverWait(self.driver, 8).until(EC.presence_of_element_located((By.CSS_SELECTOR, selector)))
                        except:
                            pass # Fallback to parsing whatever is there

                        # Scroll slightly to look active
                        self.driver.execute_script(f"window.scrollTo(0, {random.randint(200, 500)});")
                        time.sleep(random.uniform(1, 2))

                        soup = BeautifulSoup(self.driver.page_source, 'html.parser')
                        links_on_this_page: int = 0
                        
                        # Targeted extraction based on engine
                        search_results: List = []
                        if engine['name'] == "DuckDuckGo":
                            search_results = soup.select('a.result__a')
                            if not search_results:
                                search_results = soup.select('.result__title a.result__a')
                        elif engine['name'] == "Bing":
                            search_results = [h2.find('a') for h2 in soup.select('.b_algo h2') if h2.find('a')]
                            if not search_results:
                                search_results = [h2.find('a') for h2 in soup.find_all('h2') if h2.find('a')]
                        else:
                            search_results = soup.find_all('a', href=True)

                        for a in search_results:
                            if not a or not a.get('href'): continue
                            url: str = str(a['href'])
                            
                            if '/url?q=' in url: 
                                url = url.split('/url?q=')[1].split('&')[0]
                            elif 'duckduckgo.com/l/?kh=' in url:
                                continue
                            
                            url = urllib.parse.unquote(url)
                            if not url.startswith('http'): continue
                                
                            if self._is_target_website(url):
                                domain = self._extract_domain(url)
                                if domain and domain not in unique_domains:
                                    unique_domains.add(domain)
                                    links_on_this_page += 1
                                    if len(unique_domains) >= max_results:
                                        break
                        
                        logger.info(f"{engine['name']} (Page {page+1}): Found {links_on_this_page} new domains. Total: {len(unique_domains)}")
                        
                        if len(unique_domains) >= max_results:
                            break

                        if links_on_this_page == 0:
                            consecutive_empty_pages += 1
                            if consecutive_empty_pages >= 2:
                                break
                        else:
                            consecutive_empty_pages = 0
                            
                        # Pagination
                        try:
                            next_clicked = False
                            # Broad set of selectors for "Next" across engines
                            next_selectors = [
                                'input[value="Next"]',     # DuckDuckGo HTML
                                '.nav-link[value="Next"]', # DuckDuckGo alternative
                                '#pnnext',                 # Google
                                'a.sb_pagN',               # Bing
                                'a.next',                  # Generic
                                'a[aria-label="Next page"]',
                                'a.pagination__next'
                            ]
                            
                            for sel in next_selectors:
                                try:
                                    btns = self.driver.find_elements(By.CSS_SELECTOR, sel)
                                    if btns:
                                        # Use JavaScript click to bypass overlay issues
                                        self.driver.execute_script("arguments[0].click();", btns[0])
                                        next_clicked = True
                                        break
                                except: continue
                                
                            if not next_clicked:
                                # Fallback: search by text content
                                all_elements = self.driver.find_elements(By.TAG_NAME, 'a') + \
                                              self.driver.find_elements(By.TAG_NAME, 'input')
                                for el in all_elements:
                                    try:
                                        txt = (el.text or el.get_attribute('value') or '').strip().lower()
                                        if txt in ['next', 'next >', '>', 'siguiente', 'more results']:
                                            self.driver.execute_script("arguments[0].click();", el)
                                            next_clicked = True
                                            break
                                    except: continue
                            
                            if next_clicked:
                                logger.info(f"Moving to {engine['name']} Page {page + 2}...")
                                time.sleep(random.uniform(4, 7))
                                page += 1
                            else:
                                logger.debug(f"No 'Next' button found for {engine['name']} on page {page+1}")
                                break
                        except Exception as pag_err:
                            logger.debug(f"Pagination error for {engine['name']}: {pag_err}")
                            break
                            
                except Exception as engine_err:
                    logger.error(f"Error during {engine['name']} search: {engine_err}")
                    continue

        except Exception as e:
            logger.error(f"Global web search error: {e}")
        finally:
            if self.driver is not None:
                try:
                    self.driver.quit()
                    self.driver = None
                except: pass

        return list(unique_domains)

    def _is_target_website(self, url: str) -> bool:
        """Filter out search engines, social media platforms, and noise."""
        blacklist = [
            'google.', 'bing.', 'yahoo.', 'duckduckgo.',
            'facebook.', 'twitter.', 'linkedin.', 'instagram.',
            'youtube.', 'pinterest.', 'wikipedia.', 'amazon.',
            'yelp.', 'yellowpages.', 'tripadvisor.', 'wix.com',
            'wordpress.com', 'blogspot.', 'medium.com'
        ]
        
        # Also clean common tracking params
        if 'utm_' in url or 'gclid' in url:
            url = url.split('?')[0]
            
        if not is_valid_url(url):
            return False
            
        domain = self._extract_domain(url).lower()
        if not domain:
            return False
            
        for b in blacklist:
            if b in domain:
                return False
        return True

    def _extract_domain(self, url: str) -> str:
        """Extract clean 'https://domain.com' from a full URL."""
        try:
            parsed = urllib.parse.urlparse(url)
            if not parsed.netloc:
                return ""
            return f"{parsed.scheme}://{parsed.netloc}"
        except:
            return ""
