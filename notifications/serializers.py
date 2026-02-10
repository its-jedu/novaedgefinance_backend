from rest_framework import serializers
from django.utils import timezone
from .models import Notification, NotificationTemplate

class NotificationSerializer(serializers.ModelSerializer):
    user_email = serializers.EmailField(source='user.email', read_only=True)
    user_name = serializers.CharField(source='user.get_full_name', read_only=True)
    
    class Meta:
        model = Notification
        fields = [
            'notification_id', 'user', 'user_email', 'user_name',
            'notification_type', 'title', 'message', 'status',
            'email_sent', 'email_sent_at', 'email_error',
            'metadata', 'created_at', 'updated_at', 'read_at'
        ]
        read_only_fields = fields

class CreateNotificationSerializer(serializers.Serializer):
    user_id = serializers.IntegerField(required=True)
    notification_type = serializers.CharField(required=True)
    title = serializers.CharField(required=True, max_length=255)
    message = serializers.CharField(required=True)
    metadata = serializers.JSONField(required=False, default=dict)

class MarkAsReadSerializer(serializers.Serializer):
    notification_ids = serializers.ListField(
        child=serializers.UUIDField(),
        required=True
    )

class NotificationTemplateSerializer(serializers.ModelSerializer):
    class Meta:
        model = NotificationTemplate
        fields = [
            'id', 'template_name', 'notification_type',
            'subject', 'html_template', 'text_template',
            'variables', 'is_active', 'created_at', 'updated_at'
        ]

class SendTestEmailSerializer(serializers.Serializer):
    email = serializers.EmailField(required=True)
    template_id = serializers.IntegerField(required=True)
    variables = serializers.JSONField(required=False, default=dict)