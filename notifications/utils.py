import logging
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.conf import settings
from .models import Notification, NotificationTemplate

logger = logging.getLogger(__name__)

def send_notification_email(notification):
    """
    Send email for a notification
    """
    try:
        # Get template for notification type
        try:
            template = NotificationTemplate.objects.get(
                notification_type=notification.notification_type,
                is_active=True
            )
        except NotificationTemplate.DoesNotExist:
            # Use default template
            subject = notification.title
            html_message = f"""
            <html>
            <body>
                <h2>{notification.title}</h2>
                <p>{notification.message}</p>
                <hr>
                <p>This is an automated message from NovaEdgeFinance.</p>
            </body>
            </html>
            """
        else:
            # Render template with variables
            context = {
                'user': notification.user,
                'notification': notification,
                'title': notification.title,
                'message': notification.message,
                'metadata': notification.metadata,
                'site_url': getattr(settings, 'SITE_URL', 'https://novaedgefinance.com'),
                'support_email': getattr(settings, 'SUPPORT_EMAIL', 'support@novaedgefinance.com')
            }
            
            subject = template.subject
            html_message = render_to_string(
                template_string=template.html_template,
                context=context
            )
        
        # Create plain text version
        plain_message = strip_tags(html_message)
        
        # Send email
        from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@novaedgefinance.com')
        recipient_list = [notification.user.email]
        
        send_mail(
            subject=subject,
            message=plain_message,
            from_email=from_email,
            recipient_list=recipient_list,
            html_message=html_message,
            fail_silently=False
        )
        
        logger.info(f"Notification email sent to {notification.user.email}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to send notification email: {str(e)}")
        notification.mark_as_failed(str(e))
        return False


def send_template_email(to_email, template, variables=None):
    """
    Send email using a template
    """
    try:
        if variables is None:
            variables = {}
        
        # Render template
        context = {
            **variables,
            'site_url': getattr(settings, 'SITE_URL', 'https://novaedgefinance.com'),
            'support_email': getattr(settings, 'SUPPORT_EMAIL', 'support@novaedgefinance.com')
        }
        
        html_message = render_to_string(
            template_string=template.html_template,
            context=context
        )
        
        plain_message = render_to_string(
            template_string=template.text_template,
            context=context
        )
        
        # Send email
        from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@novaedgefinance.com')
        recipient_list = [to_email]
        
        send_mail(
            subject=template.subject,
            message=plain_message,
            from_email=from_email,
            recipient_list=recipient_list,
            html_message=html_message,
            fail_silently=False
        )
        
        logger.info(f"Template email sent to {to_email}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to send template email: {str(e)}")
        return False


def create_notification(user, notification_type, title, message, metadata=None):
    """
    Create and send notification
    """
    try:
        notification = Notification.objects.create(
            user=user,
            notification_type=notification_type,
            title=title,
            message=message,
            metadata=metadata or {},
            status=Notification.NotificationStatus.PENDING
        )
        
        # Send email asynchronously (in production, use Celery)
        # For now, send immediately
        success = send_notification_email(notification)
        
        if success:
            notification.mark_as_sent()
        else:
            notification.mark_as_failed("Failed to send email")
        
        return notification
        
    except Exception as e:
        logger.error(f"Failed to create notification: {str(e)}")
        return None