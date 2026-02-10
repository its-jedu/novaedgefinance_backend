from django.db import models

# Create your models here.
from django.conf import settings
from django.utils import timezone
from decimal import Decimal
import uuid

class LedgerEntry(models.Model):
    """
    Immutable ledger for all financial transactions
    """
    class TransactionType(models.TextChoices):
        DEPOSIT = 'DEPOSIT', 'Deposit'
        WITHDRAWAL = 'WITHDRAWAL', 'Withdrawal'
        INVESTMENT = 'INVESTMENT', 'Investment'
        PROFIT = 'PROFIT', 'Profit'
        REFERRAL_BONUS = 'REFERRAL_BONUS', 'Referral Bonus'
        FEE = 'FEE', 'Fee'
        REFUND = 'REFUND', 'Refund'
        ADJUSTMENT = 'ADJUSTMENT', 'Adjustment'
    
    class SourceApp(models.TextChoices):
        WALLET = 'WALLET', 'Wallet'
        INVESTMENT = 'INVESTMENT', 'Investment'
        REFERRAL = 'REFERRAL', 'Referral'
        ADMIN = 'ADMIN', 'Admin'
        SYSTEM = 'SYSTEM', 'System'
    
    ledger_id = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='ledger_entries'
    )
    
    # Transaction details
    transaction_type = models.CharField(max_length=20, choices=TransactionType.choices)
    reference_id = models.CharField(max_length=100, db_index=True)
    
    # Amounts
    amount = models.DecimalField(max_digits=20, decimal_places=8)
    balance_before = models.DecimalField(max_digits=20, decimal_places=8)
    balance_after = models.DecimalField(max_digits=20, decimal_places=8)
    
    # Source tracking
    source_app = models.CharField(max_length=20, choices=SourceApp.choices)
    source_model = models.CharField(max_length=100, blank=True)
    source_id = models.CharField(max_length=100, blank=True)
    
    # Description
    description = models.TextField()
    metadata = models.JSONField(default=dict, blank=True)
    
    # Audit trail
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    
    # Verification
    is_verified = models.BooleanField(default=False)
    verified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='verified_ledger_entries'
    )
    verified_at = models.DateTimeField(null=True, blank=True)
    verification_notes = models.TextField(blank=True)
    
    # Timestamps (immutable)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Ledger Entry'
        verbose_name_plural = 'Ledger Entries'
        indexes = [
            models.Index(fields=['user', 'created_at']),
            models.Index(fields=['transaction_type', 'created_at']),
            models.Index(fields=['source_app', 'created_at']),
            models.Index(fields=['reference_id']),
        ]
    
    def __str__(self):
        return f"Ledger {self.ledger_id}: {self.transaction_type} - ${self.amount}"
    
    def verify(self, admin_user, notes=''):
        """Verify ledger entry (admin only)"""
        self.is_verified = True
        self.verified_by = admin_user
        self.verified_at = timezone.now()
        self.verification_notes = notes
        self.save()
    
    def is_immutable(self):
        """Ledger entries should never be modified"""
        return True


class AuditLog(models.Model):
    """
    Audit trail for admin actions
    """
    class ActionType(models.TextChoices):
        CREATE = 'CREATE', 'Create'
        UPDATE = 'UPDATE', 'Update'
        DELETE = 'DELETE', 'Delete'
        VIEW = 'VIEW', 'View'
        EXPORT = 'EXPORT', 'Export'
        LOGIN = 'LOGIN', 'Login'
        LOGOUT = 'LOGOUT', 'Logout'
        SUSPEND = 'SUSPEND', 'Suspend'
        ACTIVATE = 'ACTIVATE', 'Activate'
        VERIFY = 'VERIFY', 'Verify'
        APPROVE = 'APPROVE', 'Approve'
        REJECT = 'REJECT', 'Reject'
    
    audit_id = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    admin = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='audit_logs'
    )
    
    # Action details
    action = models.CharField(max_length=20, choices=ActionType.choices)
    target_object = models.CharField(max_length=255)
    target_model = models.CharField(max_length=100, blank=True)
    target_id = models.CharField(max_length=100, blank=True)
    
    # Changes
    changes_before = models.JSONField(default=dict, blank=True)
    changes_after = models.JSONField(default=dict, blank=True)
    changes_summary = models.TextField(blank=True)
    
    # Request details
    ip_address = models.GenericIPAddressField()
    user_agent = models.TextField(blank=True)
    request_path = models.CharField(max_length=500, blank=True)
    
    # Status
    status = models.CharField(
        max_length=20,
        choices=[
            ('SUCCESS', 'Success'),
            ('FAILED', 'Failed'),
            ('PENDING', 'Pending'),
        ],
        default='SUCCESS'
    )
    error_message = models.TextField(blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Audit Log'
        verbose_name_plural = 'Audit Logs'
        indexes = [
            models.Index(fields=['admin', 'created_at']),
            models.Index(fields=['action', 'created_at']),
            models.Index(fields=['target_model', 'created_at']),
        ]
    
    def __str__(self):
        return f"Audit {self.audit_id}: {self.admin.email} - {self.action}"


class FinancialReport(models.Model):
    """
    Generated financial reports
    """
    class ReportType(models.TextChoices):
        DAILY_SUMMARY = 'DAILY_SUMMARY', 'Daily Summary'
        WEEKLY_SUMMARY = 'WEEKLY_SUMMARY', 'Weekly Summary'
        MONTHLY_SUMMARY = 'MONTHLY_SUMMARY', 'Monthly Summary'
        QUARTERLY_SUMMARY = 'QUARTERLY_SUMMARY', 'Quarterly Summary'
        YEARLY_SUMMARY = 'YEARLY_SUMMARY', 'Yearly Summary'
        USER_ACTIVITY = 'USER_ACTIVITY', 'User Activity'
        DEPOSIT_REPORT = 'DEPOSIT_REPORT', 'Deposit Report'
        WITHDRAWAL_REPORT = 'WITHDRAWAL_REPORT', 'Withdrawal Report'
        INVESTMENT_REPORT = 'INVESTMENT_REPORT', 'Investment Report'
        REFERRAL_REPORT = 'REFERRAL_REPORT', 'Referral Report'
        CUSTOM = 'CUSTOM', 'Custom Report'
    
    class ReportFormat(models.TextChoices):
        JSON = 'JSON', 'JSON'
        CSV = 'CSV', 'CSV'
        PDF = 'PDF', 'PDF'
        EXCEL = 'EXCEL', 'Excel'
    
    report_id = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    generated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='generated_reports'
    )
    
    # Report details
    report_type = models.CharField(max_length=50, choices=ReportType.choices)
    report_format = models.CharField(max_length=10, choices=ReportFormat.choices, default='JSON')
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    
    # Parameters
    date_from = models.DateField(null=True, blank=True)
    date_to = models.DateField(null=True, blank=True)
    filters = models.JSONField(default=dict, blank=True)
    
    # Data
    report_data = models.JSONField(default=dict, blank=True)
    summary = models.JSONField(default=dict, blank=True)
    
    # Storage
    file_path = models.CharField(max_length=500, blank=True)
    file_size = models.PositiveIntegerField(default=0)
    download_url = models.URLField(blank=True)
    
    # Status
    is_generated = models.BooleanField(default=False)
    generation_started_at = models.DateTimeField(null=True, blank=True)
    generation_completed_at = models.DateTimeField(null=True, blank=True)
    generation_duration = models.DurationField(null=True, blank=True)
    error_message = models.TextField(blank=True)
    
    # Security
    is_encrypted = models.BooleanField(default=False)
    encryption_key = models.CharField(max_length=255, blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Financial Report'
        verbose_name_plural = 'Financial Reports'
    
    def __str__(self):
        return f"Report {self.report_id}: {self.title}"
    
    def start_generation(self):
        """Mark report generation as started"""
        self.generation_started_at = timezone.now()
        self.save()
    
    def complete_generation(self, data, file_path=None, download_url=None):
        """Mark report generation as completed"""
        self.report_data = data
        self.is_generated = True
        self.generation_completed_at = timezone.now()
        
        if self.generation_started_at:
            self.generation_duration = self.generation_completed_at - self.generation_started_at
        
        if file_path:
            self.file_path = file_path
        
        if download_url:
            self.download_url = download_url
        
        # Calculate summary
        self.calculate_summary()
        
        self.save()
    
    def calculate_summary(self):
        """Calculate report summary"""
        # Implementation depends on report type
        self.summary = {
            'generated_at': timezone.now().isoformat(),
            'data_points': len(self.report_data) if isinstance(self.report_data, list) else 0,
            'filters': self.filters
        }
        self.save()
    
    def mark_as_failed(self, error_message):
        """Mark report generation as failed"""
        self.is_generated = False
        self.error_message = error_message
        self.generation_completed_at = timezone.now()
        
        if self.generation_started_at:
            self.generation_duration = self.generation_completed_at - self.generation_started_at
        
        self.save()


class UserActivityLog(models.Model):
    """
    Log user activities for analytics
    """
    class ActivityType(models.TextChoices):
        LOGIN = 'LOGIN', 'Login'
        LOGOUT = 'LOGOUT', 'Logout'
        PROFILE_UPDATE = 'PROFILE_UPDATE', 'Profile Update'
        PASSWORD_CHANGE = 'PASSWORD_CHANGE', 'Password Change'
        DEPOSIT_INITIATED = 'DEPOSIT_INITIATED', 'Deposit Initiated'
        DEPOSIT_COMPLETED = 'DEPOSIT_COMPLETED', 'Deposit Completed'
        INVESTMENT_STARTED = 'INVESTMENT_STARTED', 'Investment Started'
        INVESTMENT_COMPLETED = 'INVESTMENT_COMPLETED', 'Investment Completed'
        WITHDRAWAL_REQUESTED = 'WITHDRAWAL_REQUESTED', 'Withdrawal Requested'
        WITHDRAWAL_COMPLETED = 'WITHDRAWAL_COMPLETED', 'Withdrawal Completed'
        REFERRAL_SIGNUP = 'REFERRAL_SIGNUP', 'Referral Signup'
        TICKET_CREATED = 'TICKET_CREATED', 'Support Ticket Created'
        TICKET_REPLIED = 'TICKET_REPLIED', 'Ticket Replied'
        NOTIFICATION_READ = 'NOTIFICATION_READ', 'Notification Read'
        PAGE_VIEW = 'PAGE_VIEW', 'Page View'
    
    activity_id = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='activity_logs'
    )
    
    # Activity details
    activity_type = models.CharField(max_length=50, choices=ActivityType.choices)
    description = models.TextField()
    
    # Context
    page_url = models.URLField(blank=True)
    referrer_url = models.URLField(blank=True)
    session_id = models.CharField(max_length=100, blank=True)
    
    # Device & location
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    device_type = models.CharField(max_length=50, blank=True)
    browser = models.CharField(max_length=50, blank=True)
    operating_system = models.CharField(max_length=50, blank=True)
    
    # Location (populated by GeoIP if available)
    country = models.CharField(max_length=100, blank=True)
    city = models.CharField(max_length=100, blank=True)
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)
    
    # Metadata
    metadata = models.JSONField(default=dict, blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = 'User Activity Log'
        verbose_name_plural = 'User Activity Logs'
        indexes = [
            models.Index(fields=['user', 'created_at']),
            models.Index(fields=['activity_type', 'created_at']),
            models.Index(fields=['ip_address', 'created_at']),
        ]
    
    def __str__(self):
        return f"Activity {self.activity_id}: {self.user.email} - {self.activity_type}"


class SystemHealthCheck(models.Model):
    """
    System health and performance monitoring
    """
    check_id = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    
    # Check details
    check_type = models.CharField(
        max_length=50,
        choices=[
            ('DATABASE', 'Database'),
            ('CACHE', 'Cache'),
            ('STORAGE', 'Storage'),
            ('API', 'API'),
            ('PAYMENT_GATEWAY', 'Payment Gateway'),
            ('EMAIL_SERVICE', 'Email Service'),
            ('FULL', 'Full System'),
        ]
    )
    
    # Status
    status = models.CharField(
        max_length=20,
        choices=[
            ('HEALTHY', 'Healthy'),
            ('DEGRADED', 'Degraded'),
            ('UNHEALTHY', 'Unhealthy'),
            ('OFFLINE', 'Offline'),
        ]
    )
    
    # Metrics
    response_time = models.FloatField(help_text="Response time in milliseconds")
    success_rate = models.FloatField(help_text="Success rate percentage")
    
    # Details
    message = models.TextField(blank=True)
    details = models.JSONField(default=dict, blank=True)
    error_message = models.TextField(blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = 'System Health Check'
        verbose_name_plural = 'System Health Checks'
    
    def __str__(self):
        return f"Health Check {self.check_id}: {self.check_type} - {self.status}"

