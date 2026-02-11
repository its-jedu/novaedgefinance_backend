from django.db import models

# Create your models here.
from django.db import models
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.core.validators import RegexValidator
from django.utils import timezone

class UserManager(BaseUserManager):
    def create_user(self, email, phone_number, password=None, **extra_fields):
        if not email:
            raise ValueError('The Email field must be set')
        if not phone_number:
            raise ValueError('The Phone Number field must be set')
        
        email = self.normalize_email(email)
        user = self.model(email=email, phone_number=phone_number, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user
    
    def create_superuser(self, email, phone_number, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_verified', True)
        extra_fields.setdefault('email_verified', True)
        extra_fields.setdefault('profile_completed', True)
        extra_fields.setdefault('role', 'ADMIN')
        extra_fields.setdefault('is_active', True)
        
        return self.create_user(email, phone_number, password, **extra_fields)

class User(AbstractBaseUser, PermissionsMixin):
    class Role(models.TextChoices):
        USER = 'USER', 'User'
        ADMIN = 'ADMIN', 'Admin'
    
    # Required fields
    email = models.EmailField(unique=True, verbose_name='Email Address')
    phone_number = models.CharField(
        max_length=15,
        unique=True,
        validators=[
            RegexValidator(
                regex=r'^\+?1?\d{9,15}$',
                message="Phone number must be entered in the format: '+999999999'. Up to 15 digits allowed."
            )
        ]
    )
    
    # Personal info
    first_name = models.CharField(max_length=30)
    last_name = models.CharField(max_length=30)
    country = models.CharField(max_length=50)
    
    # Status fields
    is_verified = models.BooleanField(default=False)  # Phone verified
    email_verified = models.BooleanField(default=False)  # Email verified
    profile_completed = models.BooleanField(default=False)  # Profile completed
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    
    # Role
    role = models.CharField(max_length=10, choices=Role.choices, default=Role.USER)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    profile_completed_at = models.DateTimeField(null=True, blank=True)
    
    # Login attempts tracking
    failed_login_attempts = models.PositiveIntegerField(default=0)
    locked_until = models.DateTimeField(null=True, blank=True)
    
    # Phone verification
    phone_verification_code = models.CharField(max_length=6, null=True, blank=True)
    phone_verification_sent_at = models.DateTimeField(null=True, blank=True)
    
    # Email verification
    email_verification_token = models.CharField(max_length=64, null=True, blank=True)
    email_verification_sent_at = models.DateTimeField(null=True, blank=True)

    # Enhanced security fields
    failed_login_attempts = models.PositiveIntegerField(default=0)
    locked_until = models.DateTimeField(null=True, blank=True)
    last_failed_login = models.DateTimeField(null=True, blank=True)
    
    # Suspicious activity tracking
    suspicious_activity_count = models.PositiveIntegerField(default=0)
    is_under_review = models.BooleanField(default=False)
    review_reason = models.TextField(blank=True)
    
    # Investment limits
    daily_investment_limit = models.DecimalField(
        max_digits=20,
        decimal_places=8,
        null=True,
        blank=True,
        help_text="Daily investment limit in USD"
    )
    last_investment_date = models.DateField(null=True, blank=True)
    daily_investment_total = models.DecimalField(
        max_digits=20,
        decimal_places=8,
        default=0.00
    )
    
    objects = UserManager()
    
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['phone_number', 'first_name', 'last_name', 'country']
    
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
        
        self.save()
    
    def reset_failed_attempts(self):
        """Reset failed login attempts on successful login"""
        self.failed_login_attempts = 0
        self.locked_until = None
        self.save()
    
    def check_daily_investment_limit(self, amount):
        """Check if user has exceeded daily investment limit"""
        today = timezone.now().date()
        
        if self.daily_investment_limit is None:
            return True, None
        
        if self.last_investment_date != today:
            # Reset daily total
            self.daily_investment_total = 0
            self.last_investment_date = today
            self.save()
        
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
        
        self.save()
        
        # Send notification to admins
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
    def is_fully_verified(self):
        """Check if user has completed all verification steps"""
        return self.is_verified and self.email_verified and self.profile_completed
    
    @property
    def can_make_deposits(self):
        """Check if user can make deposits (requires profile completion)"""
        return self.profile_completed and self.email_verified and self.is_verified


class InvestmentProfile(models.Model):
    """
    Investment profile for user profile completion
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
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'Investment Profile'
        verbose_name_plural = 'Investment Profiles'
    
    def __str__(self):
        return f"Investment Profile for {self.user.email}"
    
