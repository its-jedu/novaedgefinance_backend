from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User, InvestmentProfile

class InvestmentProfileInline(admin.StackedInline):
    model = InvestmentProfile
    can_delete = False
    verbose_name_plural = 'Investment Profile'
    fk_name = 'user'
    readonly_fields = ('created_at', 'updated_at')

class CustomUserAdmin(UserAdmin):
    model = User
    inlines = (InvestmentProfileInline,)
    list_display = (
        'email', 'phone_number', 'first_name', 'last_name', 
        'role', 'is_verified', 'email_verified', 'profile_completed', 
        'is_active', 'created_at'
    )
    list_filter = (
        'role', 'is_verified', 'email_verified', 'profile_completed', 
        'is_active', 'country'
    )
    search_fields = ('email', 'phone_number', 'first_name', 'last_name')
    ordering = ('-created_at',)
    
    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        ('Personal Info', {'fields': ('first_name', 'last_name', 'phone_number', 'country')}),
        ('Verification Status', {'fields': (
            'is_verified', 'email_verified', 'profile_completed', 
            'profile_completed_at'
        )}),
        ('Permissions', {'fields': (
            'role', 'is_active', 'is_staff', 'is_superuser', 
            'groups', 'user_permissions'
        )}),
        ('Important Dates', {'fields': ('last_login', 'created_at', 'updated_at')}),
        ('Security', {'fields': (
            'failed_login_attempts', 'locked_until', 
            'phone_verification_code', 'phone_verification_sent_at',
            'email_verification_token', 'email_verification_sent_at'
        )}),
    )
    
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': (
                'email', 'phone_number', 'first_name', 'last_name', 
                'country', 'password1', 'password2', 'role', 
                'is_verified', 'email_verified', 'profile_completed', 
                'is_active', 'is_staff'
            ),
        }),
    )
    
    readonly_fields = ('created_at', 'updated_at', 'last_login', 'profile_completed_at')

@admin.register(InvestmentProfile)
class InvestmentProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'employment_status', 'risk_tolerance', 'investment_goal', 'created_at')
    list_filter = ('employment_status', 'risk_tolerance', 'investment_goal', 'annual_income')
    search_fields = ('user__email', 'user__first_name', 'user__last_name', 'address', 'city')
    readonly_fields = ('created_at', 'updated_at')

admin.site.register(User, CustomUserAdmin)

