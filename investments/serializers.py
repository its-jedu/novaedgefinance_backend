from rest_framework import serializers
from django.utils import timezone
from decimal import Decimal
from .models import (
    InvestmentPlan, PlanFAQ, PlanPerformance,
    UserInvestment, ProfitWithdrawal, InvestmentAlert
)

class InvestmentPlanSerializer(serializers.ModelSerializer):
    """Serializer for investment plans"""
    
    # Computed fields
    estimated_daily_return = serializers.DecimalField(
        max_digits=10,
        decimal_places=4,
        read_only=True
    )
    estimated_monthly_return = serializers.DecimalField(
        max_digits=10,
        decimal_places=2,
        read_only=True
    )
    is_available = serializers.BooleanField(read_only=True)
    current_investors = serializers.IntegerField(read_only=True)
    
    class Meta:
        model = InvestmentPlan
        fields = [
            'id', 'name', 'plan_type', 'category', 'description', 'short_description',
            'min_amount', 'max_amount', 'min_return_multiplier', 'max_return_multiplier',
            'return_period', 'min_duration_days', 'max_duration_days', 'is_flexible_duration',
            'features', 'risk_level', 'performance_fee_percentage', 'is_active', 'is_featured',
            'display_order', 'total_investors', 'total_invested', 'total_profits_paid',
            'success_rate', 'estimated_daily_return', 'estimated_monthly_return',
            'is_available', 'current_investors', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'total_investors', 'total_invested', 'total_profits_paid',
            'success_rate', 'created_at', 'updated_at'
        ]
    
    def get_estimated_daily_return(self, obj):
        return obj.calculate_daily_return_rate()
    
    def get_estimated_monthly_return(self, obj):
        daily_rate = obj.calculate_daily_return_rate()
        return daily_rate * Decimal('30')
    
    def get_is_available(self, obj):
        return obj.is_active
    
    def get_current_investors(self, obj):
        return obj.user_investments.filter(
            status__in=['ACTIVE', 'PENDING']
        ).count()


class PlanFAQSerializer(serializers.ModelSerializer):
    """Serializer for plan FAQs"""
    
    class Meta:
        model = PlanFAQ
        fields = ['id', 'plan', 'question', 'answer', 'display_order', 'created_at']
        read_only_fields = ['created_at']


class PlanPerformanceSerializer(serializers.ModelSerializer):
    """Serializer for plan performance history"""
    
    plan_name = serializers.CharField(source='plan.name', read_only=True)
    
    class Meta:
        model = PlanPerformance
        fields = [
            'id', 'plan', 'plan_name', 'period_start', 'period_end',
            'average_return', 'total_invested', 'total_profits',
            'active_investments', 'completed_investments',
            'market_condition', 'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']


class UserInvestmentSerializer(serializers.ModelSerializer):
    """Serializer for user investments"""
    
    plan_name = serializers.CharField(source='plan.name', read_only=True)
    plan_type = serializers.CharField(source='plan.plan_type', read_only=True)
    user_email = serializers.CharField(source='user.email', read_only=True)
    user_name = serializers.CharField(source='user.get_full_name', read_only=True)
    
    # Computed fields
    days_elapsed = serializers.IntegerField(read_only=True)
    days_remaining = serializers.IntegerField(read_only=True)
    progress_percentage = serializers.DecimalField(
        max_digits=5,
        decimal_places=2,
        read_only=True
    )
    can_withdraw = serializers.BooleanField(read_only=True)
    max_withdrawal_amount = serializers.DecimalField(
        max_digits=20,
        decimal_places=8,
        read_only=True
    )
    
    class Meta:
        model = UserInvestment
        fields = [
            'investment_id', 'user', 'user_email', 'user_name', 'plan', 'plan_name', 'plan_type',
            'principal_amount', 'expected_return_multiplier', 'expected_total',
            'current_value', 'total_profit', 'total_withdrawn', 'start_date', 'end_date',
            'last_profit_date', 'next_profit_date', 'status', 'withdrawal_status',
            'early_withdrawal_fee', 'referred_by', 'referral_bonus_paid', 'days_elapsed',
            'days_remaining', 'progress_percentage', 'can_withdraw', 'max_withdrawal_amount',
            'created_at', 'updated_at', 'completed_at'
        ]
        read_only_fields = [
            'investment_id', 'current_value', 'total_profit', 'total_withdrawn',
            'last_profit_date', 'next_profit_date', 'days_elapsed', 'days_remaining',
            'progress_percentage', 'can_withdraw', 'max_withdrawal_amount',
            'created_at', 'updated_at', 'completed_at'
        ]


class CreateInvestmentSerializer(serializers.Serializer):
    """Serializer for creating new investments"""
    
    plan_id = serializers.IntegerField(required=True)
    amount = serializers.DecimalField(
        max_digits=20,
        decimal_places=8,
        required=True,
        min_value=Decimal('50.00')
    )
    duration_days = serializers.IntegerField(
        required=False,
        min_value=1,
        max_value=365
    )
    referral_code = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=50
    )
    
    def validate(self, attrs):
        plan_id = attrs.get('plan_id')
        amount = attrs.get('amount')
        duration_days = attrs.get('duration_days')
        
        try:
            plan = InvestmentPlan.objects.get(id=plan_id, is_active=True)
        except InvestmentPlan.DoesNotExist:
            raise serializers.ValidationError({
                'plan_id': 'Invalid or inactive investment plan.'
            })
        
        # Validate amount
        can_invest, message = plan.can_invest(amount)
        if not can_invest:
            raise serializers.ValidationError({'amount': message})
        
        # Validate duration
        if duration_days:
            if plan.min_duration_days and duration_days < plan.min_duration_days:
                raise serializers.ValidationError({
                    'duration_days': f'Minimum duration is {plan.min_duration_days} days.'
                })
            
            if plan.max_duration_days and duration_days > plan.max_duration_days:
                raise serializers.ValidationError({
                    'duration_days': f'Maximum duration is {plan.max_duration_days} days.'
                })
        else:
            # Use default duration
            attrs['duration_days'] = plan.min_duration_days
        
        attrs['plan'] = plan
        return attrs


class ProfitWithdrawalSerializer(serializers.ModelSerializer):
    """Serializer for profit withdrawals"""
    
    user_email = serializers.CharField(source='user.email', read_only=True)
    investment_id = serializers.UUIDField(source='investment.investment_id', read_only=True)
    
    class Meta:
        model = ProfitWithdrawal
        fields = [
            'withdrawal_id', 'user', 'user_email', 'investment', 'investment_id',
            'amount', 'fee', 'net_amount', 'status', 'payment_method',
            'payment_details', 'admin_notes', 'created_at', 'updated_at',
            'processed_at'
        ]
        read_only_fields = [
            'withdrawal_id', 'fee', 'net_amount', 'status', 'admin_notes',
            'created_at', 'updated_at', 'processed_at'
        ]


class RequestWithdrawalSerializer(serializers.Serializer):
    """Serializer for requesting withdrawals"""
    
    investment_id = serializers.UUIDField(required=True)
    amount = serializers.DecimalField(
        max_digits=20,
        decimal_places=8,
        required=True,
        min_value=Decimal('0.01')
    )
    payment_method = serializers.ChoiceField(
        choices=['WALLET', 'CRYPTO', 'BANK'],
        default='WALLET'
    )
    payment_details = serializers.JSONField(
        required=False,
        default=dict
    )
    
    def validate(self, attrs):
        investment_id = attrs.get('investment_id')
        amount = attrs.get('amount')
        
        try:
            investment = UserInvestment.objects.get(
                investment_id=investment_id,
                user=self.context['request'].user
            )
        except UserInvestment.DoesNotExist:
            raise serializers.ValidationError({
                'investment_id': 'Investment not found.'
            })
        
        if investment.status != investment.InvestmentStatus.ACTIVE:
            raise serializers.ValidationError({
                'investment_id': 'Investment is not active.'
            })
        
        if amount > investment.current_value:
            raise serializers.ValidationError({
                'amount': 'Amount exceeds available balance.'
            })
        
        attrs['investment'] = investment
        return attrs


class InvestmentAlertSerializer(serializers.ModelSerializer):
    """Serializer for investment alerts"""
    
    class Meta:
        model = InvestmentAlert
        fields = [
            'id', 'title', 'message', 'alert_type', 'priority',
            'target_plans', 'target_users', 'is_for_all_users',
            'is_active', 'is_read', 'valid_from', 'valid_until',
            'created_at'
        ]
        read_only_fields = ['created_at']


class InvestmentOverviewSerializer(serializers.Serializer):
    """Serializer for investment overview"""
    
    total_invested = serializers.DecimalField(max_digits=20, decimal_places=8)
    total_profits = serializers.DecimalField(max_digits=20, decimal_places=8)
    active_investments = serializers.IntegerField()
    completed_investments = serializers.IntegerField()
    pending_withdrawals = serializers.DecimalField(max_digits=20, decimal_places=8)
    estimated_monthly_income = serializers.DecimalField(max_digits=20, decimal_places=8)
    portfolio_distribution = serializers.JSONField()


class PlanComparisonSerializer(serializers.Serializer):
    """Serializer for plan comparison"""
    
    plan = InvestmentPlanSerializer()
    estimated_returns = serializers.DecimalField(max_digits=20, decimal_places=8)
    risk_score = serializers.IntegerField()
    popularity_score = serializers.IntegerField()
    recommended_for = serializers.ListField(child=serializers.CharField())