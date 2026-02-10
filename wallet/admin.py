from django.contrib import admin

# Register your models here.
from django.utils import timezone
from .models import Wallet, Transaction, InvestmentPlan, UserInvestment, Deposit

@admin.register(Wallet)
class WalletAdmin(admin.ModelAdmin):
    list_display = ('user', 'balance_usd', 'total_deposited', 'total_profit', 'created_at')
    list_filter = ('created_at',)
    search_fields = ('user__email', 'user__first_name', 'user__last_name')
    readonly_fields = ('created_at', 'updated_at')
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user')

@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ('transaction_id', 'get_user_email', 'transaction_type', 'amount', 'status', 'created_at')
    list_filter = ('transaction_type', 'status', 'created_at')
    search_fields = ('wallet__user__email', 'reference', 'description')
    readonly_fields = ('transaction_id', 'created_at', 'updated_at')
    
    def get_user_email(self, obj):
        return obj.wallet.user.email
    get_user_email.short_description = 'User Email'
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('wallet__user')

@admin.register(InvestmentPlan)
class InvestmentPlanAdmin(admin.ModelAdmin):
    list_display = ('name', 'duration_days', 'min_amount', 'max_amount', 'total_return_percentage', 'is_active')
    list_filter = ('is_active', 'has_compounding', 'compounding_frequency')
    search_fields = ('name', 'description')
    readonly_fields = ('created_at', 'updated_at')

@admin.register(UserInvestment)
class UserInvestmentAdmin(admin.ModelAdmin):
    list_display = ('investment_id', 'get_user_email', 'plan', 'principal_amount', 'current_value', 'status', 'start_date')
    list_filter = ('status', 'plan', 'start_date')
    search_fields = ('user__email', 'investment_id', 'plan__name')
    readonly_fields = ('investment_id', 'created_at', 'updated_at', 'completed_at')
    
    def get_user_email(self, obj):
        return obj.user.email
    get_user_email.short_description = 'User Email'
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user', 'plan')
    
    def save_model(self, request, obj, form, change):
        # Update current value if saving an active investment
        if obj.status == obj.InvestmentStatus.ACTIVE:
            obj.update_current_value()
        super().save_model(request, obj, form, change)

@admin.register(Deposit)
class DepositAdmin(admin.ModelAdmin):
    list_display = ('deposit_id', 'get_user_email', 'pay_currency', 'usd_amount', 'status', 'created_at')
    list_filter = ('status', 'pay_currency', 'created_at')
    search_fields = ('user__email', 'payment_id', 'invoice_id', 'deposit_id')
    readonly_fields = ('deposit_id', 'created_at', 'updated_at', 'confirmed_at')
    
    def get_user_email(self, obj):
        return obj.user.email
    get_user_email.short_description = 'User Email'
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user')