from rest_framework import serializers
from django.utils import timezone
from decimal import Decimal
from .models import (
    Referral, BonusWallet, UserReferralCode,
    ReferralBonusSettings
)

class ReferralSerializer(serializers.ModelSerializer):
    referrer_email = serializers.EmailField(source='referrer.email', read_only=True)
    referrer_name = serializers.CharField(source='referrer.get_full_name', read_only=True)
    referred_email = serializers.EmailField(source='referred_user.email', read_only=True)
    referred_name = serializers.CharField(source='referred_user.get_full_name', read_only=True)
    
    class Meta:
        model = Referral
        fields = [
            'referral_id', 'referrer', 'referrer_email', 'referrer_name',
            'referred_user', 'referred_email', 'referred_name',
            'referral_code', 'bonus_amount', 'status',
            'referred_user_deposited', 'referred_user_deposit_amount',
            'bonus_paid', 'bonus_paid_at', 'bonus_transaction_id',
            'metadata', 'created_at', 'updated_at'
        ]
        read_only_fields = fields

class BonusWalletSerializer(serializers.ModelSerializer):
    user_email = serializers.EmailField(source='user.email', read_only=True)
    user_name = serializers.CharField(source='user.get_full_name', read_only=True)
    
    class Meta:
        model = BonusWallet
        fields = [
            'id', 'user', 'user_email', 'user_name',
            'balance', 'total_earned', 'total_withdrawn',
            'created_at', 'updated_at'
        ]
        read_only_fields = fields

class UserReferralCodeSerializer(serializers.ModelSerializer):
    user_email = serializers.EmailField(source='user.email', read_only=True)
    display_code = serializers.CharField(read_only=True)
    referral_url = serializers.CharField(read_only=True)
    
    class Meta:
        model = UserReferralCode
        fields = [
            'id', 'user', 'user_email', 'code', 'custom_code',
            'display_code', 'referral_url', 'total_referrals',
            'active_referrals', 'total_bonus_earned', 'is_active',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['code', 'total_referrals', 'active_referrals', 
                          'total_bonus_earned', 'created_at', 'updated_at']

class CreateCustomCodeSerializer(serializers.Serializer):
    custom_code = serializers.CharField(
        required=True,
        max_length=20,
        min_length=4
    )
    
    def validate_custom_code(self, value):
        # Check if custom code is available
        if UserReferralCode.objects.filter(custom_code=value).exists():
            raise serializers.ValidationError("This custom code is already taken.")
        
        # Check if code contains only alphanumeric characters
        if not value.isalnum():
            raise serializers.ValidationError("Code can only contain letters and numbers.")
        
        return value

class ReferralStatsSerializer(serializers.Serializer):
    total_referrals = serializers.IntegerField()
    active_referrals = serializers.IntegerField()
    earned_referrals = serializers.IntegerField()
    total_bonus_earned = serializers.DecimalField(max_digits=20, decimal_places=8)
    pending_bonus = serializers.DecimalField(max_digits=20, decimal_places=8)
    bonus_wallet_balance = serializers.DecimalField(max_digits=20, decimal_places=8)

class WithdrawBonusSerializer(serializers.Serializer):
    amount = serializers.DecimalField(
        max_digits=20,
        decimal_places=8,
        required=True,
        min_value=Decimal('0.01')
    )
    to_main_wallet = serializers.BooleanField(default=True)
    
    def validate(self, attrs):
        amount = attrs.get('amount')
        
        # Get user's bonus wallet
        try:
            bonus_wallet = BonusWallet.objects.get(user=self.context['request'].user)
        except BonusWallet.DoesNotExist:
            raise serializers.ValidationError("Bonus wallet not found")
        
        # Check if amount exceeds balance
        if amount > bonus_wallet.balance:
            raise serializers.ValidationError({
                'amount': 'Amount exceeds bonus wallet balance'
            })
        
        # Check minimum withdrawal amount
        settings = ReferralBonusSettings.get_settings()
        if amount < settings.minimum_withdrawal_amount:
            raise serializers.ValidationError({
                'amount': f'Minimum withdrawal amount is ${settings.minimum_withdrawal_amount}'
            })
        
        attrs['bonus_wallet'] = bonus_wallet
        return attrs

class ReferralBonusSettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReferralBonusSettings
        fields = [
            'default_bonus_amount', 'minimum_deposit_for_bonus',
            'enable_tiered_bonuses', 'tiered_bonus_settings',
            'max_referrals_per_user', 'max_bonus_per_user',
            'bonus_withdrawal_enabled', 'minimum_withdrawal_amount',
            'withdrawal_fee_percentage', 'is_active'
        ]

class ReferralLinkSerializer(serializers.Serializer):
    referral_code = serializers.CharField()
    referral_link = serializers.CharField()
    qr_code_url = serializers.CharField()
