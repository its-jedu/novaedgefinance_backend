from django.shortcuts import render

# Create your views here.
from rest_framework import generics, views, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from django.utils import timezone
import logging

from .models import Notification, NotificationTemplate
from .serializers import (
    NotificationSerializer, CreateNotificationSerializer,
    MarkAsReadSerializer, NotificationTemplateSerializer,
    SendTestEmailSerializer
)
from .permissions import IsOwnerOrAdmin, AdminOnly
from .utils import send_notification_email

logger = logging.getLogger(__name__)


class UserNotificationsView(generics.ListAPIView):
    """
    Get user's notifications
    """
    permission_classes = [IsAuthenticated]
    serializer_class = NotificationSerializer
    
    def get_queryset(self):
        return Notification.objects.filter(
            user=self.request.user
        ).order_by('-created_at')


class UnreadNotificationsView(generics.ListAPIView):
    """
    Get user's unread notifications
    """
    permission_classes = [IsAuthenticated]
    serializer_class = NotificationSerializer
    
    def get_queryset(self):
        return Notification.objects.filter(
            user=self.request.user,
            status__in=['PENDING', 'SENT']
        ).order_by('-created_at')


class MarkAsReadView(APIView):
    """
    Mark notifications as read
    """
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        serializer = MarkAsReadSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        notification_ids = serializer.validated_data['notification_ids']
        
        # Get user's notifications
        notifications = Notification.objects.filter(
            user=request.user,
            notification_id__in=notification_ids
        )
        
        count = 0
        for notification in notifications:
            notification.mark_as_read()
            count += 1
        
        return Response({
            'message': f'{count} notifications marked as read',
            'count': count
        }, status=status.HTTP_200_OK)


class MarkAllAsReadView(APIView):
    """
    Mark all user's notifications as read
    """
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        notifications = Notification.objects.filter(
            user=request.user,
            status__in=['PENDING', 'SENT']
        )
        
        count = 0
        for notification in notifications:
            notification.mark_as_read()
            count += 1
        
        return Response({
            'message': f'{count} notifications marked as read',
            'count': count
        }, status=status.HTTP_200_OK)


class NotificationCountView(APIView):
    """
    Get unread notification count
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        count = Notification.objects.filter(
            user=request.user,
            status__in=['PENDING', 'SENT']
        ).count()
        
        return Response({
            'count': count
        }, status=status.HTTP_200_OK)


# Admin Views

class AdminNotificationListView(generics.ListAPIView):
    """
    Admin: List all notifications
    """
    permission_classes = [IsAuthenticated, AdminOnly]
    serializer_class = NotificationSerializer
    queryset = Notification.objects.all().order_by('-created_at')
    
    def get_queryset(self):
        queryset = Notification.objects.all()
        
        # Filter by user email
        user_email = self.request.query_params.get('user_email', None)
        if user_email:
            queryset = queryset.filter(user__email__icontains=user_email)
        
        # Filter by notification type
        notification_type = self.request.query_params.get('type', None)
        if notification_type:
            queryset = queryset.filter(notification_type=notification_type)
        
        # Filter by status
        status = self.request.query_params.get('status', None)
        if status:
            queryset = queryset.filter(status=status)
        
        # Filter by date range
        start_date = self.request.query_params.get('start_date', None)
        end_date = self.request.query_params.get('end_date', None)
        
        if start_date:
            queryset = queryset.filter(created_at__date__gte=start_date)
        if end_date:
            queryset = queryset.filter(created_at__date__lte=end_date)
        
        return queryset.order_by('-created_at')


class AdminResendNotificationView(APIView):
    """
    Admin: Resend failed notification
    """
    permission_classes = [IsAuthenticated, AdminOnly]
    
    def post(self, request, notification_id):
        try:
            notification = get_object_or_404(Notification, notification_id=notification_id)
            
            # Only resend failed notifications
            if notification.status != Notification.NotificationStatus.FAILED:
                return Response({
                    'error': 'Can only resend failed notifications'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Try to send email again
            success = send_notification_email(notification)
            
            if success:
                notification.mark_as_sent()
                return Response({
                    'message': 'Notification resent successfully',
                    'notification': NotificationSerializer(notification).data
                }, status=status.HTTP_200_OK)
            else:
                return Response({
                    'error': 'Failed to resend notification'
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
                
        except Exception as e:
            logger.error(f"Error resending notification: {str(e)}")
            return Response({
                'error': 'Failed to resend notification'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class AdminTemplateListView(generics.ListCreateAPIView):
    """
    Admin: List and create notification templates
    """
    permission_classes = [IsAuthenticated, AdminOnly]
    serializer_class = NotificationTemplateSerializer
    queryset = NotificationTemplate.objects.all().order_by('template_name')


class AdminTemplateDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    Admin: Manage notification template
    """
    permission_classes = [IsAuthenticated, AdminOnly]
    serializer_class = NotificationTemplateSerializer
    queryset = NotificationTemplate.objects.all()
    lookup_field = 'id'


class AdminSendTestEmailView(APIView):
    """
    Admin: Send test email with template
    """
    permission_classes = [IsAuthenticated, AdminOnly]
    
    def post(self, request):
        serializer = SendTestEmailSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        email = serializer.validated_data['email']
        template_id = serializer.validated_data['template_id']
        variables = serializer.validated_data.get('variables', {})
        
        try:
            template = NotificationTemplate.objects.get(id=template_id)
            
            # Send test email
            from .utils import send_template_email
            success = send_template_email(
                to_email=email,
                template=template,
                variables=variables
            )
            
            if success:
                return Response({
                    'message': f'Test email sent to {email}'
                }, status=status.HTTP_200_OK)
            else:
                return Response({
                    'error': 'Failed to send test email'
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
                
        except NotificationTemplate.DoesNotExist:
            return Response({
                'error': 'Template not found'
            }, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.error(f"Error sending test email: {str(e)}")
            return Response({
                'error': 'Failed to send test email'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)