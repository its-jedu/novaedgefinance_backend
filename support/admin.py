from django.contrib import admin

# Register your models here.
from .models import SupportTicket, SupportMessage, SupportDepartment, FAQ

@admin.register(SupportTicket)
class SupportTicketAdmin(admin.ModelAdmin):
    list_display = ('ticket_id', 'get_user_email', 'subject', 'category', 
                   'status', 'priority', 'assigned_to', 'created_at')
    list_filter = ('status', 'priority', 'category', 'created_at')
    search_fields = ('user__email', 'subject', 'ticket_id')
    readonly_fields = ('ticket_id', 'message_count', 'last_message_at',
                      'resolved_at', 'created_at', 'updated_at')
    
    def get_user_email(self, obj):
        return obj.user.email
    get_user_email.short_description = 'User'
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user', 'assigned_to', 'resolved_by')

@admin.register(SupportMessage)
class SupportMessageAdmin(admin.ModelAdmin):
    list_display = ('message_id', 'get_ticket_id', 'get_sender_email', 
                   'is_admin', 'created_at', 'is_read')
    list_filter = ('is_admin', 'is_read', 'created_at')
    search_fields = ('ticket__ticket_id', 'sender__email', 'message')
    readonly_fields = ('message_id', 'created_at', 'read_at')
    
    def get_ticket_id(self, obj):
        return obj.ticket.ticket_id
    get_ticket_id.short_description = 'Ticket ID'
    
    def get_sender_email(self, obj):
        return obj.sender.email
    get_sender_email.short_description = 'Sender'
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('ticket', 'sender')

@admin.register(SupportDepartment)
class SupportDepartmentAdmin(admin.ModelAdmin):
    list_display = ('name', 'email', 'is_active', 'response_time_target', 
                   'open_tickets', 'resolved_tickets')
    list_filter = ('is_active', 'created_at')
    search_fields = ('name', 'email')
    filter_horizontal = ('assigned_admins',)
    readonly_fields = ('open_tickets', 'resolved_tickets', 
                      'average_response_time', 'created_at', 'updated_at')

@admin.register(FAQ)
class FAQAdmin(admin.ModelAdmin):
    list_display = ('question', 'category', 'display_order', 'is_published', 
                   'views', 'helpful_count', 'created_at')
    list_filter = ('category', 'is_published', 'created_at')
    search_fields = ('question', 'answer')
    list_editable = ('display_order', 'is_published')
    readonly_fields = ('views', 'helpful_count', 'created_at', 'updated_at')
