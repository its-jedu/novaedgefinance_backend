from django.db import models

# Create your models here.
from django.conf import settings
from django.utils import timezone
from decimal import Decimal
import uuid

class Wallet(models.Model):
    """
    User's wallet to track balance and financial activities
    """
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='wallet'
    )
    balance_usd = models.DecimalField(
        max_digits=20,
        decimal_places=8,
        default=0.00
    )
    total_deposited = models.DecimalField(
        max_digits=20,
        decimal_places=8,
        default=0.00
    )
    total_invested = models.DecimalField(
        max_digits=20,
        decimal_places=8,
        default=0.00
    )
    total_profit = models.DecimalField(
        max_digits=20,
        decimal_places=8,
        default=0.00
    )
    total_withdrawn = models.DecimalField(
        max_digits=20,
        decimal_places=8,
        default=0.00
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'Wallet'
        verbose_name_plural = 'Wallets'
    
    def __str__(self):
        return f"Wallet for {self.user.email} - ${self.balance_usd}"
    
    def can_invest(self, amount):
        """Check if user has sufficient balance for investment"""
        return self.balance_usd >= Decimal(str(amount))
    
    def credit(self, amount, transaction_type='DEPOSIT'):
        """Credit amount to wallet"""
        self.balance_usd += Decimal(str(amount))
        
        if transaction_type == 'DEPOSIT':
            self.total_deposited += Decimal(str(amount))
        elif transaction_type == 'PROFIT':
            self.total_profit += Decimal(str(amount))
        
        self.save()
    
    def debit(self, amount, transaction_type='INVESTMENT'):
        """Debit amount from wallet"""
        if not self.can_invest(amount):
            raise ValueError("Insufficient balance")
        
        self.balance_usd -= Decimal(str(amount))
        
        if transaction_type == 'INVESTMENT':
            self.total_invested += Decimal(str(amount))
        elif transaction_type == 'WITHDRAWAL':
            self.total_withdrawn += Decimal(str(amount))
        
        self.save()


class Transaction(models.Model):
    """
    Track all wallet movements
    """
    class TransactionType(models.TextChoices):
        DEPOSIT = 'DEPOSIT', 'Deposit'
        INVESTMENT = 'INVESTMENT', 'Investment'
        PROFIT = 'PROFIT', 'Profit'
        WITHDRAWAL = 'WITHDRAWAL', 'Withdrawal'
        REFUND = 'REFUND', 'Refund'
    
    class TransactionStatus(models.TextChoices):
        PENDING = 'PENDING', 'Pending'
        COMPLETED = 'COMPLETED', 'Completed'
        FAILED = 'FAILED', 'Failed'
        CANCELLED = 'CANCELLED', 'Cancelled'
    
    transaction_id = models.UUIDField(
        default=uuid.uuid4,
        editable=False,
        unique=True
    )
    wallet = models.ForeignKey(
        Wallet,
        on_delete=models.CASCADE,
        related_name='transactions'
    )
    transaction_type = models.CharField(
        max_length=20,
        choices=TransactionType.choices
    )
    amount = models.DecimalField(
        max_digits=20,
        decimal_places=8
    )
    status = models.CharField(
        max_length=20,
        choices=TransactionStatus.choices,
        default=TransactionStatus.PENDING
    )
    description = models.TextField(null=True, blank=True)
    reference = models.CharField(max_length=255, null=True, blank=True)
    
    # Metadata
    metadata = models.JSONField(default=dict, blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Transaction'
        verbose_name_plural = 'Transactions'
    
    def __str__(self):
        return f"{self.transaction_type} - ${self.amount} - {self.status}"


class Deposit(models.Model):
    """
    NOWPayments-based deposits
    """
    class PaymentStatus(models.TextChoices):
        WAITING = 'WAITING', 'Waiting'
        CONFIRMING = 'CONFIRMING', 'Confirming'
        CONFIRMED = 'CONFIRMED', 'Confirmed'
        SENDING = 'SENDING', 'Sending'
        PARTIALLY_PAID = 'PARTIALLY_PAID', 'Partially Paid'
        FINISHED = 'FINISHED', 'Finished'
        FAILED = 'FAILED', 'Failed'
        REFUNDED = 'REFUNDED', 'Refunded'
        EXPIRED = 'EXPIRED', 'Expired'
    
    deposit_id = models.UUIDField(
        default=uuid.uuid4,
        editable=False,
        unique=True
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='deposits'
    )
    
    # NOWPayments fields
    payment_id = models.CharField(max_length=255, unique=True)
    invoice_id = models.CharField(max_length=255, null=True, blank=True)
    pay_address = models.CharField(max_length=255, null=True, blank=True)
    
    # Payment details
    pay_currency = models.CharField(max_length=10)  # BTC, ETH, USDT, etc.
    pay_amount = models.DecimalField(max_digits=20, decimal_places=8)
    usd_amount = models.DecimalField(max_digits=20, decimal_places=8)
    
    # Exchange rate at time of payment
    exchange_rate = models.DecimalField(
        max_digits=20,
        decimal_places=8,
        null=True,
        blank=True
    )
    
    # Status
    status = models.CharField(
        max_length=20,
        choices=PaymentStatus.choices,
        default=PaymentStatus.WAITING
    )
    
    # NOWPayments response data
    payment_details = models.JSONField(default=dict, blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    confirmed_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Deposit'
        verbose_name_plural = 'Deposits'
    
    def __str__(self):
        return f"Deposit {self.deposit_id} - {self.user.email} - ${self.usd_amount}"
    
    def process_confirmation(self):
        """Process confirmed payment and credit user's wallet"""
        from django.db import transaction
        
        if self.status != self.PaymentStatus.CONFIRMED:
            return
        
        with transaction.atomic():
            # Update deposit status
            self.confirmed_at = timezone.now()
            self.save()
            
            # Get or create user's wallet
            wallet, created = Wallet.objects.get_or_create(user=self.user)
            
            # Credit amount to wallet
            wallet.credit(self.usd_amount, transaction_type='DEPOSIT')
            
            # Record transaction
            Transaction.objects.create(
                wallet=wallet,
                transaction_type=Transaction.TransactionType.DEPOSIT,
                amount=self.usd_amount,
                status=Transaction.TransactionStatus.COMPLETED,
                description=f"Deposit via {self.pay_currency} - NOWPayments ID: {self.payment_id}",
                reference=str(self.payment_id),
                metadata={
                    'currency': self.pay_currency,
                    'pay_amount': str(self.pay_amount),
                    'exchange_rate': str(self.exchange_rate) if self.exchange_rate else None
                }
            )