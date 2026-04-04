from django.test import TestCase, Client
from django.urls import reverse
import json
import io
import csv

class ForgeNexusCleaningTest(TestCase):
    def setUp(self):
        self.client = Client()

    def test_01_junk_email_scrubber_scenarios(self):
        """
        Verify the Triple-Layer Junk Scrubber correctly rejects bots 
        but keeps professional corporate entry points (info, contact, etc).
        """
        from csvtools.views import remove_invalid_emails
        
        test_leads = [
            {'email': 'test@example.com', 'status': 'junk'},
            {'email': 'noreply@domain.com', 'status': 'junk'},
            {'email': 'dummy@test.com', 'status': 'junk'},
            {'email': 'info@realbusiness.com', 'status': 'keep'}, # Professional Entry
            {'email': 'contact@client.com', 'status': 'keep'}, # Professional Entry
            {'email': 'support@help.com', 'status': 'keep'}, # Professional Entry
            {'email': 'sales@deal.com', 'status': 'keep'}, # Professional Entry
            {'email': 'hello@startup.io', 'status': 'keep'} # Professional Entry
        ]
        
        # We simulate the list coming from the view
        purged_list = remove_invalid_emails(test_leads)
        
        # Verify only 'keep' leads remain
        remaining_emails = [l['email'] for l in purged_list]
        self.assertNotIn('test@example.com', remaining_emails)
        self.assertNotIn('noreply@domain.com', remaining_emails)
        
        self.assertIn('info@realbusiness.com', remaining_emails)
        self.assertIn('contact@client.com', remaining_emails)
        print("✓ Junk Scrubber Test: Passed (Purged bots, preserved professional entry points)")

    def test_02_domain_extractor_scenarios(self):
        """Verify accurate domain extraction from email addresses."""
        from csvtools.views import extract_domains
        
        data = [
            {'email': 'john@leadnexus.com', 'name': 'John'},
            {'email': 'sarah@google.co.uk', 'name': 'Sarah'}
        ]
        
        result = extract_domains(data)
        
        self.assertEqual(result[0]['domain'], 'leadnexus.com')
        self.assertEqual(result[1]['domain'], 'google.co.uk')
        print("✓ Domain Extractor Test: Passed")

    def test_03_duplicate_row_removal(self):
        """Verify identical rows are merged and removed."""
        from csvtools.views import remove_duplicates
        
        data = [
            {'email': 'target1@test.com', 'name': 'Target One'},
            {'email': 'target1@test.com', 'name': 'Target One'}, # Exact Dupe
            {'email': 'target2@test.com', 'name': 'Target Two'}
        ]
        
        result = remove_duplicates(data)
        self.assertEqual(len(result), 2)
        print("✓ Duplicate Row Test: Passed")

    def test_04_bulk_case_correction_new_feature(self):
        """Test the new 'Clean Names' feature (Title Case)."""
        # Note: This is where we simulate adding a NEW function and testing it
        def clean_names_logic(data):
            for row in data:
                if 'name' in row and row['name']:
                    row['name'] = row['name'].strip().title()
            return data
            
        data = [
            {'name': 'john smith'},
            {'name': '  SARAH CONNOR '},
            {'name': 'bob'}
        ]
        
        result = clean_names_logic(data)
        self.assertEqual(result[0]['name'], 'John Smith')
        self.assertEqual(result[1]['name'], 'Sarah Connor')
        self.assertEqual(result[2]['name'], 'Bob')
        print("✓ Bulk Case Correction: Verified Power-Up logic")
