from django.db import models

# Create your models here.
from django.conf import settings
from django.utils import timezone
from django.db import transaction
from decimal import Decimal
import uuid
import logging


logger = logging.getLogger(__name__)

class InvestmentPlan(models.Model):
    """
    Investment plans for crypto mining and forex trading
    """
    class PlanType(models.TextChoices):
        STARTER = 'STARTER', 'Starter Package'
        GROWTH = 'GROWTH', 'Growth Package'
        PREMIUM = 'PREMIUM', 'Premium Package'
        CUSTOM = 'CUSTOM', 'Custom Package'
    
    class ReturnPeriod(models.TextChoices):
        WEEKLY = 'WEEKLY', 'Weekly'
        MONTHLY = 'MONTHLY', 'Monthly'
        QUARTERLY = 'QUARTERLY', 'Quarterly'
    
    class InvestmentCategory(models.TextChoices):
        CRYPTO_MINING = 'CRYPTO_MINING', 'Crypto Mining'
        FOREX_TRADING = 'FOREX_TRADING', 'Forex Trading'
        DUAL_STRATEGY = 'DUAL_STRATEGY', 'Dual Strategy (Mining + Forex)'
    
    # Basic Information
    name = models.CharField(max_length=100)
    plan_type = models.CharField(
        max_length=20,
        choices=PlanType.choices,
        default=PlanType.STARTER
    )
    category = models.CharField(
        max_length=20,
        choices=InvestmentCategory.choices,
        default=InvestmentCategory.DUAL_STRATEGY
    )
    description = models.TextField()
    short_description = models.CharField(max_length=255, blank=True)
    
    # Investment Range
    min_amount = models.DecimalField(
        max_digits=20,
        decimal_places=8,
        default=Decimal('50.00'),
        help_text="Minimum investment amount in USD"
    )
    max_amount = models.DecimalField(
        max_digits=20,
        decimal_places=8,
        null=True,
        blank=True,
        help_text="Maximum investment amount in USD (null for unlimited)"
    )
    
    # Returns Configuration
    min_return_multiplier = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('5.00'),
        help_text="Minimum return multiplier (e.g., 5 for 5x)"
    )
    max_return_multiplier = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('10.00'),
        help_text="Maximum return multiplier (e.g., 10 for 10x)"
    )
    return_period = models.CharField(
        max_length=20,
        choices=ReturnPeriod.choices,
        default=ReturnPeriod.WEEKLY
    )
    
    # Duration
    min_duration_days = models.PositiveIntegerField(
        default=7,
        help_text="Minimum recommended duration in days"
    )
    max_duration_days = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Maximum recommended duration in days"
    )
    is_flexible_duration = models.BooleanField(
        default=False,
        help_text="Can users withdraw anytime?"
    )
    
    # Features & Benefits
    features = models.JSONField(
        default=list,
        blank=True,
        help_text="List of features/benefits (JSON array)"
    )
    
    # Risk & Performance
    risk_level = models.CharField(
        max_length=20,
        choices=[
            ('LOW', 'Low Risk'),
            ('MODERATE', 'Moderate Risk'),
            ('HIGH', 'High Risk'),
        ],
        default='MODERATE'
    )
    performance_fee_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="Performance fee percentage"
    )
    
    # Status
    is_active = models.BooleanField(default=True)
    is_featured = models.BooleanField(default=False)
    display_order = models.PositiveIntegerField(default=0)
    
    # Statistics
    total_investors = models.PositiveIntegerField(default=0)
    total_invested = models.DecimalField(
        max_digits=20,
        decimal_places=8,
        default=Decimal('0.00')
    )
    total_profits_paid = models.DecimalField(
        max_digits=20,
        decimal_places=8,
        default=Decimal('0.00')
    )
    success_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="Success rate percentage"
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['display_order', 'created_at']
        verbose_name = 'Investment Plan'
        verbose_name_plural = 'Investment Plans'
    
    def __str__(self):
        return f"{self.name} ({self.get_plan_type_display()})"
    
    def get_estimated_return_range(self, amount=None):
        """
        Get estimated return range for display
        Returns: (min_return, max_return) in USD
        """
        if amount is None:
            amount = self.min_amount
        
        min_return = amount * (self.min_return_multiplier / Decimal('100'))
        max_return = amount * (self.max_return_multiplier / Decimal('100'))
        
        return min_return, max_return
    
    def calculate_daily_return_rate(self):
        """
        Calculate approximate daily return rate based on period
        """
        if self.return_period == 'WEEKLY':
            # Assuming 5-10x per week
            avg_multiplier = (self.min_return_multiplier + self.max_return_multiplier) / 2
            daily_rate = (avg_multiplier / Decimal('100')) / 7
        else:  # MONTHLY
            avg_multiplier = (self.min_return_multiplier + self.max_return_multiplier) / 2
            daily_rate = (avg_multiplier / Decimal('100')) / 30
        
        return daily_rate
    
    def can_invest(self, amount):
        """Check if amount is within plan's range"""
        if amount < self.min_amount:
            return False, f"Minimum investment is ${self.min_amount}"
        
        if self.max_amount and amount > self.max_amount:
            return False, f"Maximum investment is ${self.max_amount}"
        
        return True, ""


class PlanFAQ(models.Model):
    """
    Frequently Asked Questions for investment plans
    """
    plan = models.ForeignKey(
        InvestmentPlan,
        on_delete=models.CASCADE,
        related_name='faqs'
    )
    question = models.CharField(max_length=255)
    answer = models.TextField()
    display_order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['display_order']
        verbose_name = 'Plan FAQ'
        verbose_name_plural = 'Plan FAQs'
    
    def __str__(self):
        return f"FAQ: {self.question[:50]}..."


class PlanPerformance(models.Model):
    """
    Track historical performance of investment plans
    """
    plan = models.ForeignKey(
        InvestmentPlan,
        on_delete=models.CASCADE,
        related_name='performances'
    )
    
    # Performance metrics
    period_start = models.DateField()
    period_end = models.DateField()
    average_return = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text="Average return percentage for the period"
    )
    total_invested = models.DecimalField(
        max_digits=20,
        decimal_places=8
    )
    total_profits = models.DecimalField(
        max_digits=20,
        decimal_places=8
    )
    active_investments = models.PositiveIntegerField()
    completed_investments = models.PositiveIntegerField()
    
    # Market conditions
    market_condition = models.CharField(
        max_length=20,
        choices=[
            ('BULLISH', 'Bullish'),
            ('BEARISH', 'Bearish'),
            ('VOLATILE', 'Volatile'),
            ('STABLE', 'Stable'),
        ],
        default='STABLE'
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-period_start']
        verbose_name = 'Plan Performance'
        verbose_name_plural = 'Plan Performances'
    
    def __str__(self):
        return f"{self.plan.name} Performance: {self.period_start} to {self.period_end}"


class UserInvestment(models.Model):
    """
    Track user investments in plans (separate from wallet app)
    """
    class InvestmentStatus(models.TextChoices):
        PENDING = 'PENDING', 'Pending Approval'
        ACTIVE = 'ACTIVE', 'Active'
        COMPLETED = 'COMPLETED', 'Completed'
        CANCELLED = 'CANCELLED', 'Cancelled'
        SUSPENDED = 'SUSPENDED', 'Suspended'
    
    class WithdrawalStatus(models.TextChoices):
        NOT_REQUESTED = 'NOT_REQUESTED', 'Not Requested'
        REQUESTED = 'REQUESTED', 'Withdrawal Requested'
        PROCESSING = 'PROCESSING', 'Processing'
        COMPLETED = 'COMPLETED', 'Withdrawn'
        DENIED = 'DENIED', 'Withdrawal Denied'
    
    investment_id = models.UUIDField(
        default=uuid.uuid4,
        editable=False,
        unique=True
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='plan_investments'
    )
    plan = models.ForeignKey(
        InvestmentPlan,
        on_delete=models.CASCADE,
        related_name='user_investments'
    )
    
    # Investment details
    principal_amount = models.DecimalField(
        max_digits=20,
        decimal_places=8
    )
    expected_return_multiplier = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True
    )
    expected_total = models.DecimalField(
        max_digits=20,
        decimal_places=8,
        null=True,
        blank=True
    )
    
    # Current values
    current_value = models.DecimalField(
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
    
    # Dates
    start_date = models.DateTimeField()
    end_date = models.DateTimeField(null=True, blank=True)
    last_profit_date = models.DateTimeField(null=True, blank=True)
    next_profit_date = models.DateTimeField(null=True, blank=True)
    
    # Status
    status = models.CharField(
        max_length=20,
        choices=InvestmentStatus.choices,
        default=InvestmentStatus.PENDING
    )
    withdrawal_status = models.CharField(
        max_length=20,
        choices=WithdrawalStatus.choices,
        default=WithdrawalStatus.NOT_REQUESTED
    )
    
    # Flexible withdrawal specific
    early_withdrawal_fee = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="Fee percentage for early withdrawal"
    )
    
    # Referral tracking
    referred_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='referred_investments'
    )
    referral_bonus_paid = models.BooleanField(default=False)
    
    # Metadata
    metadata = models.JSONField(default=dict, blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = 'User Investment'
        verbose_name_plural = 'User Investments'
    
    def __str__(self):
        return f"Investment {self.investment_id} - {self.user.email} - ${self.principal_amount}"
    
    def calculate_current_value(self, as_of_date=None):
        """
        Calculate current value based on elapsed time and plan parameters
        """
        from datetime import timedelta
        
        if as_of_date is None:
            as_of_date = timezone.now()
        
        if self.status != self.InvestmentStatus.ACTIVE:
            return self.current_value
        
        if as_of_date < self.start_date:
            return self.principal_amount
        
        # Calculate elapsed time
        elapsed_days = (as_of_date - self.start_date).days
        
        if self.end_date and as_of_date >= self.end_date:
            # Investment period completed
            elapsed_days = (self.end_date - self.start_date).days
        
        # Calculate based on plan's daily return rate
        daily_rate = self.plan.calculate_daily_return_rate()
        profit = self.principal_amount * daily_rate * Decimal(str(elapsed_days))
        
        # Apply multiplier
        if self.expected_return_multiplier:
            max_profit = self.principal_amount * (self.expected_return_multiplier / Decimal('100'))
            profit = min(profit, max_profit)
        
        current_value = self.principal_amount + profit
        
        # Deduct any withdrawals
        current_value -= self.total_withdrawn
        
        return max(current_value, Decimal('0.00'))
    
    def update_current_value(self):
        """Update and save current value"""
        self.current_value = self.calculate_current_value()
        self.total_profit = self.current_value - self.principal_amount + self.total_withdrawn
        self.save()
        
        # Check if investment should be completed
        if self.end_date and timezone.now() >= self.end_date:
            self.complete_investment()
    
    @classmethod
    @transaction.atomic
    def create_investment(cls, user, plan, amount, request=None):
        """
        Atomic investment creation with wallet debit and ledger entry
        """
        from wallet.models import Wallet
        
        # Get user's wallet
        wallet = Wallet.objects.select_for_update().get(user=user)
        
        # Check balance
        if not wallet.can_invest(amount):
            raise ValueError("Insufficient balance")
        
        # Calculate dates and returns
        start_date = timezone.now()
        end_date = start_date + timezone.timedelta(days=plan.duration_days)
        
        avg_multiplier = (plan.min_return_multiplier + plan.max_return_multiplier) / 2
        expected_total = amount + (amount * (avg_multiplier / Decimal('100')))
        
        # Create investment
        investment = cls.objects.create(
            user=user,
            plan=plan,
            principal_amount=amount,
            expected_return_multiplier=avg_multiplier,
            expected_total=expected_total,
            current_value=amount,
            start_date=start_date,
            end_date=end_date,
            status=cls.InvestmentStatus.ACTIVE,
            metadata={'source': 'web', 'duration_days': plan.duration_days}
        )
        
        # Debit wallet (creates ledger entry automatically)
        wallet.debit(
            amount=amount,
            transaction_type='INVESTMENT',
            reference=str(investment.investment_id),
            description=f"Investment in {plan.name} plan",
            metadata={
                'plan_id': plan.id,
                'plan_name': plan.name,
                'investment_id': str(investment.investment_id)
            },
            request=request
        )
        
        # Update plan statistics
        plan.total_invested += amount
        plan.total_investors = plan.user_investments.filter(
            status__in=['ACTIVE', 'COMPLETED']
        ).count()
        plan.save()
        
        logger.info(f"Investment {investment.investment_id} created atomically")
        return investment
    
    @transaction.atomic
    def complete_investment(self, request=None):
        """
        Atomic investment completion with profit credit and ledger entry
        """
        from wallet.models import Wallet
        
        if self.status != self.InvestmentStatus.ACTIVE:
            raise ValueError(f"Cannot complete investment with status {self.status}")
        
        # Update current value one last time
        self.update_current_value()
        
        # Calculate profit
        profit_amount = self.total_profit
        
        # Update investment status
        self.status = self.InvestmentStatus.COMPLETED
        self.completed_at = timezone.now()
        self.save()
        
        # Credit wallet with profit (creates ledger entry automatically)
        if profit_amount > 0:
            wallet = Wallet.objects.select_for_update().get(user=self.user)
            wallet.credit(
                amount=profit_amount,
                transaction_type='PROFIT',
                reference=str(self.investment_id),
                description=f"Profit from investment in {self.plan.name}",
                metadata={
                    'plan_id': self.plan.id,
                    'plan_name': self.plan.name,
                    'principal_amount': str(self.principal_amount),
                    'profit_amount': str(profit_amount),
                    'investment_id': str(self.investment_id)
                },
                request=request
            )
        
        logger.info(f"Investment {self.investment_id} completed atomically")
        return profit_amount
    
    def request_withdrawal(self, amount):
        """Request withdrawal from investment"""
        from decimal import Decimal
        
        if not self.plan.is_flexible_duration and self.status != self.InvestmentStatus.ACTIVE:
            return False, "Cannot withdraw from non-flexible plan"
        
        if amount > self.current_value:
            return False, "Insufficient balance"
        
        # Calculate fee for early withdrawal
        fee = Decimal('0.00')
        if self.plan.is_flexible_duration and self.early_withdrawal_fee > 0:
            fee = amount * (self.early_withdrawal_fee / Decimal('100'))
        
        withdrawable_amount = amount - fee
        
        self.withdrawal_status = self.WithdrawalStatus.REQUESTED
        self.save()
        
        return True, {
            'amount': amount,
            'fee': fee,
            'net_amount': withdrawable_amount,
            'message': 'Withdrawal request submitted'
        }


class ProfitWithdrawal(models.Model):
    """
    Track profit withdrawals from investments
    """
    class WithdrawalStatus(models.TextChoices):
        PENDING = 'PENDING', 'Pending'
        PROCESSING = 'PROCESSING', 'Processing'
        COMPLETED = 'COMPLETED', 'Completed'
        FAILED = 'FAILED', 'Failed'
        CANCELLED = 'CANCELLED', 'Cancelled'
    
    withdrawal_id = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='profit_withdrawals'
    )
    investment = models.ForeignKey(
        UserInvestment,
        on_delete=models.CASCADE,
        related_name='withdrawals',
        null=True,
        blank=True
    )
    
    amount = models.DecimalField(max_digits=20, decimal_places=8)
    fee = models.DecimalField(max_digits=20, decimal_places=8, default=0.00)
    net_amount = models.DecimalField(max_digits=20, decimal_places=8)
    
    status = models.CharField(
        max_length=20,
        choices=WithdrawalStatus.choices,
        default=WithdrawalStatus.PENDING
    )
    
    # Payment details
    payment_method = models.CharField(
        max_length=50,
        choices=[
            ('WALLET', 'Wallet Balance'),
            ('CRYPTO', 'Cryptocurrency'),
            ('BANK', 'Bank Transfer'),
        ],
        default='WALLET'
    )
    payment_details = models.JSONField(default=dict, blank=True)
    
    # Admin notes
    admin_notes = models.TextField(blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Profit Withdrawal'
        verbose_name_plural = 'Profit Withdrawals'
    
    def __str__(self):
        return f"Withdrawal {self.withdrawal_id} - ${self.amount} - {self.status}"


class InvestmentAlert(models.Model):
    """
    Alerts for investment opportunities or important updates
    """
    class AlertType(models.TextChoices):
        OPPORTUNITY = 'OPPORTUNITY', 'Investment Opportunity'
        MARKET_UPDATE = 'MARKET_UPDATE', 'Market Update'
        PLAN_UPDATE = 'PLAN_UPDATE', 'Plan Update'
        PERFORMANCE = 'PERFORMANCE', 'Performance Report'
        MAINTENANCE = 'MAINTENANCE', 'Maintenance Alert'
    
    class AlertPriority(models.TextChoices):
        LOW = 'LOW', 'Low'
        MEDIUM = 'MEDIUM', 'Medium'
        HIGH = 'HIGH', 'High'
        URGENT = 'URGENT', 'Urgent'
    
    title = models.CharField(max_length=255)
    message = models.TextField()
    alert_type = models.CharField(max_length=20, choices=AlertType.choices)
    priority = models.CharField(max_length=20, choices=AlertPriority.choices, default='MEDIUM')
    
    # Target audience
    target_plans = models.ManyToManyField(
        InvestmentPlan,
        blank=True,
        related_name='alerts'
    )
    target_users = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        blank=True,
        related_name='investment_alerts'
    )
    is_for_all_users = models.BooleanField(default=False)
    
    # Status
    is_active = models.BooleanField(default=True)
    is_read = models.BooleanField(default=False)
    
    # Timestamps
    valid_from = models.DateTimeField(default=timezone.now)
    valid_until = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Investment Alert'
        verbose_name_plural = 'Investment Alerts'
    
    def __str__(self):
        return f"{self.get_alert_type_display()}: {self.title}"