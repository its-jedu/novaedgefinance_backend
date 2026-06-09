import random
import string
from datetime import timedelta
from django.utils import timezone
from django.core.mail import send_mail, EmailMultiAlternatives
from django.conf import settings
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
    print(f"[SMS SIMULATION] To: {phone_number}, Message: {message}")
    return True

def send_email_notification(subject, message, recipient_list):
    """Send email notifications using SMTP."""
    try:
        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=recipient_list,
            fail_silently=False,
        )
        logger.info(f"Email notification sent to {recipient_list}")
        return True
    except Exception as e:
        logger.error(f"Failed to send email notification: {str(e)}")
        return False

def check_rate_limit(user, max_attempts=5, lockout_minutes=15):
    """Check if user is rate limited."""
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

def send_verification_email(user_email, user_name, token):
    """Send email verification link using SMTP."""
    try:
        from django.contrib.auth import get_user_model
        User = get_user_model()
        
        # Check if user exists and if email is already verified
        try:
            user = User.objects.get(email=user_email)
            
            # Don't send verification email if already verified
            if user.email_verified:
                logger.info(f"Email {user_email} is already verified. Skipping verification email.")
                return True
            
            # Check if user is active
            if not user.is_active:
                logger.warning(f"Cannot send verification email to inactive user: {user_email}")
                return False
                
        except User.DoesNotExist:
            logger.warning(f"User with email {user_email} does not exist. Cannot send verification email.")
            return False
        
        frontend_url = settings.FRONTEND_URL
        # Point to frontend verification page (matches App.jsx route: /api/auth/verify-email)
        verification_link = f"{frontend_url}/api/auth/verify-email?token={token}"
        
        company_name = settings.COMPANY_NAME
        company_tagline = settings.COMPANY_TAGLINE
        current_year = timezone.now().year
        
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
        </head>
        <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px;">
            <div style="background: linear-gradient(to right, #2563eb, #06b6d4); padding: 30px; text-align: center; border-radius: 10px 10px 0 0;">
                <h1 style="color: white; margin: 0; font-size: 28px;">{company_name}</h1>
                <p style="color: white; opacity: 0.9; margin-top: 10px;">{company_tagline}</p>
            </div>
            
            <div style="background: #f9fafb; padding: 30px; border-radius: 0 0 10px 10px; border: 1px solid #e5e7eb;">
                <h2 style="color: #1f2937; margin-top: 0;">Verify Your Email Address</h2>
                
                <p>Hello <strong>{user_name}</strong>,</p>
                
                <p>Thank you for registering with {company_name}! Please verify your email address by clicking the button below:</p>
                
                <div style="text-align: center; margin: 30px 0;">
                    <a href="{verification_link}" style="background: linear-gradient(to right, #2563eb, #06b6d4); color: white; padding: 14px 28px; text-decoration: none; border-radius: 8px; font-weight: bold; display: inline-block;">Verify Email Address</a>
                </div>
                
                <p>Or copy and paste this link in your browser:</p>
                <p style="background: #e5e7eb; padding: 10px; border-radius: 5px; word-break: break-all; font-size: 14px;">{verification_link}</p>
                
                <p>This link will expire in <strong>24 hours</strong>.</p>
                
                <p>If you didn't create an account with {company_name}, please ignore this email.</p>
                
                <hr style="border: none; border-top: 1px solid #e5e7eb; margin: 30px 0;">
                
                <p style="color: #6b7280; font-size: 14px; text-align: center;">
                    &copy; {current_year} {company_name}. All rights reserved.<br>
                    This is an automated message, please do not reply.
                </p>
            </div>
        </body>
        </html>
        """
        
        text_content = f"""
        {company_name} - Verify Your Email
        
        Hello {user_name},
        
        Thank you for registering with {company_name}! Please verify your email address by clicking the link below:
        
        {verification_link}
        
        This link will expire in 24 hours.
        
        If you didn't create an account with {company_name}, please ignore this email.
        
        © {current_year} {company_name}. All rights reserved.
        """
        
        try:
            email_message = EmailMultiAlternatives(
                subject=f"Verify Your Email - {company_name}",
                body=text_content,
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=[user_email],
            )
            email_message.attach_alternative(html_content, "text/html")
            email_message.send(fail_silently=False)
            logger.info(f"Verification email sent to {user_email}")
            return True
        except Exception as e:
            logger.error(f"Failed to send verification email to {user_email}: {str(e)}")
            return False
            
    except Exception as e:
        logger.error(f"Error in send_verification_email for {user_email}: {str(e)}")
        return False


def send_password_reset_email(user_email, user_name, token):
    """Send password reset email using SMTP."""
    try:
        from django.contrib.auth import get_user_model
        User = get_user_model()
        
        # Check if user exists
        try:
            user = User.objects.get(email=user_email)
            
            # Check if email is verified
            if not user.email_verified:
                logger.warning(f"Cannot send password reset to unverified email: {user_email}")
                return False
            
            # Check if user is active
            if not user.is_active:
                logger.warning(f"Cannot send password reset to inactive user: {user_email}")
                return False
                
        except User.DoesNotExist:
            logger.warning(f"User with email {user_email} does not exist. Cannot send password reset.")
            return False
        
        frontend_url = settings.FRONTEND_URL
        # Point to frontend reset password page
        reset_link = f"{frontend_url}/api/auth/reset-password?token={token}"
        
        company_name = settings.COMPANY_NAME
        current_year = timezone.now().year
        
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
        </head>
        <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px;">
            <div style="background: linear-gradient(to right, #dc2626, #ef4444); padding: 30px; text-align: center; border-radius: 10px 10px 0 0;">
                <h1 style="color: white; margin: 0; font-size: 28px;">{company_name}</h1>
                <p style="color: white; opacity: 0.9; margin-top: 10px;">Password Reset Request</p>
            </div>
            
            <div style="background: #f9fafb; padding: 30px; border-radius: 0 0 10px 10px; border: 1px solid #e5e7eb;">
                <h2 style="color: #1f2937; margin-top: 0;">Reset Your Password</h2>
                
                <p>Hello <strong>{user_name}</strong>,</p>
                
                <p>We received a request to reset your password. Click the button below to set a new password:</p>
                
                <div style="text-align: center; margin: 30px 0;">
                    <a href="{reset_link}" style="background: linear-gradient(to right, #dc2626, #ef4444); color: white; padding: 14px 28px; text-decoration: none; border-radius: 8px; font-weight: bold; display: inline-block;">Reset Password</a>
                </div>
                
                <p>Or copy and paste this link in your browser:</p>
                <p style="background: #e5e7eb; padding: 10px; border-radius: 5px; word-break: break-all; font-size: 14px;">{reset_link}</p>
                
                <p>This link will expire in <strong>24 hours</strong>.</p>
                
                <p style="color: #dc2626; font-weight: bold;">If you didn't request a password reset, please ignore this email or contact support immediately.</p>
                
                <hr style="border: none; border-top: 1px solid #e5e7eb; margin: 30px 0;">
                
                <p style="color: #6b7280; font-size: 14px; text-align: center;">
                    &copy; {current_year} {company_name}. All rights reserved.<br>
                    This is an automated message, please do not reply.
                </p>
            </div>
        </body>
        </html>
        """
        
        text_content = f"""
        {company_name} - Reset Your Password
        
        Hello {user_name},
        
        We received a request to reset your password. Click the link below to set a new password:
        
        {reset_link}
        
        This link will expire in 24 hours.
        
        If you didn't request a password reset, please ignore this email.
        
        © {current_year} {company_name}. All rights reserved.
        """
        
        try:
            email_message = EmailMultiAlternatives(
                subject=f"Reset Your Password - {company_name}",
                body=text_content,
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=[user_email],
            )
            email_message.attach_alternative(html_content, "text/html")
            email_message.send(fail_silently=False)
            logger.info(f"Password reset email sent to {user_email}")
            return True
        except Exception as e:
            logger.error(f"Failed to send password reset email to {user_email}: {str(e)}")
            return False
            
    except Exception as e:
        logger.error(f"Error in send_password_reset_email for {user_email}: {str(e)}")
        return False


def send_welcome_email(user_email, user_name):
    """Send welcome email after successful email verification."""
    try:
        from django.contrib.auth import get_user_model
        User = get_user_model()
        
        # Check if user exists and is verified
        try:
            user = User.objects.get(email=user_email)
            if not user.email_verified:
                logger.warning(f"Cannot send welcome email to unverified user: {user_email}")
                return False
        except User.DoesNotExist:
            logger.warning(f"User with email {user_email} does not exist.")
            return False
        
        frontend_url = settings.FRONTEND_URL
        login_link = f"{frontend_url}/api/auth/login"
        company_name = settings.COMPANY_NAME
        company_tagline = settings.COMPANY_TAGLINE
        current_year = timezone.now().year
        
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
        </head>
        <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px;">
            <div style="background: linear-gradient(to right, #059669, #10b981); padding: 30px; text-align: center; border-radius: 10px 10px 0 0;">
                <h1 style="color: white; margin: 0; font-size: 28px;">Welcome to {company_name}!</h1>
                <p style="color: white; opacity: 0.9; margin-top: 10px;">{company_tagline}</p>
            </div>
            
            <div style="background: #f9fafb; padding: 30px; border-radius: 0 0 10px 10px; border: 1px solid #e5e7eb;">
                <h2 style="color: #1f2937; margin-top: 0;">Your Email is Verified! 🎉</h2>
                
                <p>Hello <strong>{user_name}</strong>,</p>
                
                <p>Congratulations! Your email has been verified successfully. You now have full access to your {company_name} account.</p>
                
                <div style="text-align: center; margin: 30px 0;">
                    <a href="{login_link}" style="background: linear-gradient(to right, #059669, #10b981); color: white; padding: 14px 28px; text-decoration: none; border-radius: 8px; font-weight: bold; display: inline-block;">Login to Your Account</a>
                </div>
                
                <p>Here's what you can do now:</p>
                <ul style="padding-left: 20px;">
                    <li>Complete your investment profile</li>
                    <li>Browse available investment plans</li>
                    <li>Make your first deposit</li>
                    <li>Start earning returns on your investments</li>
                </ul>
                
                <p>If you have any questions, feel free to contact our support team.</p>
                
                <hr style="border: none; border-top: 1px solid #e5e7eb; margin: 30px 0;">
                
                <p style="color: #6b7280; font-size: 14px; text-align: center;">
                    &copy; {current_year} {company_name}. All rights reserved.<br>
                    This is an automated message, please do not reply.
                </p>
            </div>
        </body>
        </html>
        """
        
        text_content = f"""
        Welcome to {company_name}!
        
        Hello {user_name},
        
        Congratulations! Your email has been verified successfully. You now have full access to your {company_name} account.
        
        Login to your account: {login_link}
        
        Here's what you can do now:
        - Complete your investment profile
        - Browse available investment plans
        - Make your first deposit
        - Start earning returns on your investments
        
        If you have any questions, feel free to contact our support team.
        
        © {current_year} {company_name}. All rights reserved.
        """
        
        try:
            email_message = EmailMultiAlternatives(
                subject=f"Welcome to {company_name}!",
                body=text_content,
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=[user_email],
            )
            email_message.attach_alternative(html_content, "text/html")
            email_message.send(fail_silently=False)
            logger.info(f"Welcome email sent to {user_email}")
            return True
        except Exception as e:
            logger.error(f"Failed to send welcome email to {user_email}: {str(e)}")
            return False
            
    except Exception as e:
        logger.error(f"Error in send_welcome_email for {user_email}: {str(e)}")
        return False


def send_login_alert_email(user_email, user_name, ip_address, device_info):
    """Send login alert email for security."""
    try:
        frontend_url = settings.FRONTEND_URL
        company_name = settings.COMPANY_NAME
        current_year = timezone.now().year
        login_time = timezone.now().strftime("%B %d, %Y at %I:%M %p UTC")
        
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
        </head>
        <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px;">
            <div style="background: linear-gradient(to right, #2563eb, #06b6d4); padding: 30px; text-align: center; border-radius: 10px 10px 0 0;">
                <h1 style="color: white; margin: 0; font-size: 28px;">{company_name}</h1>
                <p style="color: white; opacity: 0.9; margin-top: 10px;">Security Alert - New Login</p>
            </div>
            
            <div style="background: #f9fafb; padding: 30px; border-radius: 0 0 10px 10px; border: 1px solid #e5e7eb;">
                <h2 style="color: #1f2937; margin-top: 0;">New Login Detected</h2>
                
                <p>Hello <strong>{user_name}</strong>,</p>
                
                <p>We detected a new login to your account:</p>
                
                <div style="background: #e5e7eb; padding: 15px; border-radius: 8px; margin: 20px 0;">
                    <p style="margin: 5px 0;"><strong>Time:</strong> {login_time}</p>
                    <p style="margin: 5px 0;"><strong>IP Address:</strong> {ip_address}</p>
                    <p style="margin: 5px 0;"><strong>Device:</strong> {device_info}</p>
                </div>
                
                <p>If this was you, you can ignore this email.</p>
                
                <p style="color: #dc2626; font-weight: bold;">If this wasn't you, please change your password immediately and contact support.</p>
                
                <hr style="border: none; border-top: 1px solid #e5e7eb; margin: 30px 0;">
                
                <p style="color: #6b7280; font-size: 14px; text-align: center;">
                    &copy; {current_year} {company_name}. All rights reserved.<br>
                    This is an automated security alert.
                </p>
            </div>
        </body>
        </html>
        """
        
        text_content = f"""
        {company_name} - Security Alert
        
        Hello {user_name},
        
        We detected a new login to your account:
        
        Time: {login_time}
        IP Address: {ip_address}
        Device: {device_info}
        
        If this was you, you can ignore this email.
        
        If this wasn't you, please change your password immediately and contact support.
        
        © {current_year} {company_name}. All rights reserved.
        """
        
        try:
            email_message = EmailMultiAlternatives(
                subject=f"New Login Alert - {company_name}",
                body=text_content,
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=[user_email],
            )
            email_message.attach_alternative(html_content, "text/html")
            email_message.send(fail_silently=False)
            logger.info(f"Login alert email sent to {user_email}")
            return True
        except Exception as e:
            logger.error(f"Failed to send login alert email to {user_email}: {str(e)}")
            return False
            
    except Exception as e:
        logger.error(f"Error in send_login_alert_email for {user_email}: {str(e)}")
        return False