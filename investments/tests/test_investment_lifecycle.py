from decimal import Decimal
from django.test import TestCase
from django.utils import timezone
from datetime import timedelta
from rest_framework.test import APITestCase
from unittest.mock import patch

from authentication.models import User
from wallet.models import Wallet
from investments.models import InvestmentPlan, UserInvestment
from reporting.models import LedgerEntry

class InvestmentLifecycleTests(APITestCase):
    """Test complete investment lifecycle including compounding and payout"""
    
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
        
        self.wallet = Wallet.objects.create(
            user=self.user,
            balance_usd=Decimal('1000.00')
        )
        
        self.plan = InvestmentPlan.objects.create(
            name='Test Plan',
            description='Test investment plan',
            min_amount=Decimal('100.00'),
            max_amount=Decimal('500.00'),
            duration_days=7,
            daily_return_rate=Decimal('1.0'),
            total_return_percentage=Decimal('7.0'),
            is_active=True
        )
    
    def test_complete_investment_lifecycle(self):
        """Test complete investment lifecycle from start to completion"""
        
        # 1. START INVESTMENT
        investment = UserInvestment.create_investment(
            user=self.user,
            plan=self.plan,
            amount=Decimal('200.00')
        )
        
        # Verify wallet debited
        self.wallet.refresh_from_db()
        self.assertEqual(self.wallet.balance_usd, Decimal('800.00'))
        
        # Verify ledger entry created
        ledger_entry = LedgerEntry.objects.filter(
            user=self.user,
            transaction_type='INVESTMENT'
        ).first()
        
        self.assertIsNotNone(ledger_entry)
        self.assertEqual(ledger_entry.amount, Decimal('-200.00'))
        
        # 2. SIMULATE TIME PROGRESSION
        # Day 1 - calculate value
        day1_value = investment.calculate_current_value()
        self.assertGreater(day1_value, Decimal('200.00'))
        
        # Day 3 - calculate value
        with patch('django.utils.timezone.now') as mock_now:
            mock_now.return_value = investment.start_date + timedelta(days=3)
            day3_value = investment.calculate_current_value()
            
        self.assertGreater(day3_value, day1_value)
        
        # Day 7 - investment completion
        with patch('django.utils.timezone.now') as mock_now:
            mock_now.return_value = investment.start_date + timedelta(days=7)
            
            # Update current value
            investment.update_current_value()
            
            # Complete investment
            profit = investment.complete_investment()
        
        # Verify profit calculated correctly
        expected_profit = Decimal('14.00')  # 7% of $200
        self.assertAlmostEqual(profit, expected_profit, places=2)
        
        # Verify wallet credited
        self.wallet.refresh_from_db()
        self.assertEqual(
            self.wallet.balance_usd,
            Decimal('814.00')  # 800 + 14
        )
        
        # Verify profit ledger entry
        profit_entry = LedgerEntry.objects.filter(
            user=self.user,
            transaction_type='PROFIT'
        ).first()
        
        self.assertIsNotNone(profit_entry)
        self.assertEqual(profit_entry.amount, expected_profit)
        
        # Verify investment status
        investment.refresh_from_db()
        self.assertEqual(investment.status, investment.InvestmentStatus.COMPLETED)
        self.assertIsNotNone(investment.completed_at)
    
    def test_insufficient_balance_prevents_investment(self):
        """Test investment cannot be started with insufficient balance"""
        with self.assertRaises(ValueError):
            UserInvestment.create_investment(
                user=self.user,
                plan=self.plan,
                amount=Decimal('2000.00')  # More than wallet balance
            )
    
    def test_investment_compounding_works_correctly(self):
        """Test investment value compounds correctly over time"""
        investment = UserInvestment.create_investment(
            user=self.user,
            plan=self.plan,
            amount=Decimal('100.00')
        )
        
        # Day 1
        with patch('django.utils.timezone.now') as mock_now:
            mock_now.return_value = investment.start_date + timedelta(days=1)
            day1_value = investment.calculate_current_value()
        
        # Day 2 - should be higher than day 1
        with patch('django.utils.timezone.now') as mock_now:
            mock_now.return_value = investment.start_date + timedelta(days=2)
            day2_value = investment.calculate_current_value()
        
        self.assertGreater(day2_value, day1_value)
        
        # Day 7 - should be at maximum
        with patch('django.utils.timezone.now') as mock_now:
            mock_now.return_value = investment.start_date + timedelta(days=7)
            day7_value = investment.calculate_current_value()
            max_value = investment.principal_amount + self.plan.calculate_profit(
                investment.principal_amount, 
                self.plan.duration_days
            )
        
        self.assertEqual(day7_value, max_value)

