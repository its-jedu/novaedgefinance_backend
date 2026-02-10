from rest_framework import serializers
from django.conf import settings
from django.utils import timezone
from decimal import Decimal
import requests
from .models import Wallet, Transaction, Deposit

class WalletSerializer(serializers.ModelSerializer):
    user_email = serializers.EmailField(source='user.email', read_only=True)
    user_name = serializers.CharField(source='user.get_full_name', read_only=True)
    
    class Meta:
        model = Wallet
        fields = [
            'id', 'user_email', 'user_name',
            'balance_usd', 'total_deposited', 'total_invested',
            'total_profit', 'total_withdrawn', 'created_at', 'updated_at'
        ]
        read_only_fields = fields

class TransactionSerializer(serializers.ModelSerializer):
    wallet_id = serializers.IntegerField(source='wallet.id', read_only=True)
    user_email = serializers.EmailField(source='wallet.user.email', read_only=True)
    
    class Meta:
        model = Transaction
        fields = [
            'transaction_id', 'wallet_id', 'user_email',
            'transaction_type', 'amount', 'status',
            'description', 'reference', 'metadata',
            'created_at', 'updated_at'
        ]
        read_only_fields = fields

class DepositSerializer(serializers.ModelSerializer):
    user_email = serializers.EmailField(source='user.email', read_only=True)
    payment_url = serializers.CharField(read_only=True)
    qr_code_url = serializers.CharField(read_only=True)
    
    class Meta:
        model = Deposit
        fields = [
            'deposit_id', 'user_email', 'payment_id', 'invoice_id',
            'pay_address', 'pay_currency', 'pay_amount', 'usd_amount',
            'exchange_rate', 'status', 'payment_url', 'qr_code_url',
            'created_at', 'updated_at', 'confirmed_at'
        ]
        read_only_fields = fields

class CreateDepositSerializer(serializers.Serializer):
    amount_usd = serializers.DecimalField(
        max_digits=20,
        decimal_places=8,
        required=True,
        min_value=10.00,
        max_value=10000.00
    )
    currency = serializers.ChoiceField(
        choices=['BTC', 'ETH', 'USDT', 'USDC', 'LTC', 'BNB'],
        required=True
    )
    
    def validate(self, attrs):
        amount_usd = attrs.get('amount_usd')
        
        if amount_usd < Decimal('10.00'):
            raise serializers.ValidationError({
                'amount_usd': 'Minimum deposit amount is $10.00'
            })
        
        if amount_usd > Decimal('10000.00'):
            raise serializers.ValidationError({
                'amount_usd': 'Maximum deposit amount is $10,000.00'
            })
        
        return attrs

class WalletOverviewSerializer(serializers.Serializer):
    balance = serializers.DecimalField(max_digits=20, decimal_places=8)
    total_deposits = serializers.DecimalField(max_digits=20, decimal_places=8)
    total_investments = serializers.DecimalField(max_digits=20, decimal_places=8)
    total_profits = serializers.DecimalField(max_digits=20, decimal_places=8)
    recent_transactions = TransactionSerializer(many=True)
    
    def to_representation(self, instance):
        representation = super().to_representation(instance)
        # Add active investments count if investments app is installed
        try:
            from investments.models import UserInvestment
            active_investments = UserInvestment.objects.filter(
                user=self.context['request'].user,
                status='ACTIVE'
            ).count()
            representation['active_investments_count'] = active_investments
        except ImportError:
            representation['active_investments_count'] = 0
        
        return representation