from django.contrib import admin

# Register your models here.
from django.utils.html import format_html
from .models import (
    InvestmentPlan, PlanFAQ, PlanPerformance,
    UserInvestment, ProfitWithdrawal, InvestmentAlert
)

@admin.register(InvestmentPlan)
class InvestmentPlanAdmin(admin.ModelAdmin):
    list_display = ('name', 'plan_type', 'category', 'min_amount', 'max_amount', 
                   'min_return_multiplier', 'max_return_multiplier', 'return_period',
                   'is_active', 'is_featured', 'display_order')
    list_filter = ('plan_type', 'category', 'is_active', 'is_featured', 'return_period')
    search_fields = ('name', 'description', 'short_description')
    list_editable = ('is_active', 'is_featured', 'display_order')
    readonly_fields = ('total_investors', 'total_invested', 'total_profits_paid', 
                      'success_rate', 'created_at', 'updated_at')
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'plan_type', 'category', 'description', 'short_description')
        }),
        ('Investment Range', {
            'fields': ('min_amount', 'max_amount')
        }),
        ('Returns Configuration', {
            'fields': ('min_return_multiplier', 'max_return_multiplier', 'return_period')
        }),
        ('Duration', {
            'fields': ('min_duration_days', 'max_duration_days', 'is_flexible_duration')
        }),
        ('Features & Benefits', {
            'fields': ('features', 'risk_level', 'performance_fee_percentage')
        }),
        ('Status & Display', {
            'fields': ('is_active', 'is_featured', 'display_order')
        }),
        ('Statistics', {
            'fields': ('total_investors', 'total_invested', 'total_profits_paid', 'success_rate')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at')
        }),
    )


@admin.register(PlanFAQ)
class PlanFAQAdmin(admin.ModelAdmin):
    list_display = ('question', 'plan', 'display_order')
    list_filter = ('plan',)
    search_fields = ('question', 'answer')
    list_editable = ('display_order',)


@admin.register(PlanPerformance)
class PlanPerformanceAdmin(admin.ModelAdmin):
    list_display = ('plan', 'period_start', 'period_end', 'average_return', 
                   'total_invested', 'total_profits', 'market_condition')
    list_filter = ('plan', 'market_condition', 'period_start')
    search_fields = ('plan__name',)
    readonly_fields = ('created_at', 'updated_at')


@admin.register(UserInvestment)
class UserInvestmentAdmin(admin.ModelAdmin):
    list_display = ('investment_id', 'user_email', 'plan', 'principal_amount', 
                   'current_value', 'status', 'created_at')
    list_filter = ('status', 'plan', 'withdrawal_status', 'created_at')
    search_fields = ('user__email', 'investment_id', 'plan__name')
    readonly_fields = ('investment_id', 'current_value', 'total_profit', 
                      'total_withdrawn', 'created_at', 'updated_at', 'completed_at')
    
    def user_email(self, obj):
        return obj.user.email
    user_email.short_description = 'User Email'
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user', 'plan')


@admin.register(ProfitWithdrawal)
class ProfitWithdrawalAdmin(admin.ModelAdmin):
    list_display = ('withdrawal_id', 'user_email', 'amount', 'net_amount', 
                   'status', 'payment_method', 'created_at')
    list_filter = ('status', 'payment_method', 'created_at')
    search_fields = ('user__email', 'withdrawal_id', 'investment__investment_id')
    readonly_fields = ('withdrawal_id', 'created_at', 'updated_at', 'processed_at')
    
    def user_email(self, obj):
        return obj.user.email
    user_email.short_description = 'User Email'
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user', 'investment')


@admin.register(InvestmentAlert)
class InvestmentAlertAdmin(admin.ModelAdmin):
    list_display = ('title', 'alert_type', 'priority', 'is_active', 
                   'is_read', 'valid_from', 'valid_until')
    list_filter = ('alert_type', 'priority', 'is_active', 'is_read')
    search_fields = ('title', 'message')
    list_editable = ('is_active', 'is_read', 'priority')
    filter_horizontal = ('target_plans', 'target_users')
    readonly_fields = ('created_at',)
    
    def formfield_for_manytomany(self, db_field, request, **kwargs):
        if db_field.name == "target_users":
            kwargs["queryset"] = kwargs.get("queryset", db_field.remote_field.model.objects.all()).order_by('email')
        return super().formfield_for_manytomany(db_field, request, **kwargs)