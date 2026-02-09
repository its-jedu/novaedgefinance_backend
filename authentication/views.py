from django.shortcuts import render

# Create your views here.
from rest_framework import status, viewsets, generics
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import authenticate
from django.utils import timezone
import time
import secrets
import random

from .models import User, InvestmentProfile
from .serializers import (
    UserRegistrationSerializer, UserLoginSerializer,
    PhoneVerificationSerializer, EmailVerificationSerializer,
    UserProfileSerializer, AdminUserUpdateSerializer,
    PasswordResetSerializer, PasswordChangeSerializer,
    ResendVerificationSerializer, ProfileCompletionSerializer,
    ProfileStatusSerializer, InvestmentProfileSerializer
)
from .permissions import IsAdminUser, IsOwnerOrAdmin, IsVerified, IsActive, IsEmailVerified, IsProfileCompleted, CanMakeDeposits

class UserRegistrationView(APIView):
    permission_classes = [AllowAny]
    
    def post(self, request):
        serializer = UserRegistrationSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()
            
            return Response({
                'message': 'User registered successfully. Please verify your email and phone number.',
                'user': {
                    'id': user.id,
                    'email': user.email,
                    'phone_number': user.phone_number,
                    'name': user.get_full_name()
                },
                'next_steps': [
                    'Check your email for verification link',
                    'Check your phone for verification code'
                ]
            }, status=status.HTTP_201_CREATED)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class PhoneVerificationView(APIView):
    permission_classes = [AllowAny]
    
    def post(self, request):
        serializer = PhoneVerificationSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.validated_data['user']
            user.is_verified = True
            user.phone_verification_code = None
            user.phone_verification_sent_at = None
            user.save()
            
            return Response({
                'message': 'Phone number verified successfully.',
                'next_step': 'Complete your investment profile to start investing'
            }, status=status.HTTP_200_OK)
        
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
                'message': 'Email verified successfully.',
                'next_step': 'Verify your phone number and complete profile'
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
            
            # Generate JWT tokens
            refresh = RefreshToken.for_user(user)
            
            # Update last login
            user.last_login = timezone.now()
            user.save()
            
            response_data = {
                'message': 'Login successful',
                'tokens': {
                    'refresh': str(refresh),
                    'access': str(refresh.access_token),
                },
                'user': UserProfileSerializer(user).data,
                'profile_status': {
                    'email_verified': user.email_verified,
                    'phone_verified': user.is_verified,
                    'profile_completed': user.profile_completed,
                    'can_make_deposits': user.can_make_deposits
                }
            }
            
            return Response(response_data, status=status.HTTP_200_OK)
        
        # Increment failed attempts for invalid login
        email = request.data.get('email')
        try:
            user = User.objects.get(email=email)
            user.increment_failed_attempts()
        except User.DoesNotExist:
            pass
        
        # Implement exponential backoff
        time.sleep(0.1)  # Small delay for failed attempts
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class UserProfileView(generics.RetrieveUpdateAPIView):
    serializer_class = UserProfileSerializer
    permission_classes = [IsAuthenticated, IsActive]
    
    def get_object(self):
        return self.request.user

class ProfileStatusView(APIView):
    permission_classes = [IsAuthenticated, IsActive]
    
    def get(self, request):
        user = request.user
        missing_fields = []
        
        # Check investment profile fields
        try:
            profile = user.investment_profile
            
            required_fields = [
                ('date_of_birth', 'Date of Birth'),
                ('address', 'Address'),
                ('city', 'City'),
                ('postal_code', 'Postal Code'),
                ('annual_income', 'Annual Income'),
                ('employment_status', 'Employment Status'),
                ('risk_tolerance', 'Risk Tolerance'),
                ('investment_goal', 'Investment Goal'),
                ('selected_plan_id', 'Investment Plan'),
                ('accepted_terms', 'Terms & Conditions'),
                ('accepted_privacy_policy', 'Privacy Policy'),
                ('accepted_risk_disclosure', 'Risk Disclosure')
            ]
            
            for field, field_name in required_fields:
                field_value = getattr(profile, field)
                if not field_value:
                    missing_fields.append(field_name)
        
        except InvestmentProfile.DoesNotExist:
            missing_fields = ['Complete investment profile']
        
        serializer = ProfileStatusSerializer({
            'email_verified': user.email_verified,
            'phone_verified': user.is_verified,
            'profile_completed': user.profile_completed,
            'can_make_deposits': user.can_make_deposits,
            'missing_fields': missing_fields
        })
        
        return Response(serializer.data, status=status.HTTP_200_OK)

class CompleteProfileView(APIView):
    permission_classes = [IsAuthenticated, IsActive, IsEmailVerified]
    
    def post(self, request):
        user = request.user
        
        if user.profile_completed:
            return Response({
                'message': 'Profile is already completed.'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        serializer = ProfileCompletionSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            profile = user.investment_profile
            profile_data = serializer.validated_data['investment_profile']
            
            # Update investment profile
            for field, value in profile_data.items():
                setattr(profile, field, value)
            
            profile.save()
            
            # Mark user profile as completed
            user.profile_completed = True
            user.profile_completed_at = timezone.now()
            user.save()
            
            # Send profile completion email
            self.send_profile_completion_email(user.email, user.get_full_name())
            
            return Response({
                'message': 'Profile completed successfully! You can now make deposits.',
                'user': UserProfileSerializer(user).data
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
            user.save()
            
            return Response({
                'message': 'Password changed successfully.'
            }, status=status.HTTP_200_OK)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class ResendVerificationView(APIView):
    permission_classes = [AllowAny]
    
    def post(self, request):
        serializer = ResendVerificationSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.validated_data['user']
            verification_type = serializer.validated_data['type']
            
            if verification_type == 'email':
                # Resend email verification
                new_token = secrets.token_hex(32)
                user.email_verification_token = new_token
                user.email_verification_sent_at = timezone.now()
                user.save()
                
                verification_link = f"https://novaedgefinance.com/verify-email?token={new_token}"
                print(f"[EMAIL SIMULATION] New verification link for {user.email}: {verification_link}")
                
                return Response({
                    'message': 'Email verification link sent successfully.'
                }, status=status.HTTP_200_OK)
            
            elif verification_type == 'phone':
                # Resend phone verification
                if user.is_verified:
                    return Response({
                        'error': 'Phone is already verified.'
                    }, status=status.HTTP_400_BAD_REQUEST)
                
                new_code = str(random.randint(100000, 999999))
                user.phone_verification_code = new_code
                user.phone_verification_sent_at = timezone.now()
                user.save()
                
                print(f"[SMS SIMULATION] New verification code for {user.phone_number}: {new_code}")
                
                return Response({
                    'message': 'Phone verification code sent successfully.'
                }, status=status.HTTP_200_OK)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

# Admin Views
class AdminUserListView(generics.ListAPIView):
    queryset = User.objects.all().order_by('-created_at')
    serializer_class = UserProfileSerializer
    permission_classes = [IsAuthenticated, IsAdminUser]
    
    def get_queryset(self):
        queryset = User.objects.all()
        
        # Filter by role if provided
        role = self.request.query_params.get('role', None)
        if role:
            queryset = queryset.filter(role=role)
        
        # Filter by status if provided
        is_active = self.request.query_params.get('is_active', None)
        if is_active is not None:
            queryset = queryset.filter(is_active=is_active.lower() == 'true')
        
        # Filter by verification status
        email_verified = self.request.query_params.get('email_verified', None)
        if email_verified is not None:
            queryset = queryset.filter(email_verified=email_verified.lower() == 'true')
        
        # Filter by profile completion
        profile_completed = self.request.query_params.get('profile_completed', None)
        if profile_completed is not None:
            queryset = queryset.filter(profile_completed=profile_completed.lower() == 'true')
        
        return queryset.order_by('-created_at')

class AdminUserDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = User.objects.all()
    serializer_class = AdminUserUpdateSerializer
    permission_classes = [IsAuthenticated, IsAdminUser]
    
    def perform_destroy(self, instance):
        # Soft delete - deactivate user instead of deleting
        instance.is_active = False
        instance.save()
        
        # Send suspension email
        print(f"[EMAIL SIMULATION] Account suspension notification sent to {instance.email}")

class AdminSuspendUserView(APIView):
    permission_classes = [IsAuthenticated, IsAdminUser]
    
    def post(self, request, user_id):
        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return Response(
                {'error': 'User not found.'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        user.is_active = False
        user.save()
        
        return Response({
            'message': f'User {user.email} has been suspended.',
            'user': UserProfileSerializer(user).data
        }, status=status.HTTP_200_OK)

class AdminActivateUserView(APIView):
    permission_classes = [IsAuthenticated, IsAdminUser]
    
    def post(self, request, user_id):
        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return Response(
                {'error': 'User not found.'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        user.is_active = True
        user.save()
        
        return Response({
            'message': f'User {user.email} has been activated.',
            'user': UserProfileSerializer(user).data
        }, status=status.HTTP_200_OK)

class AdminResetUserPasswordView(APIView):
    permission_classes = [IsAuthenticated, IsAdminUser]
    
    def post(self, request, user_id):
        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return Response(
                {'error': 'User not found.'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Generate a temporary password
        import string
        alphabet = string.ascii_letters + string.digits
        temp_password = ''.join(secrets.choice(alphabet) for i in range(12))
        
        user.set_password(temp_password)
        user.save()
        
        return Response({
            'message': f'Password reset for {user.email}',
            'temporary_password': temp_password,  # Remove this in production
            'note': 'In production, send this via email or secure channel'
        }, status=status.HTTP_200_OK)

class AdminChangeUserRoleView(APIView):
    permission_classes = [IsAuthenticated, IsAdminUser]
    
    def post(self, request, user_id):
        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return Response(
                {'error': 'User not found.'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        new_role = request.data.get('role')
        if new_role not in [User.Role.USER, User.Role.ADMIN]:
            return Response(
                {'error': 'Invalid role. Must be USER or ADMIN'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        old_role = user.role
        user.role = new_role
        
        # Update is_staff for Django admin access
        user.is_staff = (new_role == User.Role.ADMIN)
        user.save()
        
        return Response({
            'message': f'User {user.email} role changed from {old_role} to {new_role}',
            'user': UserProfileSerializer(user).data
        }, status=status.HTTP_200_OK)

class LogoutView(APIView):
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        try:
            refresh_token = request.data["refresh"]
            token = RefreshToken(refresh_token)
            token.blacklist()
            return Response(status=status.HTTP_205_RESET_CONTENT)
        except Exception:
            return Response(status=status.HTTP_400_BAD_REQUEST)
        
