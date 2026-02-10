from django.urls import path
from . import views

urlpatterns = [
    # User Support Endpoints
    path('tickets/', views.MyTicketsView.as_view(), name='my-tickets'),
    path('tickets/<uuid:ticket_id>/', views.TicketDetailView.as_view(), name='ticket-detail'),
    path('tickets/<uuid:ticket_id>/messages/', views.TicketMessagesView.as_view(), name='ticket-messages'),
    path('tickets/<uuid:ticket_id>/reply/', views.ReplyToTicketView.as_view(), name='reply-ticket'),
    path('tickets/<uuid:ticket_id>/close/', views.CloseTicketView.as_view(), name='close-ticket'),
    
    # Public FAQ Endpoints
    path('faqs/', views.FAQListView.as_view(), name='faqs'),
    path('faqs/<int:pk>/', views.FAQDetailView.as_view(), name='faq-detail'),
    path('faqs/<int:pk>/helpful/', views.MarkFAQHelpfulView.as_view(), name='mark-faq-helpful'),
    
    # Admin Support Endpoints
    path('admin/tickets/', views.AdminTicketListView.as_view(), name='admin-tickets'),
    path('admin/tickets/<uuid:ticket_id>/status/', views.AdminUpdateTicketStatusView.as_view(), name='update-ticket-status'),
    path('admin/tickets/<uuid:ticket_id>/assign/', views.AdminAssignTicketView.as_view(), name='assign-ticket'),
    path('admin/tickets/stats/', views.AdminTicketStatsView.as_view(), name='ticket-stats'),
    path('admin/departments/', views.AdminDepartmentListView.as_view(), name='departments'),
    path('admin/departments/<int:pk>/', views.AdminDepartmentDetailView.as_view(), name='department-detail'),
    path('admin/faqs/', views.AdminFAQListView.as_view(), name='admin-faqs'),
    path('admin/faqs/<int:pk>/', views.AdminFAQDetailView.as_view(), name='admin-faq-detail'),
]