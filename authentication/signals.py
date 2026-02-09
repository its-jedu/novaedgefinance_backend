from django.db.models.signals import post_save
from django.dispatch import receiver
from django.conf import settings
from .models import User
from .utils import send_email_notification

@receiver(post_save, sender=User)
def user_post_save(sender, instance, created, **kwargs):
    """
    Send notifications on user events.
    """
    if created:
        # Send welcome email
        send_email_notification(
            subject=f"Welcome to NovaEdgeFinance, {instance.first_name}!",
            message=f"""
            Hello {instance.get_full_name()},
            
            Welcome to NovaEdgeFinance! Your account has been created successfully.
            Please verify your phone number to activate your account.
            
            Best regards,
            NovaEdgeFinance Team
            """,
            recipient_list=[instance.email]
        )
    elif instance.is_active is False and 'is_active' in kwargs['update_fields']:
        # Send suspension email
        send_email_notification(
            subject="Account Suspended - NovaEdgeFinance",
            message=f"""
            Dear {instance.get_full_name()},
            
            Your NovaEdgeFinance account has been suspended.
            Please contact support for more information.
            
            Best regards,
            NovaEdgeFinance Team
            """,
            recipient_list=[instance.email]
        )