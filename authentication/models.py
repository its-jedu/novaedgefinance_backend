from django.db import models
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.utils import timezone

class UserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError('The Email field must be set')
        
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user
    
    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('email_verified', True)
        extra_fields.setdefault('role', 'ADMIN')
        extra_fields.setdefault('is_active', True)
        
        return self.create_user(email, password, **extra_fields)

class User(AbstractBaseUser, PermissionsMixin):
    class Role(models.TextChoices):
        USER = 'USER', 'User'
        ADMIN = 'ADMIN', 'Admin'
    
    # Required fields
    email = models.EmailField(unique=True, verbose_name='Email Address')
    
    # Personal info
    first_name = models.CharField(max_length=30)
    last_name = models.CharField(max_length=30)
    country = models.CharField(max_length=50)
    
    # Status fields
    email_verified = models.BooleanField(default=False)  # Email verified
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    
    # Role
    role = models.CharField(max_length=10, choices=Role.choices, default=Role.USER)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Email verification
    email_verification_token = models.CharField(max_length=64, null=True, blank=True)
    email_verification_sent_at = models.DateTimeField(null=True, blank=True)
    
    # Login attempts tracking
    failed_login_attempts = models.PositiveIntegerField(default=0)
    locked_until = models.DateTimeField(null=True, blank=True)
    last_failed_login = models.DateTimeField(null=True, blank=True)
    
    # Suspicious activity tracking
    suspicious_activity_count = models.PositiveIntegerField(default=0)
    is_under_review = models.BooleanField(default=False)
    review_reason = models.TextField(blank=True)
    
    # Investment limits (optional, can be used later)
    daily_investment_limit = models.DecimalField(
        max_digits=20,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Daily investment limit in USD"
    )
    last_investment_date = models.DateField(null=True, blank=True)
    daily_investment_total = models.DecimalField(
        max_digits=20,
        decimal_places=2,
        default=0.00
    )
    
    objects = UserManager()
    
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['first_name', 'last_name', 'country']
    
    class Meta:
        verbose_name = 'User'
        verbose_name_plural = 'Users'
    
    def __str__(self):
        return f"{self.email} ({self.get_role_display()})"
    
    def get_full_name(self):
        return f"{self.first_name} {self.last_name}"
    
    def get_short_name(self):
        return self.first_name
    
    def is_locked(self):
        if self.locked_until and self.locked_until > timezone.now():
            return True
        return False
    
    def increment_failed_attempts(self):
        """Increment failed login attempts with exponential backoff"""
        self.failed_login_attempts += 1
        self.last_failed_login = timezone.now()
        
        # Exponential backoff: 5 min, 15 min, 30 min, 1 hour, 2 hours, 4 hours, 8 hours...
        if self.failed_login_attempts >= 5:
            backoff_minutes = min(15 * (2 ** (self.failed_login_attempts - 5)), 480)  # Max 8 hours
            self.locked_until = timezone.now() + timezone.timedelta(minutes=backoff_minutes)
        
        self.save(update_fields=['failed_login_attempts', 'last_failed_login', 'locked_until'])
    
    def reset_failed_attempts(self):
        """Reset failed login attempts on successful login"""
        self.failed_login_attempts = 0
        self.locked_until = None
        self.last_failed_login = None
        self.save(update_fields=['failed_login_attempts', 'locked_until', 'last_failed_login'])
    
    def check_daily_investment_limit(self, amount):
        """Check if user has exceeded daily investment limit"""
        today = timezone.now().date()
        
        if self.daily_investment_limit is None:
            return True, None
        
        if self.last_investment_date != today:
            # Reset daily total
            self.daily_investment_total = 0
            self.last_investment_date = today
            self.save(update_fields=['daily_investment_total', 'last_investment_date'])
        
        if self.daily_investment_total + amount > self.daily_investment_limit:
            return False, f"Daily investment limit of ${self.daily_investment_limit} exceeded"
        
        return True, None
    
    def flag_suspicious_activity(self, reason):
        """Flag user for suspicious activity"""
        self.suspicious_activity_count += 1
        self.review_reason = f"{self.review_reason}\n{timezone.now()}: {reason}".strip()
        
        if self.suspicious_activity_count >= 3:
            self.is_under_review = True
            self.is_active = False
        
        self.save(update_fields=['suspicious_activity_count', 'review_reason', 'is_under_review', 'is_active'])
        
        # Send notification to admins (optional - can be implemented later)
        try:
            from notifications.utils import notify_admins
            notify_admins(
                title="Suspicious Activity Detected",
                message=f"User {self.email} flagged: {reason}",
                metadata={'user_id': self.id, 'reason': reason}
            )
        except ImportError:
            pass
    
    @property
    def is_admin(self):
        return self.role == self.Role.ADMIN
    
    @property
    def can_make_deposits(self):
        """Check if user can make deposits (requires email verification)"""
        return self.email_verified and self.is_active


class InvestmentProfile(models.Model):
    """
    Investment profile for user - optional, can be completed later
    """
    class EmploymentStatus(models.TextChoices):
        EMPLOYED = 'EMPLOYED', 'Employed'
        SELF_EMPLOYED = 'SELF_EMPLOYED', 'Self-employed'
        UNEMPLOYED = 'UNEMPLOYED', 'Unemployed'
        STUDENT = 'STUDENT', 'Student'
        RETIRED = 'RETIRED', 'Retired'
    
    class RiskTolerance(models.TextChoices):
        LOW = 'LOW', 'Low Risk'
        MEDIUM = 'MEDIUM', 'Medium Risk'
        HIGH = 'HIGH', 'High Risk'
    
    class InvestmentGoal(models.TextChoices):
        SHORT_TERM = 'SHORT_TERM', 'Short-term Growth (1-3 years)'
        MEDIUM_TERM = 'MEDIUM_TERM', 'Medium-term Growth (3-7 years)'
        LONG_TERM = 'LONG_TERM', 'Long-term Growth (7+ years)'
        RETIREMENT = 'RETIREMENT', 'Retirement Planning'
        WEALTH_PRESERVATION = 'WEALTH_PRESERVATION', 'Wealth Preservation'
    
    class AnnualIncome(models.TextChoices):
        UNDER_25K = 'UNDER_25K', 'Under $25,000'
        _25K_50K = '25K_50K', '$25,000 - $50,000'
        _50K_100K = '50K_100K', '$50,000 - $100,000'
        _100K_250K = '100K_250K', '$100,000 - $250,000'
        OVER_250K = 'OVER_250K', 'Over $250,000'
    
    # Foreign key to user
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='investment_profile')
    
    # Personal details
    date_of_birth = models.DateField(null=True, blank=True)
    address = models.CharField(max_length=255, null=True, blank=True)
    city = models.CharField(max_length=100, null=True, blank=True)
    postal_code = models.CharField(max_length=20, null=True, blank=True)
    
    # Financial information
    annual_income = models.CharField(
        max_length=20,
        choices=AnnualIncome.choices,
        null=True,
        blank=True
    )
    employment_status = models.CharField(
        max_length=20,
        choices=EmploymentStatus.choices,
        null=True,
        blank=True
    )
    source_of_funds = models.CharField(max_length=255, null=True, blank=True)
    
    # Investment preferences
    risk_tolerance = models.CharField(
        max_length=10,
        choices=RiskTolerance.choices,
        null=True,
        blank=True
    )
    investment_goal = models.CharField(
        max_length=30,
        choices=InvestmentGoal.choices,
        null=True,
        blank=True
    )
    investment_experience = models.TextField(null=True, blank=True)
    
    # Selected plan (will reference investment plans from another app)
    selected_plan_id = models.IntegerField(null=True, blank=True)
    selected_plan_name = models.CharField(max_length=100, null=True, blank=True)
    
    # Terms acceptance
    accepted_terms = models.BooleanField(default=False)
    accepted_privacy_policy = models.BooleanField(default=False)
    accepted_risk_disclosure = models.BooleanField(default=False)
    
    # Profile completion status
    is_completed = models.BooleanField(default=False)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'Investment Profile'
        verbose_name_plural = 'Investment Profiles'
    
    def __str__(self):
        return f"Investment Profile for {self.user.email}"
    
    def mark_as_completed(self):
        """Mark profile as completed"""
        self.is_completed = True
        self.completed_at = timezone.now()
        self.save(update_fields=['is_completed', 'completed_at'])