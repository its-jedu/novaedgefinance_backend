from rest_framework import status, generics
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import authenticate
from django.utils import timezone
from django.db.models import Count, Sum, Q, Avg
from django.core.cache import cache
from datetime import datetime, timedelta
import time
import secrets
import logging

from .models import User, InvestmentProfile
from .serializers import (
    UserRegistrationSerializer, UserLoginSerializer,
    EmailVerificationSerializer, UserProfileSerializer, 
    AdminUserUpdateSerializer, PasswordChangeSerializer,
    ResendVerificationSerializer, ProfileCompletionSerializer,
    ProfileStatusSerializer, InvestmentProfileSerializer,
    ProfileUpdateSerializer, PasswordResetSerializer,
    PasswordResetConfirmSerializer
)
from .permissions import IsAdminUser, IsActive, IsEmailVerified
from .utils import send_verification_email

logger = logging.getLogger(__name__)


class AdminDashboardView(APIView):
    """
    Simple aggregated dashboard endpoint.
    Returns only essential dashboard data in a single response.
    """
    permission_classes = [IsAuthenticated, IsAdminUser]
    
    def get(self, request):
        try:
            now = timezone.now()
            today = now.date()
            week_start = today - timedelta(days=7)
            
            dashboard_data = {
                'timestamp': now.isoformat(),
                'quick_stats': self.get_quick_stats(today),
                'recent_users': self.get_recent_users(),
                'recent_transactions': self.get_recent_transactions(week_start),
            }
            
            return Response(dashboard_data, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"Dashboard error: {str(e)}", exc_info=True)
            return Response({
                'error': 'Failed to load dashboard data'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    def get_quick_stats(self, today):
        """Get quick overview stats for dashboard cards"""
        try:
            # Total users excluding admins
            total_users = User.objects.filter(
                is_staff=False, 
                is_superuser=False
            ).count()
            
            new_users_today = User.objects.filter(
                is_staff=False, 
                is_superuser=False,
                created_at__date=today
            ).count()
            
            quick_stats = {
                'total_users': total_users,
                'new_users_today': new_users_today,
                'active_investments': 0,
                'pending_deposits': 0,
                'pending_withdrawals': 0,
                'total_deposits_today': 0.0,
            }
            
            # Add wallet stats if available
            try:
                from wallet.models import Deposit, Withdrawal
                quick_stats['pending_deposits'] = Deposit.objects.filter(status='pending').count()
                quick_stats['pending_withdrawals'] = Withdrawal.objects.filter(status='pending').count()
                quick_stats['total_deposits_today'] = float(
                    Deposit.objects.filter(
                        created_at__date=today, 
                        status='approved'
                    ).aggregate(total=Sum('amount')).get('total') or 0
                )
            except (ImportError, Exception) as e:
                # Try alternative model names
                try:
                    from wallet.models import Transaction
                    quick_stats['pending_deposits'] = Transaction.objects.filter(
                        transaction_type='deposit', 
                        status='pending'
                    ).count()
                    quick_stats['pending_withdrawals'] = Transaction.objects.filter(
                        transaction_type='withdrawal', 
                        status='pending'
                    ).count()
                except (ImportError, Exception):
                    pass
            
            # Add investment stats if available
            try:
                # Try different possible model names
                try:
                    from investments.models import Investment
                    quick_stats['active_investments'] = Investment.objects.filter(
                        status='active'
                    ).count()
                except ImportError:
                    try:
                        from investments.models import UserInvestment
                        quick_stats['active_investments'] = UserInvestment.objects.filter(
                            status='active'
                        ).count()
                    except ImportError:
                        pass
            except Exception:
                pass
            
            return quick_stats
            
        except Exception as e:
            logger.error(f"Quick stats error: {str(e)}")
            return {
                'total_users': 0,
                'new_users_today': 0,
                'active_investments': 0,
                'pending_deposits': 0,
                'pending_withdrawals': 0,
                'total_deposits_today': 0.0,
            }
    
    def get_recent_users(self):
        """Get 5 most recent user registrations excluding admins"""
        try:
            recent_users = User.objects.filter(
                is_staff=False, 
                is_superuser=False
            ).order_by('-created_at')[:5]
            
            return [{
                'id': user.id,
                'name': user.get_full_name(),
                'email': user.email,
                'country': user.country,
                'date_joined': user.created_at.isoformat(),
                'initials': f"{user.first_name[0] if user.first_name else ''}{user.last_name[0] if user.last_name else ''}",
            } for user in recent_users]
        except Exception as e:
            logger.error(f"Recent users error: {str(e)}")
            return []
    
    def get_recent_transactions(self, week_start):
        """Get recent deposits and withdrawals"""
        transactions = []
        
        try:
            # Try to get transactions from wallet app
            try:
                from wallet.models import Deposit, Withdrawal
                
                # Deposits - use wallet__user instead of user
                try:
                    recent_deposits = Deposit.objects.filter(
                        created_at__date__gte=week_start
                    ).select_related('wallet__user').order_by('-created_at')[:5]
                    
                    for d in recent_deposits:
                        wallet_user = d.wallet.user if hasattr(d, 'wallet') and d.wallet else None
                        transactions.append({
                            'id': d.id,
                            'type': 'deposit',
                            'user_name': wallet_user.get_full_name() if wallet_user else 'Unknown',
                            'user_email': wallet_user.email if wallet_user else 'N/A',
                            'amount': float(d.amount) if d.amount else 0,
                            'status': d.status,
                            'created_at': d.created_at.isoformat(),
                        })
                except Exception:
                    pass
                
                # Withdrawals
                try:
                    recent_withdrawals = Withdrawal.objects.filter(
                        created_at__date__gte=week_start
                    ).select_related('wallet__user').order_by('-created_at')[:5]
                    
                    for w in recent_withdrawals:
                        wallet_user = w.wallet.user if hasattr(w, 'wallet') and w.wallet else None
                        transactions.append({
                            'id': w.id,
                            'type': 'withdrawal',
                            'user_name': wallet_user.get_full_name() if wallet_user else 'Unknown',
                            'user_email': wallet_user.email if wallet_user else 'N/A',
                            'amount': float(w.amount) if w.amount else 0,
                            'status': w.status,
                            'created_at': w.created_at.isoformat(),
                        })
                except Exception:
                    pass
                    
            except ImportError:
                pass
            
            # Sort combined transactions by created_at descending
            transactions.sort(key=lambda x: x['created_at'], reverse=True)
            
            return transactions[:10]
            
        except Exception as e:
            logger.error(f"Recent transactions error: {str(e)}")
            return []


class UserRegistrationView(APIView):
    permission_classes = [AllowAny]
    
    def post(self, request):
        serializer = UserRegistrationSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()
            
            return Response({
                'message': 'User registered successfully. Please verify your email.',
                'user': {
                    'id': user.id,
                    'email': user.email,
                    'name': user.get_full_name()
                }
            }, status=status.HTTP_201_CREATED)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class EmailVerificationView(APIView):
    permission_classes = [AllowAny]
    
    def get(self, request):
        """Handle GET request from email verification link"""
        token = request.query_params.get('token')
        
        if not token:
            return Response({
                'error': 'Verification token is required.',
                'message': 'Please use the verification link from your email.'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            user = User.objects.get(email_verification_token=token)
        except User.DoesNotExist:
            return Response({
                'error': 'Invalid verification token.',
                'message': 'The verification link is invalid. Please request a new one.'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Check if already verified
        if user.email_verified:
            return Response({
                'message': 'Email is already verified. You can log in now.',
                'email': user.email,
                'already_verified': True
            }, status=status.HTTP_200_OK)
        
        # Check if token expired (24 hours)
        if user.email_verification_sent_at and \
           (timezone.now() - user.email_verification_sent_at).total_seconds() > 86400:
            return Response({
                'error': 'Verification link has expired.',
                'message': 'Please request a new verification email.',
                'email': user.email
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Verify the user
        user.email_verified = True
        user.email_verification_token = None
        user.email_verification_sent_at = None
        user.save()
        
        # Send welcome email
        self.send_welcome_email(user.email, user.get_full_name())
        
        return Response({
            'message': 'Email verified successfully! You can now log in.',
            'email': user.email
        }, status=status.HTTP_200_OK)
    
    def post(self, request):
        """Handle POST request (for API clients)"""
        serializer = EmailVerificationSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.validated_data['user']
            
            if user.email_verified:
                return Response({
                    'message': 'Email is already verified.',
                    'email': user.email
                }, status=status.HTTP_200_OK)
            
            user.email_verified = True
            user.email_verification_token = None
            user.email_verification_sent_at = None
            user.save()
            
            self.send_welcome_email(user.email, user.get_full_name())
            
            return Response({
                'message': 'Email verified successfully! You can now log in.',
                'email': user.email
            }, status=status.HTTP_200_OK)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    def send_welcome_email(self, email, name):
        print(f"[EMAIL SIMULATION] Welcome email sent to {email} for {name}")


class UserLoginView(APIView):
    permission_classes = [AllowAny]
    
    def post(self, request):
        serializer = UserLoginSerializer(data=request.data, context={'request': request})
        
        if serializer.is_valid():
            user = serializer.validated_data['user']
            
            # Check if email is verified BEFORE generating tokens
            if not user.email_verified:
                return Response({
                    'error': 'EMAIL_NOT_VERIFIED',
                    'message': 'Please verify your email before logging in.',
                    'email': user.email,
                }, status=status.HTTP_403_FORBIDDEN)
            
            # Reset failed attempts on successful authentication
            user.reset_failed_attempts()
            
            # Generate JWT tokens
            refresh = RefreshToken.for_user(user)
            
            # Update last login
            user.last_login = timezone.now()
            user.save(update_fields=['last_login'])
            
            response_data = {
                'message': 'Login successful',
                'tokens': {
                    'refresh': str(refresh),
                    'access': str(refresh.access_token),
                },
                'user': UserProfileSerializer(user).data
            }
            
            return Response(response_data, status=status.HTTP_200_OK)
        
        # Increment failed attempts for invalid login
        email = request.data.get('email')
        if email:
            try:
                user = User.objects.get(email=email)
                user.increment_failed_attempts()
            except User.DoesNotExist:
                pass
        
        # Small delay for security
        time.sleep(0.5)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class UserProfileView(APIView):
    permission_classes = [IsAuthenticated, IsActive]
    
    def get(self, request):
        serializer = UserProfileSerializer(request.user)
        return Response(serializer.data, status=status.HTTP_200_OK)
    
    def put(self, request):
        serializer = ProfileUpdateSerializer(request.user, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(UserProfileSerializer(request.user).data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class ProfileStatusView(APIView):
    permission_classes = [IsAuthenticated, IsActive]
    
    def get(self, request):
        user = request.user
        serializer = ProfileStatusSerializer(user)
        return Response(serializer.data, status=status.HTTP_200_OK)


class InvestmentProfileView(APIView):
    permission_classes = [IsAuthenticated, IsActive, IsEmailVerified]
    
    def get(self, request):
        """Get user's investment profile"""
        try:
            profile = request.user.investment_profile
            serializer = InvestmentProfileSerializer(profile)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except InvestmentProfile.DoesNotExist:
            return Response({
                'message': 'No investment profile found.'
            }, status=status.HTTP_404_NOT_FOUND)
    
    def put(self, request):
        """Update investment profile (partial updates allowed)"""
        try:
            profile = request.user.investment_profile
            serializer = InvestmentProfileSerializer(profile, data=request.data, partial=True)
            if serializer.is_valid():
                serializer.save()
                return Response(serializer.data, status=status.HTTP_200_OK)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        except InvestmentProfile.DoesNotExist:
            return Response({
                'error': 'Investment profile not found.'
            }, status=status.HTTP_404_NOT_FOUND)


class CompleteProfileView(APIView):
    permission_classes = [IsAuthenticated, IsActive, IsEmailVerified]
    
    def post(self, request):
        """Complete investment profile (mark as completed)"""
        user = request.user
        
        serializer = ProfileCompletionSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            profile = user.investment_profile
            profile_data = serializer.validated_data['investment_profile']
            
            # Update investment profile
            for field, value in profile_data.items():
                setattr(profile, field, value)
            
            # Mark profile as completed
            profile.is_completed = True
            profile.completed_at = timezone.now()
            profile.save()
            
            # Send profile completion email
            self.send_profile_completion_email(user.email, user.get_full_name())
            
            return Response({
                'message': 'Profile completed successfully!',
                'profile': InvestmentProfileSerializer(profile).data
            }, status=status.HTTP_200_OK)
            
        except InvestmentProfile.DoesNotExist:
            return Response({
                'error': 'Investment profile not found.'
            }, status=status.HTTP_404_NOT_FOUND)
    
    def send_profile_completion_email(self, email, name):
        print(f"[EMAIL SIMULATION] Profile completion email sent to {email} for {name}")


class ChangePasswordView(APIView):
    permission_classes = [IsAuthenticated, IsActive]
    
    def post(self, request):
        serializer = PasswordChangeSerializer(data=request.data)
        if serializer.is_valid():
            user = request.user
            
            # Check old password
            if not user.check_password(serializer.validated_data['old_password']):
                return Response(
                    {'old_password': 'Wrong password.'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Set new password
            user.set_password(serializer.validated_data['new_password'])
            user.save(update_fields=['password'])
            
            return Response({
                'message': 'Password changed successfully.'
            }, status=status.HTTP_200_OK)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class PasswordResetView(APIView):
    permission_classes = [AllowAny]
    
    def post(self, request):
        serializer = PasswordResetSerializer(data=request.data)
        if serializer.is_valid():
            email = serializer.validated_data['email']
            user = User.objects.get(email=email)
            
            # Generate reset token
            reset_token = secrets.token_hex(32)
            user.email_verification_token = reset_token  # Reusing this field for password reset
            user.email_verification_sent_at = timezone.now()
            user.save(update_fields=['email_verification_token', 'email_verification_sent_at'])
            
            # Send password reset email
            reset_link = f"http://localhost:5173/auth/reset-password?token={reset_token}"
            print(f"[EMAIL SIMULATION] Password reset link for {email}: {reset_link}")
            
            return Response({
                'message': 'Password reset email sent successfully.'
            }, status=status.HTTP_200_OK)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class PasswordResetConfirmView(APIView):
    permission_classes = [AllowAny]
    
    def post(self, request):
        serializer = PasswordResetConfirmSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.validated_data['user']
            new_password = serializer.validated_data['new_password']
            
            # Set new password
            user.set_password(new_password)
            user.email_verification_token = None
            user.email_verification_sent_at = None
            user.save(update_fields=['password', 'email_verification_token', 'email_verification_sent_at'])
            
            return Response({
                'message': 'Password reset successfully. You can now log in with your new password.'
            }, status=status.HTTP_200_OK)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class ResendVerificationView(APIView):
    permission_classes = [AllowAny]
    
    def post(self, request):
        serializer = ResendVerificationSerializer(data=request.data)
        if serializer.is_valid():
            email = serializer.validated_data['email']
            user = User.objects.get(email=email)
            
            # Generate new verification token
            new_token = secrets.token_hex(32)
            user.email_verification_token = new_token
            user.email_verification_sent_at = timezone.now()
            user.save(update_fields=['email_verification_token', 'email_verification_sent_at'])
            
            # Send verification email
            send_verification_email(user.email, user.get_full_name(), new_token)
            
            return Response({
                'message': 'Verification email sent successfully.'
            }, status=status.HTTP_200_OK)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class LogoutView(APIView):
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        try:
            refresh_token = request.data.get("refresh")
            if refresh_token:
                token = RefreshToken(refresh_token)
                token.blacklist()
            return Response({
                'message': 'Logged out successfully'
            }, status=status.HTTP_205_RESET_CONTENT)
        except Exception as e:
            return Response({
                'error': 'Invalid token or logout failed'
            }, status=status.HTTP_400_BAD_REQUEST)


# Admin Views
class AdminUserListView(APIView):
    permission_classes = [IsAuthenticated, IsAdminUser]
    
    def get(self, request):
        # Exclude admin/superuser accounts from list
        queryset = User.objects.filter(
            is_staff=False, 
            is_superuser=False
        ).order_by('-created_at')
        
        # Apply filters
        role = request.query_params.get('role')
        if role:
            queryset = queryset.filter(role=role)
        
        is_active = request.query_params.get('is_active')
        if is_active is not None:
            queryset = queryset.filter(is_active=is_active.lower() == 'true')
        
        email_verified = request.query_params.get('email_verified')
        if email_verified is not None:
            queryset = queryset.filter(email_verified=email_verified.lower() == 'true')
        
        # Add search
        search = request.query_params.get('search')
        if search:
            queryset = queryset.filter(
                Q(email__icontains=search) |
                Q(first_name__icontains=search) |
                Q(last_name__icontains=search) |
                Q(country__icontains=search)
            )
        
        # Get total count for pagination info
        total_count = queryset.count()
        
        # Optional pagination
        page = int(request.query_params.get('page', 1))
        page_size = int(request.query_params.get('page_size', 20))
        start = (page - 1) * page_size
        end = start + page_size
        
        users = queryset[start:end]
        serializer = UserProfileSerializer(users, many=True)
        
        return Response({
            'count': total_count,
            'total_users': total_count,  # This now excludes admins
            'page': page,
            'page_size': page_size,
            'total_pages': (total_count + page_size - 1) // page_size,
            'users': serializer.data
        }, status=status.HTTP_200_OK)


class AdminUserDetailView(APIView):
    permission_classes = [IsAuthenticated, IsAdminUser]
    
    def get(self, request, user_id):
        try:
            user = User.objects.get(id=user_id)
            serializer = UserProfileSerializer(user)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except User.DoesNotExist:
            return Response({
                'error': 'User not found.'
            }, status=status.HTTP_404_NOT_FOUND)
    
    def put(self, request, user_id):
        try:
            user = User.objects.get(id=user_id)
            serializer = AdminUserUpdateSerializer(user, data=request.data, partial=True)
            if serializer.is_valid():
                serializer.save()
                return Response(serializer.data, status=status.HTTP_200_OK)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        except User.DoesNotExist:
            return Response({
                'error': 'User not found.'
            }, status=status.HTTP_404_NOT_FOUND)
    
    def delete(self, request, user_id):
        try:
            user = User.objects.get(id=user_id)
            # Soft delete
            user.is_active = False
            user.save(update_fields=['is_active'])
            
            # Send suspension email
            print(f"[EMAIL SIMULATION] Account suspension notification sent to {user.email}")
            
            return Response({
                'message': f'User {user.email} has been deactivated.'
            }, status=status.HTTP_200_OK)
        except User.DoesNotExist:
            return Response({
                'error': 'User not found.'
            }, status=status.HTTP_404_NOT_FOUND)


class AdminToggleUserStatusView(APIView):
    permission_classes = [IsAuthenticated, IsAdminUser]
    
    def post(self, request, user_id):
        try:
            user = User.objects.get(id=user_id)
            user.is_active = not user.is_active
            user.save(update_fields=['is_active'])
            
            status_text = "activated" if user.is_active else "suspended"
            return Response({
                'message': f'User {user.email} has been {status_text}.'
            }, status=status.HTTP_200_OK)
        except User.DoesNotExist:
            return Response({
                'error': 'User not found.'
            }, status=status.HTTP_404_NOT_FOUND)


class AdminResetUserPasswordView(APIView):
    permission_classes = [IsAuthenticated, IsAdminUser]
    
    def post(self, request, user_id):
        try:
            user = User.objects.get(id=user_id)
            
            # Generate a temporary password
            import string
            alphabet = string.ascii_letters + string.digits
            temp_password = ''.join(secrets.choice(alphabet) for i in range(12))
            
            user.set_password(temp_password)
            user.save(update_fields=['password'])
            
            # In production, send this via email instead of returning it
            print(f"[EMAIL SIMULATION] Temporary password for {user.email}: {temp_password}")
            
            return Response({
                'message': f'Password reset for {user.email}',
                'temporary_password': temp_password  # Remove this in production
            }, status=status.HTTP_200_OK)
        except User.DoesNotExist:
            return Response({
                'error': 'User not found.'
            }, status=status.HTTP_404_NOT_FOUND)


class AdminChangeUserRoleView(APIView):
    permission_classes = [IsAuthenticated, IsAdminUser]
    
    def post(self, request, user_id):
        try:
            user = User.objects.get(id=user_id)
            
            new_role = request.data.get('role')
            if new_role not in [User.Role.USER, User.Role.ADMIN]:
                return Response({
                    'error': 'Invalid role. Must be USER or ADMIN'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            old_role = user.role
            user.role = new_role
            user.is_staff = (new_role == User.Role.ADMIN)
            user.save(update_fields=['role', 'is_staff'])
            
            return Response({
                'message': f'User {user.email} role changed from {old_role} to {new_role}',
                'user': UserProfileSerializer(user).data
            }, status=status.HTTP_200_OK)
        except User.DoesNotExist:
            return Response({
                'error': 'User not found.'
            }, status=status.HTTP_404_NOT_FOUND)


class AdminUserInvestmentsView(APIView):
    permission_classes = [IsAuthenticated, IsAdminUser]
    
    def get(self, request, user_id):
        try:
            user = User.objects.get(id=user_id)
            # This would integrate with investments app
            return Response({
                'user': user.email,
                'message': 'Investment data would be here'
            }, status=status.HTTP_200_OK)
        except User.DoesNotExist:
            return Response({
                'error': 'User not found.'
            }, status=status.HTTP_404_NOT_FOUND)