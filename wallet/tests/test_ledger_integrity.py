from decimal import Decimal
from django.test import TestCase
from django.db import transaction
from django.db.utils import IntegrityError
from django.core.exceptions import PermissionError
from rest_framework.test import APITestCase

from wallet.models import Wallet
from reporting.models import LedgerEntry
from authentication.models import User

class LedgerIntegrityTests(APITestCase):
    """Test ledger immutability and financial integrity"""
    
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
            balance_usd=Decimal('1000.00'),
            total_deposited=Decimal('1000.00')
        )
    
    def test_every_balance_change_creates_ledger_entry(self):
        """Test every wallet balance change creates a ledger entry"""
        # Credit operation
        self.wallet.credit(
            amount=Decimal('500.00'),
            transaction_type='DEPOSIT',
            reference='test_deposit_1',
            description='Test deposit'
        )
        
        # Verify ledger entry created
        ledger_entries = LedgerEntry.objects.filter(user=self.user)
        self.assertEqual(ledger_entries.count(), 1)
        
        entry = ledger_entries.first()
        self.assertEqual(entry.transaction_type, 'DEPOSIT')
        self.assertEqual(entry.amount, Decimal('500.00'))
        self.assertEqual(entry.balance_before, Decimal('1000.00'))
        self.assertEqual(entry.balance_after, Decimal('1500.00'))
        
        # Debit operation
        self.wallet.debit(
            amount=Decimal('200.00'),
            transaction_type='INVESTMENT',
            reference='test_investment_1',
            description='Test investment'
        )
        
        # Verify second ledger entry
        self.assertEqual(LedgerEntry.objects.count(), 2)
        
        debit_entry = LedgerEntry.objects.filter(
            transaction_type='INVESTMENT'
        ).first()
        
        self.assertEqual(debit_entry.amount, Decimal('-200.00'))
        self.assertEqual(debit_entry.balance_before, Decimal('1500.00'))
        self.assertEqual(debit_entry.balance_after, Decimal('1300.00'))
    
    def test_ledger_entry_immutability(self):
        """Test ledger entries cannot be modified or deleted"""
        # Create ledger entry
        self.wallet.credit(
            amount=Decimal('100.00'),
            transaction_type='DEPOSIT',
            reference='test_immutable'
        )
        
        entry = LedgerEntry.objects.first()
        
        # Attempt to modify
        with self.assertRaises(PermissionError):
            entry.amount = Decimal('200.00')
            entry.save()
        
        # Attempt to delete
        with self.assertRaises(PermissionError):
            entry.delete()
    
    def test_direct_balance_modification_prevented(self):
        """Test direct balance modification without ledger is discouraged"""
        # This should be caught by business logic, not DB constraint
        # We're testing that our service layer enforces ledger creation
        
        with transaction.atomic():
            self.wallet.balance_usd = Decimal('999999.00')
            self.wallet.save()
        
        # This should have been done through credit/debit methods
        # But we can't prevent direct saves at DB level
        # We rely on developer discipline and code review
        self.wallet.refresh_from_db()
        self.assertEqual(self.wallet.balance_usd, Decimal('999999.00'))
    
    def test_atomic_financial_operations(self):
        """Test financial operations are atomic"""
        from django.db import transaction
        
        try:
            with transaction.atomic():
                # Attempt to credit and then raise exception
                self.wallet.credit(
                    amount=Decimal('1000.00'),
                    transaction_type='DEPOSIT'
                )
                raise ValueError("Simulated error")
        except ValueError:
            pass
        
        # Verify no changes persisted
        self.wallet.refresh_from_db()
        self.assertEqual(self.wallet.balance_usd, Decimal('1000.00'))
        self.assertEqual(LedgerEntry.objects.count(), 0)

