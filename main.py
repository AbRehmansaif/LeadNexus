"""
LinkedIn Data Scraper - Main Application
Collects information from LinkedIn profiles and their associated websites
"""
import argparse
import json
import os
import sys
from typing import Dict
from tqdm import tqdm

from scrapers.linkedin_scraper import LinkedInScraper
from scrapers.website_scraper import WebsiteScraper
from utils.data_storage import DataStorage
from utils.logger import logger


def load_config(config_path: str = "config.json") -> Dict:
    """
    Load configuration from JSON file
    
    Args:
        config_path: Path to config file
        
    Returns:
        Configuration dictionary
    """
    try:
        # Try to load custom config
        if os.path.exists(config_path):
            with open(config_path, 'r') as f:
                config = json.load(f)
                logger.info(f"Loaded configuration from {config_path}")
                return config
        
        # Try to load example config
        elif os.path.exists('config.example.json'):
            with open('config.example.json', 'r') as f:
                config = json.load(f)
                logger.warning("Using example config. Please create config.json for custom settings.")
                return config
        
        else:
            logger.error("No configuration file found!")
            sys.exit(1)
            
    except Exception as e:
        logger.error(f"Error loading configuration: {str(e)}")
        sys.exit(1)


def main():
    """Main application entry point"""
    
    # Parse command line arguments
    parser = argparse.ArgumentParser(
        description='LinkedIn Data Scraper - Collect business information from LinkedIn and websites'
    )
    parser.add_argument(
        '--niche',
        type=str,
        required=True,
        help='Niche or keyword to search for (e.g., "software development", "digital marketing")'
    )
    parser.add_argument(
        '--max-profiles',
        type=int,
        default=50,
        help='Maximum number of profiles to scrape (default: 50)'
    )
    parser.add_argument(
        '--config',
        type=str,
        default='config.json',
        help='Path to configuration file (default: config.json)'
    )
    parser.add_argument(
        '--output',
        type=str,
        default='./data',
        help='Output directory for data files (default: ./data)'
    )
    parser.add_argument(
        '--no-websites',
        action='store_true',
        help='Skip website scraping (only scrape LinkedIn)'
    )
    parser.add_argument(
        '--headless',
        action='store_true',
        help='Run browser in headless mode'
    )
    
    args = parser.parse_args()
    
    # Load configuration
    config = load_config(args.config)
    
    # Override config with command line arguments
    if args.output:
        config['data']['output_dir'] = args.output
    if args.headless:
        config['scraping']['headless'] = True
    if args.no_websites:
        config['website_scraping']['enabled'] = False
    
    # Initialize data storage
    storage = DataStorage(output_dir=config['data']['output_dir'])
    
    # Initialize scrapers
    linkedin_scraper = None
    website_scraper = None
    
    try:
        logger.info("=" * 60)
        logger.info("LinkedIn Data Scraper Started")
        logger.info("=" * 60)
        logger.info(f"Niche: {args.niche}")
        logger.info(f"Max Profiles: {args.max_profiles}")
        logger.info(f"Output Directory: {config['data']['output_dir']}")
        logger.info("=" * 60)
        
        # Step 1: Initialize LinkedIn scraper
        logger.info("\n[STEP 1] Initializing LinkedIn scraper...")
        linkedin_scraper = LinkedInScraper(config)
        linkedin_scraper.setup_driver()
        
        # Optional: Login to LinkedIn
        if config.get('linkedin', {}).get('use_authentication', False):
            email = config['linkedin'].get('email')
            password = config['linkedin'].get('password')
            
            if email and password:
                logger.info("Logging in to LinkedIn...")
                linkedin_scraper.login(email, password)
            else:
                logger.warning("LinkedIn credentials not provided. Proceeding without login.")
        
        # Step 2: Search and Scrape profiles simultaneously
        logger.info(f"\n[STEP 2] Searching and Scraping companies in niche: {args.niche}")
        
        def scrape_company(profile_url):
            # Scrape profile
            profile_data = linkedin_scraper.scrape_profile(profile_url)
            
            if profile_data:
                storage.add_linkedin_data(profile_data)
                # Save periodically or after each
                # storage.save_all(...)  # Optional: save incrementally
            else:
                logger.warning(f"Failed to scrape profile: {profile_url}")

        linkedin_scraper.search_and_process(args.niche, scrape_company, args.max_profiles)
        
        # Step 4: Scrape websites (if enabled)
        if config.get('website_scraping', {}).get('enabled', True) and not args.no_websites:
            logger.info("\n[STEP 4] Scraping associated websites...")
            
            # Initialize website scraper
            website_scraper = WebsiteScraper(config)
            
            # Get profiles with websites
            profiles_with_websites = [
                p for p in storage.linkedin_data 
                if p.get('website')
            ]
            
            logger.info(f"Found {len(profiles_with_websites)} profiles with websites")
            
            for i, profile in enumerate(tqdm(profiles_with_websites, desc="Scraping websites")):
                website_url = profile.get('website')
                profile_url = profile.get('profile_url')
                
                logger.info(f"\nWebsite {i+1}/{len(profiles_with_websites)}: {website_url}")
                
                # Scrape website
                website_data = website_scraper.scrape_website(website_url)
                
                if website_data:
                    storage.add_website_data(profile_url, website_data)
                    
                    # Random delay
                    website_scraper.random_delay()
                else:
                    logger.warning(f"Failed to scrape website: {website_url}")
        
        # Step 5: Save data
        logger.info("\n[STEP 5] Saving data...")
        storage.save_all(filename=f"{args.niche.replace(' ', '_')}_data")
        
        # Print statistics
        stats = storage.get_stats()
        logger.info("\n" + "=" * 60)
        logger.info("SCRAPING COMPLETE!")
        logger.info("=" * 60)
        logger.info(f"LinkedIn Profiles Scraped: {stats['linkedin_profiles']}")
        logger.info(f"Websites Scraped: {stats['websites_scraped']}")
        logger.info(f"Combined Entries: {stats['combined_entries']}")
        logger.info(f"Profiles with Website Data: {stats['profiles_with_websites']}")
        logger.info(f"Output Directory: {config['data']['output_dir']}")
        logger.info("=" * 60)
        
    except KeyboardInterrupt:
        logger.warning("\n\nScraping interrupted by user. Saving collected data...")
        if storage.linkedin_data or storage.website_data:
            storage.save_all(filename=f"{args.niche.replace(' ', '_')}_data_partial")
            logger.info("Partial data saved successfully")
    
    except Exception as e:
        logger.error(f"\n\nAn error occurred: {str(e)}", exc_info=True)
        
        # Try to save whatever data we have
        if storage.linkedin_data or storage.website_data:
            logger.info("Attempting to save collected data...")
            try:
                storage.save_all(filename=f"{args.niche.replace(' ', '_')}_data_error")
                logger.info("Data saved successfully")
            except:
                logger.error("Failed to save data")
    
    finally:
        # Cleanup
        logger.info("\nCleaning up...")
        if linkedin_scraper:
            linkedin_scraper.close()
        
        logger.info("Done!")


if __name__ == "__main__":
    main()
