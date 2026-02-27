from rest_framework import status, generics
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import authenticate
from django.utils import timezone
import time
import secrets

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
    
    def post(self, request):
        serializer = EmailVerificationSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.validated_data['user']
            user.email_verified = True
            user.email_verification_token = None
            user.email_verification_sent_at = None
            user.save()
            
            # Send welcome email after email verification
            self.send_welcome_email(user.email, user.get_full_name())
            
            return Response({
                'message': 'Email verified successfully. You can now log in.',
                'email': user.email
            }, status=status.HTTP_200_OK)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    def send_welcome_email(self, email, name):
        print(f"[EMAIL SIMULATION] Welcome email sent to {email} for {name}")
        # TODO: Integrate with actual email service

class UserLoginView(APIView):
    permission_classes = [AllowAny]
    
    def post(self, request):
        serializer = UserLoginSerializer(data=request.data, context={'request': request})
        
        if serializer.is_valid():
            user = serializer.validated_data['user']
            
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
            verification_link = f"http://localhost:5173/auth/verify-email?token={new_token}"
            print(f"[EMAIL SIMULATION] New verification link for {user.email}: {verification_link}")
            
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
        queryset = User.objects.all().order_by('-created_at')
        
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
        
        serializer = UserProfileSerializer(queryset, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

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
        
