from django.db import models

# Create your models here.
from django.conf import settings
from django.utils import timezone
import uuid

class SupportTicket(models.Model):
    """
    Support tickets for customer service
    """
    class TicketStatus(models.TextChoices):
        OPEN = 'OPEN', 'Open'
        IN_PROGRESS = 'IN_PROGRESS', 'In Progress'
        RESOLVED = 'RESOLVED', 'Resolved'
        CLOSED = 'CLOSED', 'Closed'
    
    class TicketPriority(models.TextChoices):
        LOW = 'LOW', 'Low'
        MEDIUM = 'MEDIUM', 'Medium'
        HIGH = 'HIGH', 'High'
        URGENT = 'URGENT', 'Urgent'
    
    class TicketCategory(models.TextChoices):
        ACCOUNT = 'ACCOUNT', 'Account Issues'
        DEPOSIT = 'DEPOSIT', 'Deposit Problems'
        WITHDRAWAL = 'WITHDRAWAL', 'Withdrawal Problems'
        INVESTMENT = 'INVESTMENT', 'Investment Questions'
        REFERRAL = 'REFERRAL', 'Referral Program'
        TECHNICAL = 'TECHNICAL', 'Technical Issues'
        SECURITY = 'SECURITY', 'Security Concerns'
        OTHER = 'OTHER', 'Other'
    
    ticket_id = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='support_tickets'
    )
    
    # Ticket details
    subject = models.CharField(max_length=255)
    category = models.CharField(
        max_length=20,
        choices=TicketCategory.choices,
        default=TicketCategory.OTHER
    )
    description = models.TextField()
    
    # Status
    status = models.CharField(
        max_length=20,
        choices=TicketStatus.choices,
        default=TicketStatus.OPEN
    )
    priority = models.CharField(
        max_length=20,
        choices=TicketPriority.choices,
        default=TicketPriority.MEDIUM
    )
    
    # Assignment
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assigned_tickets'
    )
    
    # Resolution
    resolved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='resolved_tickets'
    )
    resolution = models.TextField(blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    
    # Statistics
    message_count = models.PositiveIntegerField(default=0)
    last_message_at = models.DateTimeField(null=True, blank=True)
    
    # Metadata
    metadata = models.JSONField(default=dict, blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Support Ticket'
        verbose_name_plural = 'Support Tickets'
    
    def __str__(self):
        return f"Ticket #{self.ticket_id}: {self.subject}"
    
    def update_status(self, new_status, user=None):
        """Update ticket status"""
        self.status = new_status
        
        if new_status == self.TicketStatus.RESOLVED and user:
            self.resolved_by = user
            self.resolved_at = timezone.now()
        
        self.save()
    
    def close_ticket(self, user=None):
        """Close the ticket"""
        self.status = self.TicketStatus.CLOSED
        
        if user and not self.resolved_by:
            self.resolved_by = user
        
        if not self.resolved_at:
            self.resolved_at = timezone.now()
        
        self.save()
    
    def increment_message_count(self):
        """Increment message count and update last message timestamp"""
        self.message_count += 1
        self.last_message_at = timezone.now()
        self.save()


class SupportMessage(models.Model):
    """
    Messages within a support ticket
    """
    message_id = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    ticket = models.ForeignKey(
        SupportTicket,
        on_delete=models.CASCADE,
        related_name='messages'
    )
    
    # Sender information
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='support_messages'
    )
    is_admin = models.BooleanField(default=False)
    
    # Message content
    message = models.TextField()
    attachments = models.JSONField(
        default=list,
        blank=True,
        help_text="List of attachment URLs"
    )
    
    # Read tracking
    is_read = models.BooleanField(default=False)
    read_at = models.DateTimeField(null=True, blank=True)
    
    # Metadata
    metadata = models.JSONField(default=dict, blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['created_at']
        verbose_name = 'Support Message'
        verbose_name_plural = 'Support Messages'
    
    def __str__(self):
        return f"Message from {self.sender.email} in Ticket #{self.ticket.ticket_id}"
    
    def mark_as_read(self):
        """Mark message as read"""
        if not self.is_read:
            self.is_read = True
            self.read_at = timezone.now()
            self.save()


class SupportDepartment(models.Model):
    """
    Support departments for ticket categorization
    """
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    email = models.EmailField(blank=True)
    
    # Assignment
    assigned_admins = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        blank=True,
        related_name='support_departments'
    )
    
    # Settings
    is_active = models.BooleanField(default=True)
    response_time_target = models.PositiveIntegerField(
        default=24,
        help_text="Target response time in hours"
    )
    
    # Statistics
    open_tickets = models.PositiveIntegerField(default=0)
    resolved_tickets = models.PositiveIntegerField(default=0)
    average_response_time = models.FloatField(default=0.0)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'Support Department'
        verbose_name_plural = 'Support Departments'
    
    def __str__(self):
        return self.name


class FAQ(models.Model):
    """
    Frequently Asked Questions for support
    """
    question = models.CharField(max_length=255)
    answer = models.TextField()
    
    # Categorization
    category = models.CharField(
        max_length=50,
        choices=[
            ('GENERAL', 'General'),
            ('ACCOUNT', 'Account'),
            ('DEPOSIT', 'Deposits'),
            ('WITHDRAWAL', 'Withdrawals'),
            ('INVESTMENT', 'Investments'),
            ('REFERRAL', 'Referral Program'),
            ('SECURITY', 'Security'),
            ('OTHER', 'Other'),
        ],
        default='GENERAL'
    )
    
    # Display
    display_order = models.PositiveIntegerField(default=0)
    is_published = models.BooleanField(default=True)
    
    # Statistics
    views = models.PositiveIntegerField(default=0)
    helpful_count = models.PositiveIntegerField(default=0)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['category', 'display_order']
        verbose_name = 'FAQ'
        verbose_name_plural = 'FAQs'
    
    def __str__(self):
        return f"FAQ: {self.question[:50]}..."
    
    def increment_views(self):
        """Increment view count"""
        self.views += 1
        self.save()
    
    def mark_helpful(self):
        """Mark FAQ as helpful"""
        self.helpful_count += 1
        self.save()

