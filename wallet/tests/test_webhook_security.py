import json
import hmac
import hashlib
from decimal import Decimal
from django.test import TestCase
from django.urls import reverse
from django.conf import settings
from django.utils import timezone
from rest_framework.test import APITestCase
from unittest.mock import patch, MagicMock

from wallet.models import Deposit, WebhookLog
from authentication.models import User

class WebhookSecurityTests(APITestCase):
    """Test webhook security, signature verification, and idempotency"""
    
    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create_user(
            email='test@example.com',
            phone_number='+1234567890',
            first_name='Test',
            last_name='User',
            country='USA',
            password='TestPass123!',
            is_verified=True,
            email_verified=True,
            profile_completed=True
        )
        
        self.webhook_url = reverse('nowpayments-webhook')
        
        # Sample webhook payload
        self.payload = {
            'payment_id': 'test_payment_123',
            'payment_status': 'confirmed',
            'pay_amount': '0.001',
            'pay_currency': 'BTC',
            'price_amount': '100.00',
            'price_currency': 'usd',
            'user_id': self.user.id
        }
        
        self.raw_payload = json.dumps(self.payload).encode('utf-8')
        
        # Set IPN secret for testing
        settings.NOWPAYMENTS_IPN_SECRET = 'test_secret_key'
    
    def generate_signature(self, payload):
        """Generate valid signature for testing"""
        return hmac.new(
            settings.NOWPAYMENTS_IPN_SECRET.encode('utf-8'),
            payload,
            hashlib.sha512
        ).hexdigest()
    
    def test_valid_signature_accepts_webhook(self):
        """Test webhook with valid signature is accepted"""
        signature = self.generate_signature(self.raw_payload)
        
        response = self.client.post(
            self.webhook_url,
            data=self.payload,
            format='json',
            HTTP_X_NOWPAYMENTS_SIG=signature
        )
        
        self.assertEqual(response.status_code, 200)
        
        # Verify webhook log created
        webhook_log = WebhookLog.objects.filter(
            payment_id=self.payload['payment_id']
        ).first()
        
        self.assertIsNotNone(webhook_log)
        self.assertTrue(webhook_log.signature_valid)
    
    def test_invalid_signature_rejects_webhook(self):
        """Test webhook with invalid signature is rejected"""
        invalid_signature = 'invalid_signature_123'
        
        response = self.client.post(
            self.webhook_url,
            data=self.payload,
            format='json',
            HTTP_X_NOWPAYMENTS_SIG=invalid_signature
        )
        
        self.assertEqual(response.status_code, 401)
        
        # Verify webhook log created with invalid signature
        webhook_log = WebhookLog.objects.filter(
            payment_id=self.payload['payment_id']
        ).first()
        
        self.assertIsNotNone(webhook_log)
        self.assertFalse(webhook_log.signature_valid)
    
    def test_missing_signature_rejects_webhook(self):
        """Test webhook without signature is rejected"""
        response = self.client.post(
            self.webhook_url,
            data=self.payload,
            format='json'
        )
        
        self.assertEqual(response.status_code, 401)
    
    def test_idempotency_prevents_duplicate_processing(self):
        """Test duplicate webhooks are ignored"""
        # First webhook
        signature = self.generate_signature(self.raw_payload)
        
        response1 = self.client.post(
            self.webhook_url,
            data=self.payload,
            format='json',
            HTTP_X_NOWPAYMENTS_SIG=signature
        )
        
        self.assertEqual(response1.status_code, 200)
        
        # Duplicate webhook
        response2 = self.client.post(
            self.webhook_url,
            data=self.payload,
            format='json',
            HTTP_X_NOWPAYMENTS_SIG=signature
        )
        
        self.assertEqual(response2.status_code, 200)
        self.assertEqual(response2.data['status'], 'ignored')
        
        # Verify only one deposit created
        deposits = Deposit.objects.filter(payment_id=self.payload['payment_id'])
        self.assertEqual(deposits.count(), 1)
    
    def test_missing_payment_id_rejects_webhook(self):
        """Test webhook without payment_id is rejected"""
        invalid_payload = {'status': 'confirmed'}
        
        response = self.client.post(
            self.webhook_url,
            data=invalid_payload,
            format='json'
        )
        
        self.assertEqual(response.status_code, 400)
    
    def test_webhook_log_stores_raw_payload(self):
        """Test webhook log stores raw payload for audit"""
        signature = self.generate_signature(self.raw_payload)
        
        self.client.post(
            self.webhook_url,
            data=self.payload,
            format='json',
            HTTP_X_NOWPAYMENTS_SIG=signature
        )
        
        webhook_log = WebhookLog.objects.get(
            payment_id=self.payload['payment_id']
        )
        
        self.assertEqual(webhook_log.raw_payload['payment_id'], self.payload['payment_id'])
        self.assertEqual(webhook_log.signature, signature)

