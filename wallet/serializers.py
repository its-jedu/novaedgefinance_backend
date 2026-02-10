from rest_framework import serializers
from django.conf import settings
from django.utils import timezone
from decimal import Decimal
import requests
from .models import (
    Wallet, Transaction, InvestmentPlan, 
    UserInvestment, Deposit
)

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

class InvestmentPlanSerializer(serializers.ModelSerializer):
    class Meta:
        model = InvestmentPlan
        fields = [
            'id', 'name', 'description', 'duration_days',
            'min_amount', 'max_amount', 'daily_return_rate',
            'total_return_percentage', 'is_active',
            'has_compounding', 'compounding_frequency',
            'created_at', 'updated_at'
        ]

class UserInvestmentSerializer(serializers.ModelSerializer):
    plan_name = serializers.CharField(source='plan.name', read_only=True)
    user_email = serializers.EmailField(source='user.email', read_only=True)
    days_elapsed = serializers.IntegerField(read_only=True)
    days_remaining = serializers.IntegerField(read_only=True)
    progress_percentage = serializers.DecimalField(
        max_digits=5,
        decimal_places=2,
        read_only=True
    )
    
    class Meta:
        model = UserInvestment
        fields = [
            'investment_id', 'user_email', 'plan_name',
            'principal_amount', 'expected_total', 'current_value',
            'total_profit', 'start_date', 'end_date',
            'last_compounded_at', 'completed_at', 'status',
            'days_elapsed', 'days_remaining', 'progress_percentage',
            'created_at', 'updated_at'
        ]
        read_only_fields = fields

class CreateInvestmentSerializer(serializers.Serializer):
    plan_id = serializers.IntegerField(required=True)
    amount = serializers.DecimalField(
        max_digits=20,
        decimal_places=8,
        required=True,
        min_value=0.01
    )
    
    def validate(self, attrs):
        plan_id = attrs.get('plan_id')
        amount = attrs.get('amount')
        
        try:
            plan = InvestmentPlan.objects.get(id=plan_id, is_active=True)
        except InvestmentPlan.DoesNotExist:
            raise serializers.ValidationError({
                'plan_id': 'Invalid or inactive investment plan.'
            })
        
        # Check minimum amount
        if amount < plan.min_amount:
            raise serializers.ValidationError({
                'amount': f'Minimum investment amount is ${plan.min_amount}.'
            })
        
        # Check maximum amount
        if plan.max_amount and amount > plan.max_amount:
            raise serializers.ValidationError({
                'amount': f'Maximum investment amount is ${plan.max_amount}.'
            })
        
        attrs['plan'] = plan
        return attrs

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
        
        if amount_usd < Decimal('50.00'):
            raise serializers.ValidationError({
                'amount_usd': 'Minimum deposit amount is $50.00'
            })
        
        if amount_usd > Decimal('10000.00'):
            raise serializers.ValidationError({
                'amount_usd': 'Maximum deposit amount is $10,000.00'
            })
        
        return attrs

class InvestmentGrowthDataSerializer(serializers.Serializer):
    date = serializers.DateField()
    value = serializers.DecimalField(max_digits=20, decimal_places=8)
    profit = serializers.DecimalField(max_digits=20, decimal_places=8)
    
class WalletOverviewSerializer(serializers.Serializer):
    balance = serializers.DecimalField(max_digits=20, decimal_places=8)
    total_deposits = serializers.DecimalField(max_digits=20, decimal_places=8)
    total_investments = serializers.DecimalField(max_digits=20, decimal_places=8)
    total_profits = serializers.DecimalField(max_digits=20, decimal_places=8)
    active_investments_count = serializers.IntegerField()
    active_investments_total = serializers.DecimalField(max_digits=20, decimal_places=8)
    recent_transactions = TransactionSerializer(many=True)
    recent_investments = UserInvestmentSerializer(many=True)