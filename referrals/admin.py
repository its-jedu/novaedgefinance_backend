from django.contrib import admin

# Register your models here.
from .models import Referral, BonusWallet, UserReferralCode, ReferralBonusSettings

@admin.register(Referral)
class ReferralAdmin(admin.ModelAdmin):
    list_display = ('referral_id', 'get_referrer_email', 'get_referred_email', 
                   'bonus_amount', 'status', 'bonus_paid', 'created_at')
    list_filter = ('status', 'bonus_paid', 'created_at')
    search_fields = ('referrer__email', 'referred_user__email', 'referral_code')
    readonly_fields = ('referral_id', 'created_at', 'updated_at', 'bonus_paid_at')
    
    def get_referrer_email(self, obj):
        return obj.referrer.email
    get_referrer_email.short_description = 'Referrer'
    
    def get_referred_email(self, obj):
        return obj.referred_user.email
    get_referred_email.short_description = 'Referred User'
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('referrer', 'referred_user')

@admin.register(BonusWallet)
class BonusWalletAdmin(admin.ModelAdmin):
    list_display = ('get_user_email', 'balance', 'total_earned', 
                   'total_withdrawn', 'created_at')
    list_filter = ('created_at',)
    search_fields = ('user__email',)
    readonly_fields = ('created_at', 'updated_at')
    
    def get_user_email(self, obj):
        return obj.user.email
    get_user_email.short_description = 'User'
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user')

@admin.register(UserReferralCode)
class UserReferralCodeAdmin(admin.ModelAdmin):
    list_display = ('get_user_email', 'code', 'custom_code', 
                   'total_referrals', 'total_bonus_earned', 'is_active')
    list_filter = ('is_active', 'created_at')
    search_fields = ('user__email', 'code', 'custom_code')
    list_editable = ('is_active',)
    readonly_fields = ('created_at', 'updated_at')
    
    def get_user_email(self, obj):
        return obj.user.email
    get_user_email.short_description = 'User'
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user')

@admin.register(ReferralBonusSettings)
class ReferralBonusSettingsAdmin(admin.ModelAdmin):
    list_display = ('default_bonus_amount', 'minimum_deposit_for_bonus', 
                   'bonus_withdrawal_enabled', 'is_active')
    readonly_fields = ('created_at', 'updated_at')

