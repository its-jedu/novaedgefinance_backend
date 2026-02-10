from django.contrib import admin

# Register your models here.
from .models import Wallet, Transaction, Deposit

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