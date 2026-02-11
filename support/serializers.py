from rest_framework import serializers
from django.utils import timezone
from .models import (
    SupportTicket, SupportMessage,
    SupportDepartment, FAQ
)

class SupportTicketSerializer(serializers.ModelSerializer):
    user_email = serializers.EmailField(source='user.email', read_only=True)
    user_name = serializers.CharField(source='user.get_full_name', read_only=True)
    assigned_to_email = serializers.EmailField(source='assigned_to.email', read_only=True)
    resolved_by_email = serializers.EmailField(source='resolved_by.email', read_only=True)
    
    # Computed fields
    days_open = serializers.IntegerField(read_only=True)
    last_message_preview = serializers.CharField(read_only=True)
    
    class Meta:
        model = SupportTicket
        fields = [
            'ticket_id', 'user', 'user_email', 'user_name',
            'subject', 'category', 'description', 'status',
            'priority', 'assigned_to', 'assigned_to_email',
            'resolved_by', 'resolved_by_email', 'resolution',
            'resolved_at', 'message_count', 'last_message_at',
            'metadata', 'days_open', 'last_message_preview',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'ticket_id', 'message_count', 'last_message_at',
            'resolved_at', 'resolved_by', 'assigned_to',
            'days_open', 'last_message_preview',
            'created_at', 'updated_at'
        ]

class CreateTicketSerializer(serializers.Serializer):
    subject = serializers.CharField(required=True, max_length=255)
    category = serializers.ChoiceField(
        choices=SupportTicket.TicketCategory.choices,
        required=True
    )
    description = serializers.CharField(required=True)
    priority = serializers.ChoiceField(
        choices=SupportTicket.TicketPriority.choices,
        default=SupportTicket.TicketPriority.MEDIUM,
        required=False
    )

class SupportMessageSerializer(serializers.ModelSerializer):
    sender_email = serializers.EmailField(source='sender.email', read_only=True)
    sender_name = serializers.CharField(source='sender.get_full_name', read_only=True)
    ticket_id = serializers.UUIDField(source='ticket.ticket_id', read_only=True)
    
    class Meta:
        model = SupportMessage
        fields = [
            'message_id', 'ticket', 'ticket_id', 'sender', 'sender_email',
            'sender_name', 'is_admin', 'message', 'attachments',
            'is_read', 'read_at', 'metadata', 'created_at'
        ]
        read_only_fields = [
            'message_id', 'is_admin', 'is_read', 'read_at',
            'created_at'
        ]

class CreateMessageSerializer(serializers.Serializer):
    message = serializers.CharField(required=True)
    attachments = serializers.ListField(
        child=serializers.URLField(),
        required=False,
        default=[]
    )

class UpdateTicketStatusSerializer(serializers.Serializer):
    status = serializers.ChoiceField(
        choices=SupportTicket.TicketStatus.choices,
        required=True
    )
    resolution = serializers.CharField(required=False, allow_blank=True)

class AssignTicketSerializer(serializers.Serializer):
    admin_id = serializers.IntegerField(required=True)

class SupportDepartmentSerializer(serializers.ModelSerializer):
    admin_count = serializers.IntegerField(read_only=True)
    
    class Meta:
        model = SupportDepartment
        fields = [
            'id', 'name', 'description', 'email',
            'assigned_admins', 'admin_count', 'is_active',
            'response_time_target', 'open_tickets',
            'resolved_tickets', 'average_response_time',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'open_tickets', 'resolved_tickets',
            'average_response_time', 'created_at', 'updated_at'
        ]

class FAQSerializer(serializers.ModelSerializer):
    class Meta:
        model = FAQ
        fields = [
            'id', 'question', 'answer', 'category',
            'display_order', 'is_published', 'views',
            'helpful_count', 'created_at', 'updated_at'
        ]
        read_only_fields = ['views', 'helpful_count', 'created_at', 'updated_at']

class TicketStatsSerializer(serializers.Serializer):
    total_tickets = serializers.IntegerField()
    open_tickets = serializers.IntegerField()
    in_progress_tickets = serializers.IntegerField()
    resolved_tickets = serializers.IntegerField()
    closed_tickets = serializers.IntegerField()
    average_response_time = serializers.FloatField()
    satisfaction_rate = serializers.FloatField()

class TicketSearchSerializer(serializers.Serializer):
    query = serializers.CharField(required=True, max_length=100)
