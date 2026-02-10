from django.db import models

# Create your models here.
from django.conf import settings
from django.utils import timezone
from django.utils.crypto import get_random_string
from decimal import Decimal
import uuid

class Referral(models.Model):
    """
    Track referrals between users
    """
    class ReferralStatus(models.TextChoices):
        PENDING = 'PENDING', 'Pending'
        EARNED = 'EARNED', 'Earned'
        CANCELLED = 'CANCELLED', 'Cancelled'
    
    referral_id = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    referrer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='referrals_made'
    )
    referred_user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='referred_by'
    )
    
    referral_code = models.CharField(max_length=20, db_index=True)
    
    bonus_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('5.00')
    )
    status = models.CharField(
        max_length=20,
        choices=ReferralStatus.choices,
        default=ReferralStatus.PENDING
    )
    
    # Trigger conditions
    referred_user_deposited = models.BooleanField(default=False)
    referred_user_deposit_amount = models.DecimalField(
        max_digits=20,
        decimal_places=8,
        default=Decimal('0.00')
    )
    
    # Bonus payment tracking
    bonus_paid = models.BooleanField(default=False)
    bonus_paid_at = models.DateTimeField(null=True, blank=True)
    bonus_transaction_id = models.CharField(max_length=100, blank=True)
    
    # Metadata
    metadata = models.JSONField(default=dict, blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Referral'
        verbose_name_plural = 'Referrals'
        unique_together = ['referrer', 'referred_user']
    
    def __str__(self):
        return f"Referral: {self.referrer.email} → {self.referred_user.email}"
    
    def mark_as_earned(self):
        """Mark referral as earned when conditions are met"""
        self.status = self.ReferralStatus.EARNED
        self.save()


class BonusWallet(models.Model):
    """
    Separate wallet for referral bonuses
    """
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='bonus_wallet'
    )
    balance = models.DecimalField(
        max_digits=20,
        decimal_places=8,
        default=Decimal('0.00')
    )
    total_earned = models.DecimalField(
        max_digits=20,
        decimal_places=8,
        default=Decimal('0.00')
    )
    total_withdrawn = models.DecimalField(
        max_digits=20,
        decimal_places=8,
        default=Decimal('0.00')
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'Bonus Wallet'
        verbose_name_plural = 'Bonus Wallets'
    
    def __str__(self):
        return f"Bonus Wallet: {self.user.email} - ${self.balance}"
    
    def credit(self, amount, referral=None):
        """Credit bonus amount to wallet"""
        self.balance += Decimal(str(amount))
        self.total_earned += Decimal(str(amount))
        self.save()
        
        # Update referral if provided
        if referral:
            referral.bonus_paid = True
            referral.bonus_paid_at = timezone.now()
            referral.save()
    
    def debit(self, amount):
        """Debit amount from bonus wallet"""
        if self.balance < amount:
            raise ValueError("Insufficient bonus balance")
        
        self.balance -= Decimal(str(amount))
        self.total_withdrawn += Decimal(str(amount))
        self.save()


class UserReferralCode(models.Model):
    """
    User's referral codes
    """
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='referral_code'
    )
    
    # Primary referral code (auto-generated)
    code = models.CharField(max_length=20, unique=True, db_index=True)
    
    # Custom referral code (user can set)
    custom_code = models.CharField(max_length=20, blank=True, null=True, unique=True)
    
    # Statistics
    total_referrals = models.PositiveIntegerField(default=0)
    active_referrals = models.PositiveIntegerField(default=0)
    total_bonus_earned = models.DecimalField(
        max_digits=20,
        decimal_places=8,
        default=Decimal('0.00')
    )
    
    # Settings
    is_active = models.BooleanField(default=True)
    auto_generate = models.BooleanField(default=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'User Referral Code'
        verbose_name_plural = 'User Referral Codes'
    
    def __str__(self):
        return f"Referral Code: {self.get_display_code()} - {self.user.email}"
    
    def get_display_code(self):
        """Get display code (custom if set, otherwise auto-generated)"""
        return self.custom_code if self.custom_code else self.code
    
    def generate_code(self):
        """Generate a unique referral code"""
        import random
        import string
        
        # Generate 8-character alphanumeric code
        code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
        
        # Ensure uniqueness
        while UserReferralCode.objects.filter(code=code).exists():
            code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
        
        self.code = code
        return code


class ReferralBonusSettings(models.Model):
    """
    System-wide referral bonus settings
    """
    # Bonus amounts
    default_bonus_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('5.00'),
        help_text="Default bonus amount in USD"
    )
    minimum_deposit_for_bonus = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('10.00'),
        help_text="Minimum deposit amount to qualify for referral bonus"
    )
    
    # Tiered bonuses
    enable_tiered_bonuses = models.BooleanField(default=False)
    tiered_bonus_settings = models.JSONField(
        default=dict,
        blank=True,
        help_text="Tiered bonus structure (e.g., {'tier1': {'min_referrals': 5, 'bonus': 7.50}})"
    )
    
    # Limits
    max_referrals_per_user = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Maximum number of referrals per user (null for unlimited)"
    )
    max_bonus_per_user = models.DecimalField(
        max_digits=20,
        decimal_places=8,
        null=True,
        blank=True,
        help_text="Maximum total bonus a user can earn (null for unlimited)"
    )
    
    # Bonus withdrawal settings
    bonus_withdrawal_enabled = models.BooleanField(default=True)
    minimum_withdrawal_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('5.00')
    )
    withdrawal_fee_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('0.00')
    )
    
    # Status
    is_active = models.BooleanField(default=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'Referral Bonus Settings'
        verbose_name_plural = 'Referral Bonus Settings'
    
    def __str__(self):
        return f"Referral Bonus Settings"
    
    @classmethod
    def get_settings(cls):
        """Get or create settings"""
        settings, created = cls.objects.get_or_create(pk=1)
        return settings