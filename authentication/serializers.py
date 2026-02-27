from rest_framework import serializers
from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password
from django.core.validators import validate_email
from django.core.exceptions import ValidationError
import secrets
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
            'id', 'email', 'first_name', 'last_name',
            'country', 'password', 'password2', 'role',
            'email_verified'
        ]
        read_only_fields = ['id', 'role', 'email_verified']
    
    def validate_email(self, value):
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("A user with this email already exists.")
        try:
            validate_email(value)
        except ValidationError:
            raise serializers.ValidationError("Enter a valid email address.")
        return value
    
    def validate(self, attrs):
        if attrs['password'] != attrs['password2']:
            raise serializers.ValidationError({"password": "Password fields didn't match."})
        return attrs
    
    def create(self, validated_data):
        validated_data.pop('password2')
        user = User.objects.create_user(**validated_data)
        
        # Generate email verification token
        email_token = secrets.token_hex(32)
        user.email_verification_token = email_token
        user.email_verification_sent_at = timezone.now()
        user.save()
        
        # Create empty investment profile
        InvestmentProfile.objects.create(user=user)
        
        # Send email verification
        self.send_email_verification(user.email, email_token, user.get_full_name())
        
        return user
    
    def send_email_verification(self, email, token, name):
        verification_link = f"http://localhost:5173/auth/verify-email?token={token}"
        print(f"[EMAIL SIMULATION] Email verification link for {email}: {verification_link}")
        print(f"Subject: Verify Your Email - NovaEdge Finance")
        print(f"Hello {name},\n\nPlease verify your email by clicking: {verification_link}\n\nThis link will expire in 24 hours.")
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
            
            # Check email verification
            if not user.email_verified:
                raise serializers.ValidationError("Please verify your email before logging in.")
            
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
            raise serializers.ValidationError({"token": "Verification link has expired. Please request a new one."})
        
        attrs['user'] = user
        return attrs

class InvestmentProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = InvestmentProfile
        exclude = ['user', 'created_at', 'updated_at']
        extra_kwargs = {
            'accepted_terms': {'required': False},
            'accepted_privacy_policy': {'required': False},
            'accepted_risk_disclosure': {'required': False},
        }
    
    def validate(self, attrs):
        # Make all fields optional - profile completion is not required for basic access
        return attrs

class ProfileCompletionSerializer(serializers.Serializer):
    investment_profile = InvestmentProfileSerializer(required=True)
    
    def validate(self, attrs):
        # Optional: Add any additional validation for profile completion
        return attrs

class UserProfileSerializer(serializers.ModelSerializer):
    investment_profile = InvestmentProfileSerializer(read_only=True)
    full_name = serializers.SerializerMethodField()
    can_make_deposits = serializers.SerializerMethodField()
    profile_status = serializers.SerializerMethodField()
    
    class Meta:
        model = User
        fields = [
            'id', 'email', 'first_name', 'last_name', 'full_name',
            'country', 'role', 'email_verified', 'is_active', 
            'created_at', 'investment_profile', 'can_make_deposits',
            'profile_status'
        ]
        read_only_fields = ['id', 'created_at', 'email_verified']
    
    def get_full_name(self, obj):
        return obj.get_full_name()
    
    def get_can_make_deposits(self, obj):
        return obj.can_make_deposits
    
    def get_profile_status(self, obj):
        """Return profile completion status"""
        try:
            profile = obj.investment_profile
            # Check if profile has any data filled
            has_data = any([
                profile.date_of_birth,
                profile.address,
                profile.city,
                profile.annual_income,
                profile.employment_status,
                profile.risk_tolerance,
                profile.investment_goal,
                profile.accepted_terms
            ])
            return {
                'has_profile': True,
                'is_completed': profile.is_completed,
                'has_data': has_data
            }
        except InvestmentProfile.DoesNotExist:
            return {
                'has_profile': False,
                'is_completed': False,
                'has_data': False
            }

class ProfileStatusSerializer(serializers.Serializer):
    email_verified = serializers.BooleanField()
    can_make_deposits = serializers.BooleanField()
    profile_exists = serializers.BooleanField()
    profile_completed = serializers.BooleanField()
    missing_fields = serializers.ListField(child=serializers.CharField(), required=False)
    
    def to_representation(self, instance):
        user = instance
        missing = []
        
        # Check investment profile completion
        try:
            profile = user.investment_profile
            profile_exists = True
            profile_completed = profile.is_completed
            
            if not profile_completed:
                # List which fields are missing (optional)
                if not profile.date_of_birth:
                    missing.append('date_of_birth')
                if not profile.address:
                    missing.append('address')
                if not profile.city:
                    missing.append('city')
                if not profile.annual_income:
                    missing.append('annual_income')
                if not profile.employment_status:
                    missing.append('employment_status')
                if not profile.risk_tolerance:
                    missing.append('risk_tolerance')
                if not profile.accepted_terms:
                    missing.append('accepted_terms')
        except InvestmentProfile.DoesNotExist:
            profile_exists = False
            profile_completed = False
            missing = ['investment_profile']
        
        return {
            'email_verified': user.email_verified,
            'can_make_deposits': user.can_make_deposits,
            'profile_exists': profile_exists,
            'profile_completed': profile_completed,
            'missing_fields': missing
        }

class ProfileUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'country']
    
    def validate(self, attrs):
        # Optional: Add any validation for profile updates
        return attrs

class AdminUserUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = [
            'id', 'email', 'first_name', 'last_name',
            'country', 'role', 'email_verified', 'is_active', 
            'is_staff', 'daily_investment_limit'
        ]

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

class PasswordResetConfirmSerializer(serializers.Serializer):
    token = serializers.CharField(required=True, max_length=64)
    new_password = serializers.CharField(
        required=True,
        write_only=True,
        validators=[validate_password]
    )
    confirm_password = serializers.CharField(required=True, write_only=True)
    
    def validate(self, attrs):
        if attrs['new_password'] != attrs['confirm_password']:
            raise serializers.ValidationError({"new_password": "Passwords do not match."})
        
        try:
            user = User.objects.get(email_verification_token=attrs['token'])
        except User.DoesNotExist:
            raise serializers.ValidationError({"token": "Invalid reset token."})
        
        # Check if token expired (24 hours)
        if user.email_verification_sent_at and \
           (timezone.now() - user.email_verification_sent_at).total_seconds() > 86400:
            raise serializers.ValidationError({"token": "Reset link has expired. Please request a new one."})
        
        attrs['user'] = user
        return attrs

class ResendVerificationSerializer(serializers.Serializer):
    email = serializers.EmailField(required=True)
    
    def validate_email(self, value):
        try:
            user = User.objects.get(email=value)
        except User.DoesNotExist:
            raise serializers.ValidationError("User with this email does not exist.")
        
        if user.email_verified:
            raise serializers.ValidationError("Email is already verified.")
        
        if not user.is_active:
            raise serializers.ValidationError("This account is suspended.")
        
        return value

