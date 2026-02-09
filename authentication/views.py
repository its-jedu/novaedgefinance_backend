from django.shortcuts import render

# Create your views here.
from rest_framework import status, viewsets, generics
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView
from django.contrib.auth import authenticate
from django.utils import timezone
import time

from .models import User
from .serializers import (
    UserRegistrationSerializer, UserLoginSerializer,
    PhoneVerificationSerializer, UserSerializer,
    AdminUserUpdateSerializer, PasswordResetSerializer,
    PasswordChangeSerializer
)
from .permissions import IsAdminUser, IsOwnerOrAdmin, IsVerified, IsActive

class UserRegistrationView(APIView):
    permission_classes = [AllowAny]
    
    def post(self, request):
        serializer = UserRegistrationSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()
            
            # Send welcome email (simulated)
            self.send_welcome_email(user.email, user.get_full_name())
            
            return Response({
                'message': 'User registered successfully. Please verify your phone number.',
                'user': {
                    'id': user.id,
                    'email': user.email,
                    'phone_number': user.phone_number,
                    'name': user.get_full_name()
                }
            }, status=status.HTTP_201_CREATED)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    def send_welcome_email(self, email, name):
        # In production, integrate with email service
        print(f"[EMAIL SIMULATION] Welcome email sent to {email} for {name}")
        pass

class PhoneVerificationView(APIView):
    permission_classes = [AllowAny]
    
    def post(self, request):
        serializer = PhoneVerificationSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.validated_data['user']
            user.is_verified = True
            user.verification_code = None
            user.verification_code_sent_at = None
            user.save()
            
            # Send verification confirmation email
            self.send_verification_email(user.email)
            
            # Generate tokens
            refresh = RefreshToken.for_user(user)
            
            return Response({
                'message': 'Phone number verified successfully.',
                'tokens': {
                    'refresh': str(refresh),
                    'access': str(refresh.access_token),
                },
                'user': UserSerializer(user).data
            }, status=status.HTTP_200_OK)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    def send_verification_email(self, email):
        # In production, integrate with email service
        print(f"[EMAIL SIMULATION] Verification confirmation sent to {email}")
        pass

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
            
            return Response({
                'message': 'Login successful',
                'tokens': {
                    'refresh': str(refresh),
                    'access': str(refresh.access_token),
                },
                'user': UserSerializer(user).data
            }, status=status.HTTP_200_OK)
        
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
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated, IsActive]
    
    def get_object(self):
        return self.request.user

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
            
            # Invalidate all tokens (optional)
            # RefreshToken.for_user(user).blacklist()
            
            return Response({
                'message': 'Password changed successfully.'
            }, status=status.HTTP_200_OK)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

# Admin Views
class AdminUserListView(generics.ListAPIView):
    queryset = User.objects.all().order_by('-created_at')
    serializer_class = UserSerializer
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
        self.send_suspension_email(instance.email)
    
    def send_suspension_email(self, email):
        # In production, integrate with email service
        print(f"[EMAIL SIMULATION] Account suspension notification sent to {email}")
        pass

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
            'user': UserSerializer(user).data
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
            'user': UserSerializer(user).data
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
        import secrets
        import string
        alphabet = string.ascii_letters + string.digits
        temp_password = ''.join(secrets.choice(alphabet) for i in range(12))
        
        user.set_password(temp_password)
        user.save()
        
        # In production, send the temporary password via secure channel
        # For now, return it (in production, you would email it to the user)
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
            'user': UserSerializer(user).data
        }, status=status.HTTP_200_OK)

class ResendVerificationView(APIView):
    permission_classes = [AllowAny]
    
    def post(self, request):
        phone_number = request.data.get('phone_number')
        
        if not phone_number:
            return Response(
                {'error': 'Phone number is required.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            user = User.objects.get(phone_number=phone_number)
        except User.DoesNotExist:
            return Response(
                {'error': 'User with this phone number not found.'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        if user.is_verified:
            return Response(
                {'error': 'User is already verified.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Generate new verification code
        import random
        verification_code = str(random.randint(100000, 999999))
        user.verification_code = verification_code
        user.verification_code_sent_at = timezone.now()
        user.save()
        
        # Send new code
        print(f"[SMS SIMULATION] New verification code for {phone_number}: {verification_code}")
        
        return Response({
            'message': 'New verification code sent successfully.'
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