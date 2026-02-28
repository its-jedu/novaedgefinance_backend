import random
import string
from datetime import timedelta
from django.utils import timezone
from django.core.mail import send_mail
from django.conf import settings
import resend
import logging

logger = logging.getLogger(__name__)

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


def send_email_via_resend(to_email, subject, html_content, text_content=None):
    """
    Send email using Resend.com with proper format
    """
    if not settings.RESEND_API_KEY:
        logger.warning("RESEND_API_KEY not set. Email not sent.")
        print(f"[EMAIL SIMULATION] To: {to_email}")
        print(f"Subject: {subject}")
        print(f"Content: {html_content}")
        return False
    
    try:
        resend.api_key = settings.RESEND_API_KEY
        
        # Format the from address properly
        from_email = settings.EMAIL_FROM_ADDRESS
        
        # If it's not already formatted with name, format it
        if '<' not in from_email:
            from_email = f"NovaEdge Finance <{from_email}>"
        
        params = {
            "from": from_email,
            "to": [to_email],
            "subject": subject,
            "html": html_content,
        }
        
        if text_content:
            params["text"] = text_content
            
        # Using the correct Resend API format
        email = resend.Emails.send(params)
        logger.info(f"Email sent to {to_email}: {email}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to send email to {to_email}: {str(e)}")
        return False

def send_verification_email(user_email, user_name, token):
    """
    Send email verification link
    """
    verification_link = f"http://localhost:5173/auth/verify-email?token={token}"
    
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
    </head>
    <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px;">
        <div style="background: linear-gradient(to right, #2563eb, #06b6d4); padding: 30px; text-align: center; border-radius: 10px 10px 0 0;">
            <h1 style="color: white; margin: 0; font-size: 28px;">NovaEdge Finance</h1>
            <p style="color: white; opacity: 0.9; margin-top: 10px;">Smart Crypto Investing Starts Here</p>
        </div>
        
        <div style="background: #f9fafb; padding: 30px; border-radius: 0 0 10px 10px; border: 1px solid #e5e7eb;">
            <h2 style="color: #1f2937; margin-top: 0;">Verify Your Email Address</h2>
            
            <p>Hello <strong>{user_name}</strong>,</p>
            
            <p>Thank you for registering with NovaEdge Finance! Please verify your email address by clicking the button below:</p>
            
            <div style="text-align: center; margin: 30px 0;">
                <a href="{verification_link}" style="background: linear-gradient(to right, #2563eb, #06b6d4); color: white; padding: 14px 28px; text-decoration: none; border-radius: 8px; font-weight: bold; display: inline-block;">Verify Email Address</a>
            </div>
            
            <p>Or copy and paste this link in your browser:</p>
            <p style="background: #e5e7eb; padding: 10px; border-radius: 5px; word-break: break-all; font-size: 14px;">{verification_link}</p>
            
            <p>This link will expire in <strong>24 hours</strong>.</p>
            
            <p>If you didn't create an account with NovaEdge Finance, please ignore this email.</p>
            
            <hr style="border: none; border-top: 1px solid #e5e7eb; margin: 30px 0;">
            
            <p style="color: #6b7280; font-size: 14px; text-align: center;">
                &copy; 2026 NovaEdge Finance. All rights reserved.<br>
                This is an automated message, please do not reply.
            </p>
        </div>
    </body>
    </html>
    """
    
    text_content = f"""
    NovaEdge Finance - Verify Your Email
    
    Hello {user_name},
    
    Thank you for registering with NovaEdge Finance! Please verify your email address by clicking the link below:
    
    {verification_link}
    
    This link will expire in 24 hours.
    
    If you didn't create an account with NovaEdge Finance, please ignore this email.
    
    © 2026 NovaEdge Finance. All rights reserved.
    """
    
    return send_email_via_resend(
        to_email=user_email,
        subject="Verify Your Email - NovaEdge Finance",
        html_content=html_content,
        text_content=text_content
    )

