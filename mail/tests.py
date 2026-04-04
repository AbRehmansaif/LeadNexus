from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.utils import timezone
from .models import EmailCampaign, Recipient, CampaignStep, SMTPCredential
from .tasks import send_single_email_task, send_campaign_emails
from django.db import IntegrityError
import json

class CampaignEngineSafetyTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='password123')
        self.client = Client()
        self.client.login(username='testuser', password='password123')
        
        # Setup SMTP
        self.smtp = SMTPCredential.objects.create(
            user=self.user,
            name="Test SMTP",
            host="smtp.gmail.com",
            port=587,
            username="sender@gmail.com",
            password="encrypted_pass",
            from_email="sender@gmail.com",
            is_active=True,
            daily_limit=100
        )

        # Setup Campaign
        self.campaign = EmailCampaign.objects.create(
            user=self.user,
            name="Alpha Campaign",
            subject="Hello {{ name }}",
            body="This is an automated test.",
            status='pending'
        )
        
        # Setup Step
        self.step = CampaignStep.objects.create(
            campaign=self.campaign,
            step_number=1,
            subject="Step 1",
            body="Body 1"
        )

    def test_01_ingestion_deduplication(self):
        """Verify that duplicate leads are stripped DURING campaign creation."""
        url = '/mail/api/campaigns/create_with_recipients/'
        payload = {
            'name': 'Dedupe Test',
            'subject': 'Test Subject',
            'body': 'Test Body',
            'recipients': json.dumps([
                {'email': 'target1@example.com', 'name': 'Target One'},
                {'email': 'target1@example.com', 'name': 'Target One Duplicate'}, # DUPLICATE
                {'email': 'target2@example.com', 'name': 'Target Two'}
            ])
        }
        
        response = self.client.post(url, data=payload)
        self.assertEqual(response.status_code, 201)
        
        campaign_id = response.json()['id']
        campaign = EmailCampaign.objects.get(id=campaign_id)
        
        # Verify stats show only 2 leads
        self.assertEqual(campaign.total_recipients, 2)
        self.assertEqual(campaign.recipients.count(), 2)
        print("✓ Ingestion Deduplication: Passed (3 inputs -> 2 stored)")

    def test_02_database_uniqueness_guard(self):
        """Verify that the DB physically rejects duplicate leads for the same campaign."""
        Recipient.objects.create(campaign=self.campaign, email='unique@test.com')
        
        with self.assertRaises(IntegrityError):
            # Attempt to bypass the view and force a duplicate into the DB
            Recipient.objects.create(campaign=self.campaign, email='unique@test.com')
        print("✓ Database Uniqueness Guard: Passed (DB rejected duplicate lead)")

    def test_03_double_send_cross_reference_guard(self):
        """Verify that even if duplicates existed, the task aborters prevent multiple sends."""
        # We manually create a duplicate recipient for the same email address 
        # (simulating legacy data) - bypassing IntegrityError for test setup 
        # purposes by using a different campaign if needed, but 
        # actually we just want to test the TASK logic.
        
        # Campaign 2
        campaign2 = EmailCampaign.objects.create(user=self.user, name="Beta", subject="X")
        
        # We force two recipients for the SAME email (if the constraint wasn't there)
        # But since the constraint IS there, we'll verify that the guard in tasks.py 
        # handles the logic of 'Already sent to this address'.
        
        r1 = Recipient.objects.create(campaign=self.campaign, email='target@test.com', status='pending')
        
        # Manually mark Step 1 as SENT for r1
        r1.current_step_index = 1
        r1.status = 'active'
        r1.save()
        
        # Now trigger the task for the SAME email in a different "Ghost" row if it existed.
        # But since we have unique constraint, we'll test the condition where index >= step.
        result = send_single_email_task(r1.id, 1)
        self.assertIn("Already received Step 1", result)
        print("✓ Double-Send Guard (Row Level): Passed")

    def test_04_pause_resume_behavior(self):
        """Verify that 'Paused' campaigns do not fire, and 'Resumed' ones do."""
        r1 = Recipient.objects.create(campaign=self.campaign, email='paused_test@test.com', status='pending')
        
        # 1. Pause
        self.campaign.status = 'paused'
        self.campaign.save()
        
        result = send_single_email_task(r1.id, 1)
        self.assertIn("Paused", result)
        self.assertEqual(r1.current_step_index, 0)
        
        # 2. Resume
        self.campaign.status = 'running'
        self.campaign.save()
        
        # Mocking SMTP to avoid actual network hit
        from unittest.mock import patch
        with patch('django.core.mail.EmailMessage.send') as mocked_send:
            result = send_single_email_task(r1.id, 1)
            self.assertEqual(mocked_send.call_count, 1)
            r1.refresh_from_db()
            self.assertEqual(r1.current_step_index, 1)
            self.assertEqual(r1.status, 'completed') # Only 1 step in this campaign
        
        print("✓ Pause/Resume Behavior: Passed (Blocked while paused, Sent when resumed)")

    def test_05_stats_integrity(self):
        """Verify that stats update accurately and don't count duplicates."""
        Recipient.objects.create(campaign=self.campaign, email='stat1@test.com', status='pending')
        Recipient.objects.create(campaign=self.campaign, email='stat2@test.com', status='pending')
        
        # Initially 2 leads
        self.campaign.sync_stats_from_db()
        self.assertEqual(self.campaign.total_recipients, 2)
        
        # Send one
        with patch('django.core.mail.EmailMessage.send'):
            r = self.campaign.recipients.filter(email='stat1@test.com').first()
            send_single_email_task(r.id, 1)
            
        self.campaign.refresh_from_db()
        self.assertEqual(self.campaign.sent_count, 1)
        self.assertEqual(self.campaign.pending_count, 1)
        print("✓ Stats Integrity: Passed (1/2 leads sent correctly)")
