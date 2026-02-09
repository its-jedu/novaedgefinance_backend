from rest_framework import serializers
from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password
from django.core.validators import validate_email
from django.core.exceptions import ValidationError
import re
import secrets
import random
from .models import User, InvestmentProfile
from django.utils import timezone

class UserRegistrationSerializer(serializers.ModelSerializer):
    password = serializers.CharField(
        write_only=True,
        required=True,
        style={'input_type': 'password'},
        validators=[validate_password]
    )
    password2 = serializers.CharField(
        write_only=True,
        required=True,
        style={'input_type': 'password'}
    )
    
    class Meta:
        model = User
        fields = [
            'id', 'email', 'phone_number', 'first_name', 'last_name',
            'country', 'password', 'password2', 'role', 'is_verified',
            'email_verified', 'profile_completed'
        ]
        read_only_fields = ['id', 'role', 'is_verified', 'email_verified', 'profile_completed']
    
    def validate_email(self, value):
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("A user with this email already exists.")
        try:
            validate_email(value)
        except ValidationError:
            raise serializers.ValidationError("Enter a valid email address.")
        return value
    
    def validate_phone_number(self, value):
        if User.objects.filter(phone_number=value).exists():
            raise serializers.ValidationError("A user with this phone number already exists.")
        
        phone_regex = r'^\+?1?\d{9,15}$'
        if not re.match(phone_regex, value):
            raise serializers.ValidationError(
                "Phone number must be entered in the format: '+999999999'. Up to 15 digits allowed."
            )
        return value
    
    def validate(self, attrs):
        if attrs['password'] != attrs['password2']:
            raise serializers.ValidationError({"password": "Password fields didn't match."})
        return attrs
    
    def create(self, validated_data):
        validated_data.pop('password2')
        user = User.objects.create_user(**validated_data)
        
        # Generate verification codes
        phone_code = str(random.randint(100000, 999999))
        email_token = secrets.token_hex(32)
        
        user.phone_verification_code = phone_code
        user.phone_verification_sent_at = timezone.now()
        user.email_verification_token = email_token
        user.email_verification_sent_at = timezone.now()
        user.save()
        
        # Create empty investment profile
        InvestmentProfile.objects.create(user=user)
        
        # Send verification messages
        self.send_phone_verification(user.phone_number, phone_code)
        self.send_email_verification(user.email, email_token, user.get_full_name())
        
        return user
    
    def send_phone_verification(self, phone_number, code):
        print(f"[SMS SIMULATION] Phone verification code for {phone_number}: {code}")
        # TODO: Integrate with SMS service
    
    def send_email_verification(self, email, token, name):
        verification_link = f"https://novaedgefinance.com/verify-email?token={token}"
        print(f"[EMAIL SIMULATION] Email verification link for {email}: {verification_link}")
        print(f"Subject: Verify Your Email - NovaEdgeFinance")
        print(f"Hello {name},\n\nPlease verify your email by clicking: {verification_link}")
        # TODO: Integrate with email service

class UserLoginSerializer(serializers.Serializer):
    email = serializers.EmailField(required=True)
    password = serializers.CharField(
        write_only=True,
        required=True,
        style={'input_type': 'password'}
    )
    
    def validate(self, attrs):
        email = attrs.get('email')
        password = attrs.get('password')
        
        if email and password:
            user = authenticate(request=self.context.get('request'), email=email, password=password)
            
            if not user:
                raise serializers.ValidationError("Invalid email or password.")
            
            # Check email verification (NEW)
            if not user.email_verified:
                raise serializers.ValidationError("Please verify your email before logging in.")
            
            # Check phone verification
            if not user.is_verified:
                raise serializers.ValidationError("Please verify your phone number before logging in.")
            
            if not user.is_active:
                raise serializers.ValidationError("Your account has been suspended. Please contact support.")
            
            if user.is_locked():
                raise serializers.ValidationError(
                    f"Account is locked due to multiple failed login attempts. "
                    f"Try again at {user.locked_until.strftime('%H:%M:%S')}"
                )
            
            user.reset_failed_attempts()
            attrs['user'] = user
        else:
            raise serializers.ValidationError("Must include 'email' and 'password'.")
        
        return attrs

class PhoneVerificationSerializer(serializers.Serializer):
    phone_number = serializers.CharField(required=True)
    verification_code = serializers.CharField(required=True, max_length=6)
    
    def validate(self, attrs):
        phone_number = attrs.get('phone_number')
        verification_code = attrs.get('verification_code')
        
        try:
            user = User.objects.get(phone_number=phone_number)
        except User.DoesNotExist:
            raise serializers.ValidationError({"phone_number": "User with this phone number not found."})
        
        if user.phone_verification_code != verification_code:
            raise serializers.ValidationError({"verification_code": "Invalid verification code."})
        
        # Check if code expired (10 minutes)
        if user.phone_verification_sent_at and \
           (timezone.now() - user.phone_verification_sent_at).total_seconds() > 600:
            raise serializers.ValidationError({"verification_code": "Verification code has expired."})
        
        attrs['user'] = user
        return attrs

class EmailVerificationSerializer(serializers.Serializer):
    token = serializers.CharField(required=True, max_length=64)
    
    def validate(self, attrs):
        token = attrs.get('token')
        
        try:
            user = User.objects.get(email_verification_token=token)
        except User.DoesNotExist:
            raise serializers.ValidationError({"token": "Invalid verification token."})
        
        # Check if token expired (24 hours)
        if user.email_verification_sent_at and \
           (timezone.now() - user.email_verification_sent_at).total_seconds() > 86400:
            raise serializers.ValidationError({"token": "Verification link has expired."})
        
        attrs['user'] = user
        return attrs

class InvestmentProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = InvestmentProfile
        exclude = ['user', 'created_at', 'updated_at']
        extra_kwargs = {
            'accepted_terms': {'required': True},
            'accepted_privacy_policy': {'required': True},
            'accepted_risk_disclosure': {'required': True},
        }
    
    def validate(self, attrs):
        # Ensure all required fields are present for profile completion
        required_fields = [
            'date_of_birth',
            'address',
            'city',
            'postal_code',
            'annual_income',
            'employment_status',
            'risk_tolerance',
            'investment_goal',
            'selected_plan_id',
        ]
        
        for field in required_fields:
            if field not in attrs or not attrs[field]:
                raise serializers.ValidationError({field: "This field is required for profile completion."})
        
        # Validate terms acceptance
        if not attrs.get('accepted_terms'):
            raise serializers.ValidationError({"accepted_terms": "You must accept the terms and conditions."})
        
        if not attrs.get('accepted_privacy_policy'):
            raise serializers.ValidationError({"accepted_privacy_policy": "You must accept the privacy policy."})
        
        if not attrs.get('accepted_risk_disclosure'):
            raise serializers.ValidationError({"accepted_risk_disclosure": "You must accept the risk disclosure."})
        
        return attrs

class ProfileCompletionSerializer(serializers.Serializer):
    investment_profile = InvestmentProfileSerializer(required=True)
    
    def validate(self, attrs):
        return attrs

class UserProfileSerializer(serializers.ModelSerializer):
    investment_profile = InvestmentProfileSerializer(read_only=True)
    can_make_deposits = serializers.BooleanField(read_only=True)
    is_fully_verified = serializers.BooleanField(read_only=True)
    
    class Meta:
        model = User
        fields = [
            'id', 'email', 'phone_number', 'first_name', 'last_name',
            'country', 'role', 'is_verified', 'email_verified',
            'profile_completed', 'is_active', 'created_at',
            'profile_completed_at', 'investment_profile',
            'can_make_deposits', 'is_fully_verified'
        ]
        read_only_fields = ['id', 'created_at', 'profile_completed_at']

class ProfileStatusSerializer(serializers.Serializer):
    email_verified = serializers.BooleanField()
    phone_verified = serializers.BooleanField()
    profile_completed = serializers.BooleanField()
    can_make_deposits = serializers.BooleanField()
    missing_fields = serializers.ListField(child=serializers.CharField())

class AdminUserUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = [
            'id', 'email', 'phone_number', 'first_name', 'last_name',
            'country', 'role', 'is_verified', 'email_verified',
            'profile_completed', 'is_active', 'is_staff'
        ]

class PasswordResetSerializer(serializers.Serializer):
    email = serializers.EmailField(required=True)
    
    def validate_email(self, value):
        try:
            user = User.objects.get(email=value)
        except User.DoesNotExist:
            raise serializers.ValidationError("User with this email does not exist.")
        
        if not user.is_active:
            raise serializers.ValidationError("This account is suspended.")
        
        if not user.email_verified:
            raise serializers.ValidationError("Email is not verified. Please verify your email first.")
        
        return value

class PasswordChangeSerializer(serializers.Serializer):
    old_password = serializers.CharField(required=True, write_only=True)
    new_password = serializers.CharField(
        required=True,
        write_only=True,
        validators=[validate_password]
    )
    confirm_password = serializers.CharField(required=True, write_only=True)
    
    def validate(self, attrs):
        if attrs['new_password'] != attrs['confirm_password']:
            raise serializers.ValidationError({"new_password": "Passwords do not match."})
        return attrs

class ResendVerificationSerializer(serializers.Serializer):
    email = serializers.EmailField(required=False)
    phone_number = serializers.CharField(required=False)
    
    def validate(self, attrs):
        email = attrs.get('email')
        phone_number = attrs.get('phone_number')
        
        if not email and not phone_number:
            raise serializers.ValidationError("Either email or phone number must be provided.")
        
        if email:
            try:
                user = User.objects.get(email=email)
                attrs['user'] = user
                attrs['type'] = 'email'
            except User.DoesNotExist:
                raise serializers.ValidationError({"email": "User with this email not found."})
        elif phone_number:
            try:
                user = User.objects.get(phone_number=phone_number)
                attrs['user'] = user
                attrs['type'] = 'phone'
            except User.DoesNotExist:
                raise serializers.ValidationError({"phone_number": "User with this phone number not found."})
        
        return attrs