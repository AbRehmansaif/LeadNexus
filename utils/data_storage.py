"""
Data storage utilities for saving scraped data
"""
import json
import csv
import os
import pandas as pd
from datetime import datetime
from typing import List, Dict, Any
from utils.logger import logger


class DataStorage:
    """Handle data storage in multiple formats"""
    
    def __init__(self, output_dir: str = "./data"):
        """
        Initialize data storage
        
        Args:
            output_dir: Directory to save data files
        """
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)
        
        self.linkedin_data = []
        self.website_data = []
        self.combined_data = []
    
    def add_linkedin_data(self, data: Dict[str, Any]):
        """
        Add LinkedIn profile data
        
        Args:
            data: Dictionary containing profile data
        """
        data['scraped_at'] = datetime.now().isoformat()
        self.linkedin_data.append(data)
        logger.info(f"Added LinkedIn data for: {data.get('name', 'Unknown')}")
    
    def add_website_data(self, linkedin_url: str, data: Dict[str, Any]):
        """
        Add website data linked to LinkedIn profile
        
        Args:
            linkedin_url: LinkedIn profile URL
            data: Dictionary containing website data
        """
        data['linkedin_url'] = linkedin_url
        data['scraped_at'] = datetime.now().isoformat()
        self.website_data.append(data)
        logger.info(f"Added website data for: {data.get('website_url', 'Unknown')}")
    
    def combine_data(self):
        """Combine LinkedIn and website data"""
        self.combined_data = []
        
        for linkedin_entry in self.linkedin_data:
            combined_entry = linkedin_entry.copy()
            
            # Find matching website data
            website_entries = [
                w for w in self.website_data 
                if w.get('linkedin_url') == linkedin_entry.get('profile_url')
            ]
            
            if website_entries:
                # Merge with first matching website entry
                website_entry = website_entries[0]
                combined_entry.update({
                    'website_email': website_entry.get('email'),
                    'website_phone': website_entry.get('phone'),
                    'website_facebook': website_entry.get('facebook'),
                    'website_twitter': website_entry.get('twitter'),
                    'website_instagram': website_entry.get('instagram'),
                    'website_address': website_entry.get('address'),
                })
            
            self.combined_data.append(combined_entry)
        
        logger.info(f"Combined {len(self.combined_data)} entries")
    
    def save_to_csv(self, filename: str = None):
        """
        Save data to CSV files
        
        Args:
            filename: Optional custom filename prefix
        """
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        prefix = filename or 'scraped_data'
        
        # Save LinkedIn data
        if self.linkedin_data:
            linkedin_file = os.path.join(self.output_dir, f'{prefix}_linkedin_{timestamp}.csv')
            df = pd.DataFrame(self.linkedin_data)
            df.to_csv(linkedin_file, index=False, encoding='utf-8-sig')
            logger.info(f"Saved LinkedIn data to: {linkedin_file}")
        
        # Save website data
        if self.website_data:
            website_file = os.path.join(self.output_dir, f'{prefix}_website_{timestamp}.csv')
            df = pd.DataFrame(self.website_data)
            df.to_csv(website_file, index=False, encoding='utf-8-sig')
            logger.info(f"Saved website data to: {website_file}")
        
        # Save combined data
        if self.combined_data:
            combined_file = os.path.join(self.output_dir, f'{prefix}_combined_{timestamp}.csv')
            df = pd.DataFrame(self.combined_data)
            df.to_csv(combined_file, index=False, encoding='utf-8-sig')
            logger.info(f"Saved combined data to: {combined_file}")
    
    def save_to_json(self, filename: str = None):
        """
        Save data to JSON files
        
        Args:
            filename: Optional custom filename prefix
        """
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        prefix = filename or 'scraped_data'
        
        # Save all data in one JSON file
        all_data = {
            'metadata': {
                'scraped_at': datetime.now().isoformat(),
                'total_linkedin_profiles': len(self.linkedin_data),
                'total_websites_scraped': len(self.website_data),
                'total_combined_entries': len(self.combined_data)
            },
            'linkedin_data': self.linkedin_data,
            'website_data': self.website_data,
            'combined_data': self.combined_data
        }
        
        json_file = os.path.join(self.output_dir, f'{prefix}_{timestamp}.json')
        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump(all_data, f, indent=2, ensure_ascii=False)
        
        logger.info(f"Saved JSON data to: {json_file}")
    
    def save_to_excel(self, filename: str = None):
        """
        Save data to Excel file with multiple sheets
        
        Args:
            filename: Optional custom filename prefix
        """
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        prefix = filename or 'scraped_data'
        
        excel_file = os.path.join(self.output_dir, f'{prefix}_{timestamp}.xlsx')
        
        with pd.ExcelWriter(excel_file, engine='openpyxl') as writer:
            if self.linkedin_data:
                df = pd.DataFrame(self.linkedin_data)
                df.to_excel(writer, sheet_name='LinkedIn Data', index=False)
            
            if self.website_data:
                df = pd.DataFrame(self.website_data)
                df.to_excel(writer, sheet_name='Website Data', index=False)
            
            if self.combined_data:
                df = pd.DataFrame(self.combined_data)
                df.to_excel(writer, sheet_name='Combined Data', index=False)
        
        logger.info(f"Saved Excel data to: {excel_file}")
    
    def save_all(self, filename: str = None):
        """
        Save data in all formats
        
        Args:
            filename: Optional custom filename prefix
        """
        self.combine_data()
        self.save_to_csv(filename)
        self.save_to_json(filename)
        self.save_to_excel(filename)
        
        logger.info(f"Saved all data. Total entries: {len(self.combined_data)}")
    
    def get_stats(self) -> Dict[str, int]:
        """
        Get statistics about collected data
        
        Returns:
            Dictionary with statistics
        """
        return {
            'linkedin_profiles': len(self.linkedin_data),
            'websites_scraped': len(self.website_data),
            'combined_entries': len(self.combined_data),
            'profiles_with_websites': sum(1 for entry in self.combined_data if entry.get('website_email'))
        }
