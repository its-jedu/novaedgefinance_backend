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
    expires_at = serializers.DateTimeField(read_only=True)
    
    class Meta:
        model = Deposit
        fields = [
            'deposit_id', 'user_email', 'payment_id', 'invoice_id',
            'pay_address', 'pay_currency', 'pay_amount', 'usd_amount',
            'exchange_rate', 'status', 'payment_url', 'qr_code_url',
            'expires_at', 'payment_details', 'created_at', 'updated_at', 
            'confirmed_at'
        ]
        read_only_fields = fields


class DepositStatusSerializer(serializers.ModelSerializer):
    """
    Simplified serializer for checking deposit status
    """
    class Meta:
        model = Deposit
        fields = [
            'deposit_id', 'payment_id', 'status', 
            'usd_amount', 'pay_amount', 'pay_currency',
            'confirmed_at', 'created_at'
        ]
        read_only_fields = fields


class CreateDepositSerializer(serializers.Serializer):
    amount_usd = serializers.DecimalField(
        max_digits=20,
        decimal_places=2,
        required=True,
        min_value=10.00,
        max_value=100000.00
    )
    currency = serializers.ChoiceField(
        choices=['BTC', 'ETH', 'USDT', 'USDC', 'LTC', 'BNB', 'BUSD', 'DAI'],
        required=True
    )
    plan_id = serializers.IntegerField(required=False, allow_null=True)
    
    def validate(self, attrs):
        amount_usd = attrs.get('amount_usd')
        
        if amount_usd < Decimal('10.00'):
            raise serializers.ValidationError({
                'amount_usd': 'Minimum deposit amount is $10.00'
            })
        
        if amount_usd > Decimal('100000.00'):
            raise serializers.ValidationError({
                'amount_usd': 'Maximum deposit amount is $100,000.00'
            })
        
        # Validate plan if provided
        plan_id = attrs.get('plan_id')
        if plan_id:
            from investments.models import InvestmentPlan
            try:
                plan = InvestmentPlan.objects.get(id=plan_id, is_active=True)
                # Check if amount is within plan limits
                if amount_usd < plan.min_amount:
                    raise serializers.ValidationError({
                        'amount_usd': f'Minimum amount for this plan is ${plan.min_amount}'
                    })
                if plan.max_amount and amount_usd > plan.max_amount:
                    raise serializers.ValidationError({
                        'amount_usd': f'Maximum amount for this plan is ${plan.max_amount}'
                    })
            except InvestmentPlan.DoesNotExist:
                raise serializers.ValidationError({
                    'plan_id': 'Invalid investment plan'
                })
        
        return attrs


class WalletOverviewSerializer(serializers.Serializer):
    balance = serializers.DecimalField(max_digits=20, decimal_places=2)
    total_balance = serializers.DecimalField(max_digits=20, decimal_places=2)
    available_balance = serializers.DecimalField(max_digits=20, decimal_places=2)
    locked_balance = serializers.DecimalField(max_digits=20, decimal_places=2)
    total_deposits = serializers.DecimalField(max_digits=20, decimal_places=2)
    total_investments = serializers.DecimalField(max_digits=20, decimal_places=2)
    total_profits = serializers.DecimalField(max_digits=20, decimal_places=2)
    total_withdrawn = serializers.DecimalField(max_digits=20, decimal_places=2)
    recent_transactions = TransactionSerializer(many=True)
    active_investments_count = serializers.IntegerField(default=0)
    
    def to_representation(self, instance):
        representation = super().to_representation(instance)
        
        # Format all decimal fields to 2 decimal places for display
        for key, value in representation.items():
            if isinstance(value, Decimal):
                representation[key] = float(value)
        
        return representation

