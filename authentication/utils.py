import random
import string
from datetime import timedelta
from django.utils import timezone
from django.core.mail import send_mail
from django.conf import settings

def generate_verification_code(length=6):
    """Generate a random numeric verification code."""
    return ''.join(random.choices(string.digits, k=length))

def send_sms(phone_number, message):
    """
    Placeholder for SMS sending function.
    Integrate with services like Twilio, AWS SNS, etc.
    """
    # For MVP, we'll just print
    print(f"[SMS SIMULATION] To: {phone_number}, Message: {message}")
    
    # Example with Twilio (uncomment and configure):
    # from twilio.rest import Client
    # client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
    # message = client.messages.create(
    #     body=message,
    #     from_=settings.TWILIO_PHONE_NUMBER,
    #     to=phone_number
    # )
    return True

def send_email_notification(subject, message, recipient_list):
    """
    Send email notifications.
    """
    if settings.DEBUG:
        print(f"[EMAIL SIMULATION] To: {recipient_list}, Subject: {subject}, Message: {message}")
    else:
        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=recipient_list,
            fail_silently=False,
        )

def check_rate_limit(user, max_attempts=5, lockout_minutes=15):
    """
    Check if user is rate limited.
    """
    if user.is_locked():
        remaining_time = user.locked_until - timezone.now()
        return {
            'locked': True,
            'remaining_seconds': remaining_time.total_seconds(),
            'message': f'Account locked. Try again in {remaining_time.seconds // 60} minutes.'
        }
    
    if user.failed_login_attempts >= max_attempts:
        user.locked_until = timezone.now() + timedelta(minutes=lockout_minutes)
        user.save()
        return {
            'locked': True,
            'remaining_seconds': lockout_minutes * 60,
            'message': f'Account locked for {lockout_minutes} minutes.'
        }
    
    return {'locked': False}