from rest_framework import serializers
from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password
from django.core.validators import validate_email
from django.core.exceptions import ValidationError
import re
from .models import User
import random

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
            'country', 'password', 'password2', 'role', 'is_verified'
        ]
        read_only_fields = ['id', 'role', 'is_verified']
    
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
        
        # Basic phone validation
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
        
        # Generate verification code
        verification_code = str(random.randint(100000, 999999))
        user.verification_code = verification_code
        user.verification_code_sent_at = timezone.now()
        user.save()
        
        # Send verification code (simulated)
        self.send_verification_code(user.phone_number, verification_code)
        
        return user
    
    def send_verification_code(self, phone_number, code):
        # In production, integrate with SMS service like Twilio, AWS SNS, etc.
        print(f"[SMS SIMULATION] Verification code for {phone_number}: {code}")
        # Simulate sending SMS
        # For MVP, we'll just print it. Replace with actual SMS service in production.
        pass

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
            
            if not user.is_verified:
                raise serializers.ValidationError("Please verify your phone number before logging in.")
            
            if not user.is_active:
                raise serializers.ValidationError("Your account has been suspended. Please contact support.")
            
            if user.is_locked():
                raise serializers.ValidationError(
                    f"Account is locked due to multiple failed login attempts. "
                    f"Try again at {user.locked_until.strftime('%H:%M:%S')}"
                )
            
            # Reset failed attempts on successful login
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
        
        # Check if verification code is valid (and not expired - e.g., within 10 minutes)
        if user.verification_code != verification_code:
            raise serializers.ValidationError({"verification_code": "Invalid verification code."})
        
        # Check if code expired (10 minutes)
        from django.utils import timezone
        if user.verification_code_sent_at and \
           (timezone.now() - user.verification_code_sent_at).total_seconds() > 600:
            raise serializers.ValidationError({"verification_code": "Verification code has expired."})
        
        attrs['user'] = user
        return attrs

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = [
            'id', 'email', 'phone_number', 'first_name', 'last_name',
            'country', 'role', 'is_verified', 'is_active', 'created_at',
            'failed_login_attempts'
        ]
        read_only_fields = ['id', 'created_at', 'failed_login_attempts']

class AdminUserUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = [
            'id', 'email', 'phone_number', 'first_name', 'last_name',
            'country', 'role', 'is_verified', 'is_active', 'is_staff'
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