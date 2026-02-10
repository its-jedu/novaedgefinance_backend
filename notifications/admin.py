from django.contrib import admin

# Register your models here.
from .models import Notification, NotificationTemplate

@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ('notification_id', 'get_user_email', 'notification_type', 
                   'title', 'status', 'created_at')
    list_filter = ('notification_type', 'status', 'created_at')
    search_fields = ('user__email', 'title', 'message')
    readonly_fields = ('notification_id', 'created_at', 'updated_at', 
                      'email_sent_at', 'read_at')
    
    def get_user_email(self, obj):
        return obj.user.email
    get_user_email.short_description = 'User Email'
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user')

@admin.register(NotificationTemplate)
class NotificationTemplateAdmin(admin.ModelAdmin):
    list_display = ('template_name', 'notification_type', 'subject', 'is_active')
    list_filter = ('notification_type', 'is_active')
    search_fields = ('template_name', 'subject')
    list_editable = ('is_active',)
    readonly_fields = ('created_at', 'updated_at')