from django.shortcuts import render

# Create your views here.
from rest_framework import generics, views, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from django.db.models import Q, Count, Avg
from django.shortcuts import get_object_or_404
from django.utils import timezone
import logging

from .models import (
    SupportTicket, SupportMessage,
    SupportDepartment, FAQ
)
from .serializers import (
    SupportTicketSerializer, CreateTicketSerializer,
    SupportMessageSerializer, CreateMessageSerializer,
    UpdateTicketStatusSerializer, AssignTicketSerializer,
    SupportDepartmentSerializer, FAQSerializer,
    TicketStatsSerializer, TicketSearchSerializer
)
from .permissions import IsOwnerOrAdmin, IsTicketOwner, AdminOnly, CanRespondToTicket

logger = logging.getLogger(__name__)


class MyTicketsView(generics.ListCreateAPIView):
    """
    User: List and create support tickets
    """
    permission_classes = [IsAuthenticated]
    
    def get_serializer_class(self):
        if self.request.method == 'POST':
            return CreateTicketSerializer
        return SupportTicketSerializer
    
    def get_queryset(self):
        return SupportTicket.objects.filter(
            user=self.request.user
        ).order_by('-created_at')
    
    def perform_create(self, serializer):
        ticket = SupportTicket.objects.create(
            user=self.request.user,
            subject=serializer.validated_data['subject'],
            category=serializer.validated_data['category'],
            description=serializer.validated_data['description'],
            priority=serializer.validated_data.get('priority', 'MEDIUM')
        )
        
        # Create initial message
        SupportMessage.objects.create(
            ticket=ticket,
            sender=self.request.user,
            message=serializer.validated_data['description'],
            is_admin=False
        )
        
        # Update ticket message count
        ticket.increment_message_count()
        
        # Send notification to admins
        self.notify_admins(ticket)
        
        logger.info(f"Support ticket created: {ticket.ticket_id}")
    
    def notify_admins(self, ticket):
        """Notify admins about new ticket"""
        try:
            from notifications.utils import create_notification
            
            # Get admin users
            from django.contrib.auth import get_user_model
            User = get_user_model()
            admins = User.objects.filter(role='ADMIN', is_active=True)
            
            for admin in admins:
                create_notification(
                    user=admin,
                    notification_type='SYSTEM_UPDATE',
                    title='New Support Ticket',
                    message=f'New ticket created: {ticket.subject}',
                    metadata={
                        'ticket_id': str(ticket.ticket_id),
                        'user': ticket.user.email,
                        'category': ticket.category
                    }
                )
        except ImportError:
            logger.warning("Notifications app not installed")


class TicketDetailView(generics.RetrieveAPIView):
    """
    Get ticket details
    """
    permission_classes = [IsAuthenticated, IsOwnerOrAdmin]
    serializer_class = SupportTicketSerializer
    lookup_field = 'ticket_id'
    
    def get_queryset(self):
        if self.request.user.role == 'ADMIN':
            return SupportTicket.objects.all()
        return SupportTicket.objects.filter(user=self.request.user)


class TicketMessagesView(generics.ListAPIView):
    """
    Get messages for a ticket
    """
    permission_classes = [IsAuthenticated, IsOwnerOrAdmin]
    serializer_class = SupportMessageSerializer
    
    def get_queryset(self):
        ticket_id = self.kwargs['ticket_id']
        
        # Get ticket with permission check
        ticket = get_object_or_404(SupportTicket, ticket_id=ticket_id)
        
        # Check permissions
        if self.request.user.role != 'ADMIN' and ticket.user != self.request.user:
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied("You don't have permission to view this ticket.")
        
        # Mark user's unread messages as read
        if self.request.user.role == 'ADMIN':
            # Mark all user messages as read for admin
            unread_messages = SupportMessage.objects.filter(
                ticket=ticket,
                is_admin=False,
                is_read=False
            )
        else:
            # Mark all admin messages as read for user
            unread_messages = SupportMessage.objects.filter(
                ticket=ticket,
                is_admin=True,
                is_read=False
            )
        
        for message in unread_messages:
            message.mark_as_read()
        
        return SupportMessage.objects.filter(ticket=ticket).order_by('created_at')


class ReplyToTicketView(APIView):
    """
    Reply to a support ticket
    """
    permission_classes = [IsAuthenticated, CanRespondToTicket]
    
    def post(self, request, ticket_id):
        serializer = CreateMessageSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        message_text = serializer.validated_data['message']
        attachments = serializer.validated_data.get('attachments', [])
        
        try:
            # Get ticket
            ticket = get_object_or_404(SupportTicket, ticket_id=ticket_id)
            
            # Check permissions
            if request.user.role != 'ADMIN' and ticket.user != request.user:
                return Response(
                    {'error': 'Permission denied'},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            # Create message
            message = SupportMessage.objects.create(
                ticket=ticket,
                sender=request.user,
                is_admin=(request.user.role == 'ADMIN'),
                message=message_text,
                attachments=attachments
            )
            
            # Update ticket
            ticket.increment_message_count()
            
            # Update ticket status
            if request.user.role == 'ADMIN':
                if ticket.status == SupportTicket.TicketStatus.OPEN:
                    ticket.status = SupportTicket.TicketStatus.IN_PROGRESS
            else:
                if ticket.status == SupportTicket.TicketStatus.RESOLVED:
                    ticket.status = SupportTicket.TicketStatus.IN_PROGRESS
            
            ticket.save()
            
            # Send notification
            self.send_notification(ticket, message)
            
            return Response(
                SupportMessageSerializer(message).data,
                status=status.HTTP_201_CREATED
            )
            
        except SupportTicket.DoesNotExist:
            return Response(
                {'error': 'Ticket not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            logger.error(f"Error replying to ticket: {str(e)}")
            return Response(
                {'error': 'Failed to send reply'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def send_notification(self, ticket, message):
        """Send notification about new message"""
        try:
            from notifications.utils import create_notification
            
            # Determine recipient
            if message.is_admin:
                # Admin replied, notify user
                recipient = ticket.user
                notification_type = 'SYSTEM_UPDATE'
                title = 'New Reply to Your Support Ticket'
                notification_message = f'Admin has replied to your ticket: {ticket.subject}'
            else:
                # User replied, notify admins
                recipient = None  # Will notify all admins
                notification_type = 'SYSTEM_UPDATE'
                title = 'New Customer Reply'
                notification_message = f'Customer replied to ticket: {ticket.subject}'
            
            if recipient:
                create_notification(
                    user=recipient,
                    notification_type=notification_type,
                    title=title,
                    message=notification_message,
                    metadata={
                        'ticket_id': str(ticket.ticket_id),
                        'message_preview': message.message[:100]
                    }
                )
            else:
                # Notify all admins
                from django.contrib.auth import get_user_model
                User = get_user_model()
                admins = User.objects.filter(role='ADMIN', is_active=True)
                
                for admin in admins:
                    create_notification(
                        user=admin,
                        notification_type=notification_type,
                        title=title,
                        message=notification_message,
                        metadata={
                            'ticket_id': str(ticket.ticket_id),
                            'user': ticket.user.email
                        }
                    )
                    
        except ImportError:
            logger.warning("Notifications app not installed")


class CloseTicketView(APIView):
    """
    Close a support ticket
    """
    permission_classes = [IsAuthenticated, IsOwnerOrAdmin]
    
    def post(self, request, ticket_id):
        try:
            ticket = get_object_or_404(SupportTicket, ticket_id=ticket_id)
            
            # Check permissions
            if request.user.role != 'ADMIN' and ticket.user != request.user:
                return Response(
                    {'error': 'Permission denied'},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            ticket.close_ticket(request.user)
            
            return Response({
                'message': 'Ticket closed successfully',
                'ticket': SupportTicketSerializer(ticket).data
            }, status=status.HTTP_200_OK)
            
        except SupportTicket.DoesNotExist:
            return Response(
                {'error': 'Ticket not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            logger.error(f"Error closing ticket: {str(e)}")
            return Response(
                {'error': 'Failed to close ticket'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class FAQListView(generics.ListAPIView):
    """
    Get published FAQs
    """
    permission_classes = []  # Public access
    serializer_class = FAQSerializer
    
    def get_queryset(self):
        queryset = FAQ.objects.filter(is_published=True)
        
        # Filter by category if provided
        category = self.request.query_params.get('category', None)
        if category:
            queryset = queryset.filter(category=category)
        
        # Search if query provided
        search_query = self.request.query_params.get('search', None)
        if search_query:
            queryset = queryset.filter(
                Q(question__icontains=search_query) |
                Q(answer__icontains=search_query)
            )
        
        return queryset.order_by('category', 'display_order')


class FAQDetailView(generics.RetrieveAPIView):
    """
    Get FAQ details
    """
    permission_classes = []  # Public access
    serializer_class = FAQSerializer
    queryset = FAQ.objects.filter(is_published=True)
    
    def retrieve(self, request, *args, **kwargs):
        # Increment view count
        instance = self.get_object()
        instance.increment_views()
        return super().retrieve(request, *args, **kwargs)


class MarkFAQHelpfulView(APIView):
    """
    Mark FAQ as helpful
    """
    permission_classes = []  # Public access
    
    def post(self, request, pk):
        try:
            faq = get_object_or_404(FAQ, pk=pk, is_published=True)
            faq.mark_helpful()
            
            return Response({
                'message': 'Thank you for your feedback!',
                'helpful_count': faq.helpful_count
            }, status=status.HTTP_200_OK)
            
        except FAQ.DoesNotExist:
            return Response(
                {'error': 'FAQ not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            logger.error(f"Error marking FAQ helpful: {str(e)}")
            return Response(
                {'error': 'Failed to process feedback'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


# Admin Views

class AdminTicketListView(generics.ListAPIView):
    """
    Admin: List all support tickets
    """
    permission_classes = [IsAuthenticated, AdminOnly]
    serializer_class = SupportTicketSerializer
    queryset = SupportTicket.objects.all().order_by('-created_at')
    
    def get_queryset(self):
        queryset = SupportTicket.objects.all()
        
        # Filter by status
        status = self.request.query_params.get('status', None)
        if status:
            queryset = queryset.filter(status=status)
        
        # Filter by priority
        priority = self.request.query_params.get('priority', None)
        if priority:
            queryset = queryset.filter(priority=priority)
        
        # Filter by category
        category = self.request.query_params.get('category', None)
        if category:
            queryset = queryset.filter(category=category)
        
        # Filter by user email
        user_email = self.request.query_params.get('user_email', None)
        if user_email:
            queryset = queryset.filter(user__email__icontains=user_email)
        
        # Filter by assigned admin
        assigned_to = self.request.query_params.get('assigned_to', None)
        if assigned_to:
            queryset = queryset.filter(assigned_to__email__icontains=assigned_to)
        
        # Filter by date range
        start_date = self.request.query_params.get('start_date', None)
        end_date = self.request.query_params.get('end_date', None)
        
        if start_date:
            queryset = queryset.filter(created_at__date__gte=start_date)
        if end_date:
            queryset = queryset.filter(created_at__date__lte=end_date)
        
        return queryset.order_by('-created_at')


class AdminUpdateTicketStatusView(APIView):
    """
    Admin: Update ticket status
    """
    permission_classes = [IsAuthenticated, AdminOnly]
    
    def post(self, request, ticket_id):
        serializer = UpdateTicketStatusSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        status = serializer.validated_data['status']
        resolution = serializer.validated_data.get('resolution', '')
        
        try:
            ticket = get_object_or_404(SupportTicket, ticket_id=ticket_id)
            
            ticket.status = status
            if resolution:
                ticket.resolution = resolution
            
            if status == SupportTicket.TicketStatus.RESOLVED:
                ticket.resolved_by = request.user
                ticket.resolved_at = timezone.now()
            
            ticket.save()
            
            # Create status update message
            SupportMessage.objects.create(
                ticket=ticket,
                sender=request.user,
                is_admin=True,
                message=f'Ticket status updated to {status}. {resolution}'
            )
            
            ticket.increment_message_count()
            
            # Send notification to user
            try:
                from notifications.utils import create_notification
                create_notification(
                    user=ticket.user,
                    notification_type='SYSTEM_UPDATE',
                    title='Ticket Status Updated',
                    message=f'Your ticket "{ticket.subject}" has been updated to {status}.',
                    metadata={
                        'ticket_id': str(ticket.ticket_id),
                        'status': status,
                        'admin': request.user.email
                    }
                )
            except ImportError:
                logger.warning("Notifications app not installed")
            
            return Response({
                'message': f'Ticket status updated to {status}',
                'ticket': SupportTicketSerializer(ticket).data
            }, status=status.HTTP_200_OK)
            
        except SupportTicket.DoesNotExist:
            return Response(
                {'error': 'Ticket not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            logger.error(f"Error updating ticket status: {str(e)}")
            return Response(
                {'error': 'Failed to update ticket status'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class AdminAssignTicketView(APIView):
    """
    Admin: Assign ticket to another admin
    """
    permission_classes = [IsAuthenticated, AdminOnly]
    
    def post(self, request, ticket_id):
        serializer = AssignTicketSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        admin_id = serializer.validated_data['admin_id']
        
        try:
            from django.contrib.auth import get_user_model
            User = get_user_model()
            admin = User.objects.get(id=admin_id, role='ADMIN', is_active=True)
            
            ticket = get_object_or_404(SupportTicket, ticket_id=ticket_id)
            
            ticket.assigned_to = admin
            ticket.save()
            
            # Create assignment message
            SupportMessage.objects.create(
                ticket=ticket,
                sender=request.user,
                is_admin=True,
                message=f'Ticket assigned to {admin.email}'
            )
            
            ticket.increment_message_count()
            
            # Send notification to assigned admin
            try:
                from notifications.utils import create_notification
                create_notification(
                    user=admin,
                    notification_type='SYSTEM_UPDATE',
                    title='Ticket Assigned to You',
                    message=f'You have been assigned to ticket: {ticket.subject}',
                    metadata={
                        'ticket_id': str(ticket.ticket_id),
                        'assigned_by': request.user.email,
                        'customer': ticket.user.email
                    }
                )
            except ImportError:
                logger.warning("Notifications app not installed")
            
            return Response({
                'message': f'Ticket assigned to {admin.email}',
                'ticket': SupportTicketSerializer(ticket).data
            }, status=status.HTTP_200_OK)
            
        except User.DoesNotExist:
            return Response(
                {'error': 'Admin user not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        except SupportTicket.DoesNotExist:
            return Response(
                {'error': 'Ticket not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            logger.error(f"Error assigning ticket: {str(e)}")
            return Response(
                {'error': 'Failed to assign ticket'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class AdminTicketStatsView(APIView):
    """
    Admin: Get support ticket statistics
    """
    permission_classes = [IsAuthenticated, AdminOnly]
    
    def get(self, request):
        try:
            # Overall statistics
            total_tickets = SupportTicket.objects.count()
            open_tickets = SupportTicket.objects.filter(status='OPEN').count()
            in_progress_tickets = SupportTicket.objects.filter(status='IN_PROGRESS').count()
            resolved_tickets = SupportTicket.objects.filter(status='RESOLVED').count()
            closed_tickets = SupportTicket.objects.filter(status='CLOSED').count()
            
            # Calculate average response time
            resolved_tickets_with_response = SupportTicket.objects.filter(
                status__in=['RESOLVED', 'CLOSED'],
                resolved_at__isnull=False
            )
            
            if resolved_tickets_with_response.exists():
                response_times = []
                for ticket in resolved_tickets_with_response:
                    # Find first admin response
                    first_admin_response = SupportMessage.objects.filter(
                        ticket=ticket,
                        is_admin=True
                    ).order_by('created_at').first()
                    
                    if first_admin_response:
                        response_time = (first_admin_response.created_at - ticket.created_at).total_seconds() / 3600  # hours
                        response_times.append(response_time)
                
                average_response_time = sum(response_times) / len(response_times) if response_times else 0
            else:
                average_response_time = 0
            
            # Category distribution
            category_distribution = {}
            for category in SupportTicket.TicketCategory.choices:
                count = SupportTicket.objects.filter(category=category[0]).count()
                category_distribution[category[1]] = count
            
            # Monthly ticket creation
            monthly_tickets = []
            for i in range(6):  # Last 6 months
                month = timezone.now() - timezone.timedelta(days=30*i)
                month_start = month.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
                month_end = (month_start + timezone.timedelta(days=32)).replace(day=1) - timezone.timedelta(days=1)
                
                month_tickets = SupportTicket.objects.filter(
                    created_at__range=[month_start, month_end]
                )
                
                monthly_tickets.append({
                    'month': month_start.strftime('%Y-%m'),
                    'new_tickets': month_tickets.count(),
                    'resolved_tickets': month_tickets.filter(status__in=['RESOLVED', 'CLOSED']).count()
                })
            
            stats = {
                'overall': {
                    'total_tickets': total_tickets,
                    'open_tickets': open_tickets,
                    'in_progress_tickets': in_progress_tickets,
                    'resolved_tickets': resolved_tickets,
                    'closed_tickets': closed_tickets,
                    'average_response_time': round(average_response_time, 2)
                },
                'category_distribution': category_distribution,
                'monthly_tickets': monthly_tickets,
                'top_users': self.get_top_users(),
                'admin_performance': self.get_admin_performance()
            }
            
            return Response(stats, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"Error getting ticket stats: {str(e)}")
            return Response(
                {'error': 'Failed to get ticket statistics'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def get_top_users(self):
        """Get users with most tickets"""
        from django.contrib.auth import get_user_model
        User = get_user_model()
        
        top_users = User.objects.annotate(
            ticket_count=Count('support_tickets')
        ).filter(ticket_count__gt=0).order_by('-ticket_count')[:10]
        
        return [
            {
                'user': user.email,
                'ticket_count': user.ticket_count,
                'last_ticket': user.support_tickets.order_by('-created_at').first().created_at if user.support_tickets.exists() else None
            }
            for user in top_users
        ]
    
    def get_admin_performance(self):
        """Get admin performance metrics"""
        from django.contrib.auth import get_user_model
        User = get_user_model()
        
        admins = User.objects.filter(role='ADMIN', is_active=True)
        
        performance = []
        for admin in admins:
            resolved_tickets = SupportTicket.objects.filter(resolved_by=admin).count()
            assigned_tickets = SupportTicket.objects.filter(assigned_to=admin).count()
            admin_messages = SupportMessage.objects.filter(sender=admin, is_admin=True).count()
            
            performance.append({
                'admin': admin.email,
                'resolved_tickets': resolved_tickets,
                'assigned_tickets': assigned_tickets,
                'admin_messages': admin_messages
            })
        
        return performance


class AdminDepartmentListView(generics.ListCreateAPIView):
    """
    Admin: List and create support departments
    """
    permission_classes = [IsAuthenticated, AdminOnly]
    serializer_class = SupportDepartmentSerializer
    queryset = SupportDepartment.objects.all().order_by('name')


class AdminDepartmentDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    Admin: Manage support department
    """
    permission_classes = [IsAuthenticated, AdminOnly]
    serializer_class = SupportDepartmentSerializer
    queryset = SupportDepartment.objects.all()


class AdminFAQListView(generics.ListCreateAPIView):
    """
    Admin: List and create FAQs
    """
    permission_classes = [IsAuthenticated, AdminOnly]
    serializer_class = FAQSerializer
    queryset = FAQ.objects.all().order_by('category', 'display_order')


class AdminFAQDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    Admin: Manage FAQ
    """
    permission_classes = [IsAuthenticated, AdminOnly]
    serializer_class = FAQSerializer
    queryset = FAQ.objects.all()

