from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.translation import gettext_lazy as _
from .models import User, InvestmentProfile

class InvestmentProfileInline(admin.StackedInline):
    model = InvestmentProfile
    can_delete = False
    verbose_name_plural = 'Investment Profile'
    fk_name = 'user'
    extra = 0
    readonly_fields = ['created_at', 'updated_at', 'completed_at']
    fieldsets = (
        ('Personal Details', {
            'fields': ('date_of_birth', 'address', 'city', 'postal_code')
        }),
        ('Financial Information', {
            'fields': ('annual_income', 'employment_status', 'source_of_funds')
        }),
        ('Investment Preferences', {
            'fields': ('risk_tolerance', 'investment_goal', 'investment_experience', 
                      'selected_plan_id', 'selected_plan_name')
        }),
        ('Terms Acceptance', {
            'fields': ('accepted_terms', 'accepted_privacy_policy', 'accepted_risk_disclosure')
        }),
        ('Status', {
            'fields': ('is_completed', 'completed_at', 'created_at', 'updated_at')
        }),
    )

class CustomUserAdmin(BaseUserAdmin):
    model = User
    inlines = [InvestmentProfileInline]
    
    # List display
    list_display = [
        'id', 'email', 'first_name', 'last_name', 
        'country', 'email_verified', 'role', 'is_active', 
        'created_at', 'get_investment_profile_status'
    ]
    
    list_display_links = ['id', 'email']
    
    # List filters
    list_filter = [
        'email_verified', 'role', 'is_active', 
        'country', 'created_at'
    ]
    
    # Search fields
    search_fields = ['email', 'first_name', 'last_name', 'country']
    
    # Date hierarchy
    date_hierarchy = 'created_at'
    
    # Default ordering
    ordering = ['-created_at']
    
    # Fieldsets for detail view
    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        (_('Personal Info'), {'fields': ('first_name', 'last_name', 'country')}),
        (_('Permissions'), {
            'fields': ('role', 'email_verified', 'is_active', 'is_staff', 'is_superuser'),
        }),
        (_('Security'), {
            'fields': ('failed_login_attempts', 'locked_until', 'last_failed_login'),
            'classes': ('collapse',),
        }),
        (_('Suspicious Activity'), {
            'fields': ('suspicious_activity_count', 'is_under_review', 'review_reason'),
            'classes': ('collapse',),
        }),
        (_('Investment Limits'), {
            'fields': ('daily_investment_limit', 'last_investment_date', 'daily_investment_total'),
            'classes': ('collapse',),
        }),
        (_('Important dates'), {'fields': ('last_login', 'created_at', 'updated_at')}),
    )
    
    # Readonly fields
    readonly_fields = [
        'last_login', 'created_at', 'updated_at',
        'failed_login_attempts', 'locked_until', 'last_failed_login',
        'suspicious_activity_count', 'is_under_review', 'review_reason',
        'daily_investment_total', 'last_investment_date'
    ]
    
    # Add form fieldsets
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'first_name', 'last_name', 'country', 
                      'password1', 'password2', 'role'),
        }),
    )
    
    # Actions
    actions = ['activate_users', 'deactivate_users', 'mark_email_verified', 'mark_admin']
    
    def get_investment_profile_status(self, obj):
        """Display investment profile status in list display"""
        try:
            if hasattr(obj, 'investment_profile'):
                profile = obj.investment_profile
                if profile.is_completed:
                    return '✅ Completed'
                elif any([profile.date_of_birth, profile.address, profile.city]):
                    return '⏳ Partial'
                else:
                    return '⬜ Not Started'
            return '⬜ No Profile'
        except:
            return '⬜ Error'
    get_investment_profile_status.short_description = 'Investment Profile'
    get_investment_profile_status.admin_order_field = 'investment_profile__is_completed'
    
    def activate_users(self, request, queryset):
        """Activate selected users"""
        updated = queryset.update(is_active=True)
        self.message_user(request, f'{updated} users activated successfully.')
    activate_users.short_description = "Activate selected users"
    
    def deactivate_users(self, request, queryset):
        """Deactivate selected users"""
        updated = queryset.update(is_active=False)
        self.message_user(request, f'{updated} users deactivated successfully.')
    deactivate_users.short_description = "Deactivate selected users"
    
    def mark_email_verified(self, request, queryset):
        """Mark email as verified for selected users"""
        updated = queryset.update(email_verified=True)
        self.message_user(request, f'{updated} users email marked as verified.')
    mark_email_verified.short_description = "Mark email as verified"
    
    def mark_admin(self, request, queryset):
        """Set role to admin for selected users"""
        updated = queryset.update(role='ADMIN', is_staff=True)
        self.message_user(request, f'{updated} users set as admin.')
    mark_admin.short_description = "Set as Admin"

class InvestmentProfileAdmin(admin.ModelAdmin):
    model = InvestmentProfile
    list_display = [
        'id', 'user_email', 'get_user_name', 'is_completed', 
        'completed_at', 'risk_tolerance', 'investment_goal', 'created_at'
    ]
    list_filter = ['is_completed', 'risk_tolerance', 'investment_goal', 'employment_status']
    search_fields = ['user__email', 'user__first_name', 'user__last_name', 'city']
    readonly_fields = ['created_at', 'updated_at', 'completed_at']
    date_hierarchy = 'created_at'
    ordering = ['-created_at']
    
    fieldsets = (
        ('User Information', {
            'fields': ('user',)
        }),
        ('Personal Details', {
            'fields': ('date_of_birth', 'address', 'city', 'postal_code')
        }),
        ('Financial Information', {
            'fields': ('annual_income', 'employment_status', 'source_of_funds')
        }),
        ('Investment Preferences', {
            'fields': ('risk_tolerance', 'investment_goal', 'investment_experience', 
                      'selected_plan_id', 'selected_plan_name')
        }),
        ('Terms Acceptance', {
            'fields': ('accepted_terms', 'accepted_privacy_policy', 'accepted_risk_disclosure')
        }),
        ('Status', {
            'fields': ('is_completed', 'completed_at', 'created_at', 'updated_at')
        }),
    )
    
    def user_email(self, obj):
        return obj.user.email
    user_email.short_description = 'Email'
    user_email.admin_order_field = 'user__email'
    
    def get_user_name(self, obj):
        return obj.user.get_full_name()
    get_user_name.short_description = 'Name'
    get_user_name.admin_order_field = 'user__first_name'
    
    actions = ['mark_as_completed', 'mark_as_incomplete']
    
    def mark_as_completed(self, request, queryset):
        from django.utils import timezone
        updated = queryset.update(is_completed=True, completed_at=timezone.now())
        self.message_user(request, f'{updated} profiles marked as completed.')
    mark_as_completed.short_description = "Mark as completed"
    
    def mark_as_incomplete(self, request, queryset):
        updated = queryset.update(is_completed=False, completed_at=None)
        self.message_user(request, f'{updated} profiles marked as incomplete.')
    mark_as_incomplete.short_description = "Mark as incomplete"

# Register the models with their custom admin classes
admin.site.register(User, CustomUserAdmin)
admin.site.register(InvestmentProfile, InvestmentProfileAdmin)