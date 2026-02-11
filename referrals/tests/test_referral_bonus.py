from decimal import Decimal
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APITestCase

from authentication.models import User
from wallet.models import Wallet, Deposit
from referrals.models import Referral, BonusWallet, ReferralBonusSettings
from referrals.utils import process_referral_on_deposit

class ReferralBonusTests(APITestCase):
    """Test referral bonus system"""
    
    def setUp(self):
        """Set up test data"""
        # Referrer
        self.referrer = User.objects.create_user(
            email='referrer@example.com',
            phone_number='+1111111111',
            first_name='Referrer',
            last_name='User',
            country='USA',
            password='TestPass123!'
        )
        
        # Referred user
        self.referred = User.objects.create_user(
            email='referred@example.com',
            phone_number='+1222222222',
            first_name='Referred',
            last_name='User',
            country='USA',
            password='TestPass123!',
            referred_by=self.referrer
        )
        
        # Create referral relationship
        self.referral = Referral.objects.create(
            referrer=self.referrer,
            referred_user=self.referred,
            referral_code='TEST123',
            bonus_amount=Decimal('5.00'),
            status=Referral.ReferralStatus.PENDING
        )
        
        # Create wallets
        self.referrer_wallet = Wallet.objects.create(
            user=self.referrer,
            balance_usd=Decimal('0.00')
        )
        
        self.referred_wallet = Wallet.objects.create(
            user=self.referred,
            balance_usd=Decimal('100.00')
        )
        
        # Get settings
        self.settings = ReferralBonusSettings.get_settings()
        self.settings.default_bonus_amount = Decimal('5.00')
        self.settings.minimum_deposit_for_bonus = Decimal('10.00')
        self.settings.save()
    
    def test_referral_bonus_triggers_on_deposit(self):
        """Test referral bonus is credited when referred user makes deposit"""
        
        # Process referral bonus
        result = process_referral_on_deposit(
            referred_user=self.referred,
            deposit_amount=Decimal('100.00')
        )
        
        self.assertTrue(result)
        
        # Check referral status updated
        self.referral.refresh_from_db()
        self.assertEqual(self.referral.status, Referral.ReferralStatus.EARNED)
        self.assertTrue(self.referral.referred_user_deposited)
        
        # Check bonus wallet created and credited
        bonus_wallet = BonusWallet.objects.get(user=self.referrer)
        self.assertEqual(bonus_wallet.balance, Decimal('5.00'))
        self.assertEqual(bonus_wallet.total_earned, Decimal('5.00'))
    
    def test_referral_bonus_not_credited_for_small_deposit(self):
        """Test referral bonus is not credited for deposits below minimum"""
        
        # Process small deposit
        result = process_referral_on_deposit(
            referred_user=self.referred,
            deposit_amount=Decimal('5.00')  # Below minimum
        )
        
        self.assertFalse(result)
        
        # Check referral status unchanged
        self.referral.refresh_from_db()
        self.assertEqual(self.referral.status, Referral.ReferralStatus.PENDING)
        
        # Check bonus wallet not created
        self.assertFalse(
            BonusWallet.objects.filter(user=self.referrer).exists()
        )
    
    def test_prevent_multiple_bonuses_same_referral(self):
        """Test referral bonus is only credited once per referral"""
        
        # First deposit
        process_referral_on_deposit(
            referred_user=self.referred,
            deposit_amount=Decimal('100.00')
        )
        
        # Second deposit
        result = process_referral_on_deposit(
            referred_user=self.referred,
            deposit_amount=Decimal('200.00')
        )
        
        # Should return False (already processed)
        self.assertFalse(result)
        
        # Verify only one bonus credited
        bonus_wallet = BonusWallet.objects.get(user=self.referrer)
        self.assertEqual(bonus_wallet.balance, Decimal('5.00'))
        self.assertEqual(bonus_wallet.total_earned, Decimal('5.00'))
    
    def test_referral_bonus_withdrawal(self):
        """Test bonus withdrawal to main wallet"""
        
        # Credit bonus
        bonus_wallet = BonusWallet.objects.create(
            user=self.referrer,
            balance=Decimal('25.00'),
            total_earned=Decimal('25.00')
        )
        
        # Withdraw bonus
        from referrals.views import WithdrawBonusView
        view = WithdrawBonusView()
        
        # Simulate withdrawal
        initial_wallet_balance = self.referrer_wallet.balance_usd
        amount = Decimal('10.00')
        
        # This would be called via API, but we'll test the logic
        with self.settings(BONUS_WITHDRAWAL_ENABLED=True):
            # Manual withdrawal for testing
            bonus_wallet.debit(amount)
            self.referrer_wallet.credit(amount, transaction_type='REFERRAL_BONUS')
        
        # Check balances
        bonus_wallet.refresh_from_db()
        self.assertEqual(bonus_wallet.balance, Decimal('15.00'))
        self.assertEqual(bonus_wallet.total_withdrawn, Decimal('10.00'))
        
        self.referrer_wallet.refresh_from_db()
        self.assertEqual(
            self.referrer_wallet.balance_usd,
            initial_wallet_balance + amount
        )

