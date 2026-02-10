from django.db import models

# Create your models here.
from django.conf import settings
from django.utils import timezone
import uuid

class Notification(models.Model):
    """
    System notifications for users
    """
    class NotificationType(models.TextChoices):
        ACCOUNT_REGISTRATION = 'ACCOUNT_REGISTRATION', 'Account Registration'
        LOGIN = 'LOGIN', 'Login'
        ACCOUNT_UPDATE = 'ACCOUNT_UPDATE', 'Account Update'
        DEPOSIT_CONFIRMED = 'DEPOSIT_CONFIRMED', 'Deposit Confirmed'
        INVESTMENT_STARTED = 'INVESTMENT_STARTED', 'Investment Started'
        INVESTMENT_COMPLETED = 'INVESTMENT_COMPLETED', 'Investment Completed'
        PROFIT_CREDITED = 'PROFIT_CREDITED', 'Profit Credited'
        WITHDRAWAL_REQUESTED = 'WITHDRAWAL_REQUESTED', 'Withdrawal Requested'
        WITHDRAWAL_COMPLETED = 'WITHDRAWAL_COMPLETED', 'Withdrawal Completed'
        ACCOUNT_SUSPENSION = 'ACCOUNT_SUSPENSION', 'Account Suspension'
        ACCOUNT_BAN = 'ACCOUNT_BAN', 'Account Ban'
        PASSWORD_RESET = 'PASSWORD_RESET', 'Password Reset'
        ADMIN_ACTION = 'ADMIN_ACTION', 'Admin Action'
        SECURITY_ALERT = 'SECURITY_ALERT', 'Security Alert'
        REFERRAL_BONUS = 'REFERRAL_BONUS', 'Referral Bonus'
        SYSTEM_UPDATE = 'SYSTEM_UPDATE', 'System Update'
    
    class NotificationStatus(models.TextChoices):
        PENDING = 'PENDING', 'Pending'
        SENT = 'SENT', 'Sent'
        FAILED = 'FAILED', 'Failed'
        READ = 'READ', 'Read'
    
    notification_id = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='notifications'
    )
    
    notification_type = models.CharField(max_length=50, choices=NotificationType.choices)
    title = models.CharField(max_length=255)
    message = models.TextField()
    
    status = models.CharField(
        max_length=20,
        choices=NotificationStatus.choices,
        default=NotificationStatus.PENDING
    )
    
    # Email tracking
    email_sent = models.BooleanField(default=False)
    email_sent_at = models.DateTimeField(null=True, blank=True)
    email_error = models.TextField(blank=True)
    
    # Metadata
    metadata = models.JSONField(default=dict, blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    read_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Notification'
        verbose_name_plural = 'Notifications'
    
    def __str__(self):
        return f"{self.notification_type} - {self.user.email} - {self.status}"
    
    def mark_as_sent(self):
        self.status = self.NotificationStatus.SENT
        self.email_sent = True
        self.email_sent_at = timezone.now()
        self.save()
    
    def mark_as_failed(self, error_message):
        self.status = self.NotificationStatus.FAILED
        self.email_error = error_message
        self.save()
    
    def mark_as_read(self):
        if not self.read_at:
            self.status = self.NotificationStatus.READ
            self.read_at = timezone.now()
            self.save()


class NotificationTemplate(models.Model):
    """
    Email templates for notifications
    """
    template_name = models.CharField(max_length=100, unique=True)
    notification_type = models.CharField(
        max_length=50,
        choices=Notification.NotificationType.choices,
        unique=True
    )
    
    subject = models.CharField(max_length=255)
    html_template = models.TextField(help_text="HTML template with {{variables}}")
    text_template = models.TextField(help_text="Plain text template with {{variables}}")
    
    # Variables description
    variables = models.JSONField(
        default=list,
        blank=True,
        help_text="List of available template variables"
    )
    
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'Notification Template'
        verbose_name_plural = 'Notification Templates'
    
    def __str__(self):
        return f"{self.template_name} ({self.notification_type})"