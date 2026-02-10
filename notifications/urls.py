from django.urls import path
from . import views

urlpatterns = [
    # User Notification Endpoints
    path('my/', views.UserNotificationsView.as_view(), name='my-notifications'),
    path('unread/', views.UnreadNotificationsView.as_view(), name='unread-notifications'),
    path('mark-read/', views.MarkAsReadView.as_view(), name='mark-read'),
    path('mark-all-read/', views.MarkAllAsReadView.as_view(), name='mark-all-read'),
    path('count/', views.NotificationCountView.as_view(), name='notification-count'),
    
    # Admin Notification Endpoints
    path('admin/list/', views.AdminNotificationListView.as_view(), name='admin-notifications'),
    path('admin/<uuid:notification_id>/resend/', views.AdminResendNotificationView.as_view(), name='resend-notification'),
    path('admin/templates/', views.AdminTemplateListView.as_view(), name='templates'),
    path('admin/templates/<int:id>/', views.AdminTemplateDetailView.as_view(), name='template-detail'),
    path('admin/send-test-email/', views.AdminSendTestEmailView.as_view(), name='send-test-email'),
]